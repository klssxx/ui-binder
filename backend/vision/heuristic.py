"""LocalHeuristicVisionProvider — deterministic OpenCV-based UI detection.

Pipeline (no OCR, no network):
  1. background estimation from border ring
  2. two-level ink masks:
       strong (dist > 45): buttons, inputs borders, text, charts
       weak   (dist > 12): subtle panels, navbar, sidebar, cards
  3. controls (buttons / bordered inputs) from closed STRONG blobs
  4. panels/navbar/sidebar from WEAK blobs minus strong pixels,
     with thin horizontal dividers removed (open 3x1) so bands don't merge
  5. text lines: STRONG residue minus control bboxes, horizontally merged
  6. dividers from thin wide blobs
  7. charts from edge density inside containers
  8. hierarchy by bbox containment, dedup by IoU

Every detection carries type + confidence. Confidence is never a fact:
manual corrections in the editor override everything.
"""
from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np
from PIL import Image

from backend.schema.ui_schema import BBox, Component, UIDocument
from backend.vision.provider import VisionProvider, register

_MIN_AREA_FRAC = 0.0008       # ignore blobs smaller than this fraction of the image
_BUTTON_W = (36, 260)
_BUTTON_H = (22, 62)
_TEXT_H = (8, 46)
_HEADING_MIN_H = 30
_DIVIDER_MAX_H = 6
_CHART_EDGE_DENSITY = 0.055
_STRONG_DIST = 45
_WEAK_DIST = 12


def _hex(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(int(round(v)) for v in rgb[:3]))


def _iou(a: BBox, b: BBox) -> float:
    x1, y1 = max(a.x, b.x), max(a.y, b.y)
    x2 = min(a.x + a.width, b.x + b.width)
    y2 = min(a.y + a.height, b.y + b.height)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    return inter / (a.area() + b.area() - inter)


class _Raw:
    __slots__ = ("type", "bbox", "confidence", "text", "styles", "metadata")

    def __init__(self, type_: str, bbox: BBox, confidence: float, *,
                 text: str | None = None, styles: dict | None = None, metadata: dict | None = None):
        self.type = type_
        self.bbox = bbox
        self.confidence = confidence
        self.text = text
        self.styles = styles or {}
        self.metadata = metadata or {}

    def area(self) -> float:
        return self.bbox.area()


def _blob_stats(mask: np.ndarray):
    n, _labels, stats, _cent = cv2.connectedComponentsWithStats(mask, connectivity=8)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        yield int(x), int(y), int(w), int(h), int(area)


@register
class LocalHeuristicVisionProvider(VisionProvider):
    name = "heuristic"

    def analyze(self, image: Image.Image) -> tuple[UIDocument, dict[str, Any]]:
        t0 = time.perf_counter()
        rgb = np.asarray(image.convert("RGB"))
        H, W = rgb.shape[:2]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

        bg = self._estimate_background(rgb)
        dist = np.abs(rgb.astype(np.int16) - bg[None, None, :]).max(axis=2)
        strong = ((dist > _STRONG_DIST) * 255).astype(np.uint8)
        weak = ((dist > _WEAK_DIST) * 255).astype(np.uint8)

        controls = self._controls(rgb, strong, W, H)
        panels = self._panels(weak, strong, W, H, bg)
        texts = self._text_lines(rgb, strong, controls, W, H)
        dividers = self._dividers(weak, W, H)
        charts = self._charts(gray, panels, W, H)
        edge_boxes = self._edge_containers(gray, W, H,
                                           existing=controls + panels + texts + dividers)

        raws = self._dedup(controls + panels + texts + dividers + charts + edge_boxes)
        components = self._build_tree(raws, W, H)

        doc = UIDocument(
            screen={"id": "screen", "width": float(W), "height": float(H),
                    "background": _hex(bg), "preset": None},
            components=components,
            metadata={"provider": self.name},
        )
        counts: dict[str, int] = {}
        for c in components:
            counts[c.type] = counts.get(c.type, 0) + 1
        notes = {
            "provider": self.name,
            "components": len(components),
            "counts": counts,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
            "image_size": [W, H],
            "background": _hex(bg),
            "warning": "Heuristic vision has no OCR: texts are inferred positions, edit them in the inspector.",
        }
        return doc, notes

    # ---------- steps ----------

    def _estimate_background(self, rgb: np.ndarray) -> np.ndarray:
        h, w = rgb.shape[:2]
        # bottom rows + right cols dominate plain app backgrounds; use full ring
        ring = np.concatenate([
            rgb[-max(2, h // 40):, :].reshape(-1, 3),
            rgb[:, -max(2, w // 40):].reshape(-1, 3),
            rgb[: max(2, h // 40), :].reshape(-1, 3),
            rgb[:, : max(2, w // 40)].reshape(-1, 3),
        ])
        quantized = (ring // 8 * 8)
        colors, counts = np.unique(quantized, axis=0, return_counts=True)
        return colors[np.argmax(counts)].astype(np.float64)

    def _controls(self, rgb, strong, W, H) -> list[_Raw]:
        """Buttons and bordered inputs from the STRONG mask."""
        closed = cv2.morphologyEx(strong, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        out: list[_Raw] = []
        min_area = _MIN_AREA_FRAC * W * H
        for x, y, w, h, area in _blob_stats(closed):
            if area < min_area or w < 12 or h < 10:
                continue
            if w >= W * 0.97 and h >= H * 0.97:
                continue
            fill = area / (w * h)
            region2d = rgb[y:y + h, x:x + w]
            pad = 4 if (w > 12 and h > 12) else 0
            inner_std = float(region2d[pad:-pad, pad:-pad].mean(axis=2).std()) if pad else 0.0
            bbox = BBox(x=float(x), y=float(y), width=float(w), height=float(h))
            aspect = w / max(h, 1)
            # bordered hollow rectangle of control height → text input
            if (0.06 <= fill <= 0.62 and 24 <= h <= 64 and 120 <= w <= 900
                    and aspect >= 2.2 and inner_std < 10.0):
                out.append(_Raw("input", bbox, 0.5,
                                styles={"background": "transparent", "border": True}))
                continue
            if fill < 0.55:
                continue
            mean = region2d.reshape(-1, 3).mean(axis=0)
            if (_BUTTON_W[0] <= w <= _BUTTON_W[1] and _BUTTON_H[0] <= h <= _BUTTON_H[1]
                    and 1.2 <= aspect <= 9):
                out.append(_Raw("button", bbox, 0.78,
                                styles={"background": _hex(mean), "radius": 6}))
                continue
        return out

    def _panels(self, weak, strong, W, H, bg) -> list[_Raw]:
        """Navbar/sidebar via row/column ink profiles (fringe-bridge immune),
        then panels/cards from the WEAK mask with strong content carved out."""
        out: list[_Raw] = []
        out += self._bands(weak, W, H)

        without_strong = cv2.bitwise_and(weak, cv2.bitwise_not(strong))
        # 1px erosion kills antialias fringes; open(3,1) drops thin horizontal dividers
        eroded = cv2.erode(without_strong, np.ones((2, 2), np.uint8))
        cleaned = cv2.morphologyEx(eroded, cv2.MORPH_OPEN, np.ones((3, 1), np.uint8))
        closed = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        min_area = 0.002 * W * H
        for x, y, w, h, area in _blob_stats(closed):
            if area < min_area or w < 40 or h < 24:
                continue
            if w >= W * 0.97 and h >= H * 0.97:
                continue
            fill = area / (w * h)
            if fill < 0.30:
                continue
            bbox = BBox(x=float(x), y=float(y), width=float(w), height=float(h))
            if any(_iou(bbox, e.bbox) > 0.7 for e in out):
                continue
            if h >= H * 0.45 and w <= W * 0.35 and x < W * 0.4:
                out.append(_Raw("sidebar", bbox, 0.55))
                continue
            if w >= W * 0.6 and y < H * 0.2 and h < H * 0.25:
                out.append(_Raw("navbar", bbox, 0.6))
                continue
            if w * h > 0.015 * W * H:
                out.append(_Raw("panel" if fill > 0.6 else "container", bbox,
                                0.55 if fill > 0.6 else 0.4))
        return out

    def _bands(self, weak, W, H) -> list[_Raw]:
        """Top horizontal band → navbar; left vertical band (below navbar) → sidebar."""
        out: list[_Raw] = []
        ink = (weak > 0)
        row_frac = ink.mean(axis=1)
        y = 0
        navbar_h = 0
        if H > 40 and row_frac[0] > 0.45:
            while y < int(H * 0.3) and row_frac[y] > 0.45:
                y += 1
            navbar_h = y
            if navbar_h >= 12:
                out.append(_Raw("navbar",
                                BBox(x=0.0, y=0.0, width=float(W), height=float(navbar_h)), 0.6))
        col_frac = ink[navbar_h + 2:, :].mean(axis=0) if H - navbar_h - 2 > 10 else ink.mean(axis=0)
        x = 0
        if W > 40 and col_frac[0] > 0.45:
            while x < int(W * 0.45) and col_frac[x] > 0.45:
                x += 1
            side_w = x
            if side_w >= 40:
                out.append(_Raw("sidebar",
                                BBox(x=0.0, y=float(navbar_h), width=float(side_w),
                                     height=float(H - navbar_h)), 0.55))
        return out

    def _text_lines(self, rgb, strong, controls, W, H) -> list[_Raw]:
        """Text lines: strong residue minus CONTROL boxes (panels keep their text)."""
        residue = strong.copy()
        for c in controls:
            b = c.bbox
            residue[int(b.y):int(b.y + b.height), int(b.x):int(b.x + b.width)] = 0
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 3))
        merged = cv2.morphologyEx(residue, cv2.MORPH_CLOSE, kernel)
        out: list[_Raw] = []
        for x, y, w, h, area in _blob_stats(merged):
            if area < 40 or not (_TEXT_H[0] <= h <= _TEXT_H[1]) or w < 10 or w > W * 0.95:
                continue
            roi = rgb[y:y + h, x:x + w]
            mask_px = residue[y:y + h, x:x + w].reshape(-1) > 0
            if mask_px.sum() == 0:
                continue
            color = roi.reshape(-1, 3)[mask_px].mean(axis=0)
            bbox = BBox(x=float(x), y=float(y), width=float(w), height=float(h))
            if h >= _HEADING_MIN_H:
                out.append(_Raw("heading", bbox, 0.55,
                                styles={"color": _hex(color), "fontSize": round(h * 0.72)}))
            else:
                out.append(_Raw("text", bbox, 0.5,
                                styles={"color": _hex(color), "fontSize": max(9, round(h * 0.72))}))
        return out

    def _dividers(self, weak, W, H) -> list[_Raw]:
        horiz = cv2.morphologyEx(weak, cv2.MORPH_OPEN, np.ones((1, 5), np.uint8))
        out = []
        for x, y, w, h, area in _blob_stats(horiz):
            if h <= _DIVIDER_MAX_H and w >= W * 0.08:
                out.append(_Raw("divider", BBox(x=float(x), y=float(y), width=float(w),
                                                height=max(float(h), 1.0)), 0.6))
        return out

    def _charts(self, gray, panels, W, H) -> list[_Raw]:
        """Charts: enough edges AND a high share of DIAGONAL orientations.

        Text strokes are mostly axis-aligned; chart lines tilt. Orientation
        histogram over Canny-masked Sobel gradients separates them.
        """
        edges = cv2.Canny(gray, 50, 150)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        out = []
        for p in panels:
            b = p.bbox
            x0, y0 = int(b.x), int(b.y)
            x1, y1 = int(b.x + b.width), int(b.y + b.height)
            roi_edges = edges[y0:y1, x0:x1]
            if roi_edges.size == 0:
                continue
            edge_count = int((roi_edges > 0).sum())
            if edge_count < 1200 or b.width < 80 or b.height < 60:
                continue
            angles = np.degrees(np.arctan2(gy[y0:y1, x0:x1][roi_edges > 0],
                                          gx[y0:y1, x0:x1][roi_edges > 0]))
            diag = np.abs(((angles + 180) % 180) - 90)  # 0=axis-aligned, 90=45° diagonal
            diagonal_frac = float((diag > 20).mean())
            if diagonal_frac > 0.30:
                inner = BBox(x=b.x + b.width * 0.08, y=b.y + b.height * 0.12,
                             width=b.width * 0.84, height=b.height * 0.76)
                out.append(_Raw("chart", inner, 0.35))
        return out[:4]

    def _edge_containers(self, gray, W, H, existing: list[_Raw]) -> list[_Raw]:
        edges = cv2.Canny(gray, 50, 150)
        dil = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(dil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        min_area = 0.004 * W * H
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w * h < min_area or w >= W * 0.98 or h >= H * 0.98:
                continue
            bbox = BBox(x=float(x), y=float(y), width=float(w), height=float(h))
            if any(_iou(bbox, e.bbox) > 0.7 for e in existing):
                continue
            out.append(_Raw("container", bbox, 0.4))
        return out

    # ---------- assembly ----------

    def _dedup(self, raws: list[_Raw]) -> list[_Raw]:
        raws = sorted(raws, key=lambda r: -r.confidence)
        kept: list[_Raw] = []
        for r in raws:
            if any(r.type == k.type and _iou(r.bbox, k.bbox) > 0.8 for k in kept):
                continue
            kept.append(r)
        return kept

    def _build_tree(self, raws: list[_Raw], W: int, H: int) -> list[Component]:
        ordered = sorted(raws, key=lambda r: -r.bbox.area())
        id_by_raw: dict[int, str] = {}
        for i, r in enumerate(ordered, start=1):
            id_by_raw[id(r)] = f"component_{i:04d}"

        parent_by_raw: dict[int, _Raw | None] = {}
        for r in ordered:
            parent = None
            for other in ordered:
                if other is r or other.bbox.area() <= r.bbox.area():
                    continue
                o, b = other.bbox, r.bbox
                if (o.x - 2 <= b.x and o.y - 2 <= b.y
                        and o.x + o.width + 2 >= b.x + b.width
                        and o.y + o.height + 2 >= b.y + b.height):
                    if parent is None or other.bbox.area() < parent.bbox.area():
                        parent = other
            parent_by_raw[id(r)] = parent

        components: list[Component] = []
        for r in ordered:
            raw_parent = parent_by_raw[id(r)]
            parent_id = id_by_raw.get(id(raw_parent)) if raw_parent is not None else "screen"
            components.append(Component(
                id=id_by_raw[id(r)],
                type=r.type,  # type: ignore[arg-type]
                name=f"{r.type}-{id_by_raw[id(r)].split('_')[-1]}",
                parent_id=parent_id,
                children=[],
                bbox=r.bbox,
                text=r.text,
                styles=r.styles,
                metadata={"confidence": round(r.confidence, 3), "source": self.name},
            ))
        by_id = {c.id: c for c in components}
        for c in components:
            if c.parent_id in by_id:
                by_id[c.parent_id].children.append(c.id)
        components.sort(key=lambda c: (-(c.bbox.area()), c.bbox.y, c.bbox.x))
        return components
