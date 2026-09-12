"""Design token extraction from the reference screenshot + UI AST."""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from PIL import Image

from backend.schema.tokens import ColorToken, DesignTokens, FontToken, RadiusToken, SpacingToken
from backend.schema.ui_schema import UIDocument


def _to_hex(bgr: np.ndarray) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(int(round(v)) for v in bgr[:3]))


def extract_tokens(image: Image.Image, doc: UIDocument) -> DesignTokens:
    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    small = cv2.resize(rgb, (max(64, w // 6), max(64, h // 6)))
    pixels = np.float32(small.reshape(-1, 3))

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    k = min(6, max(3, len(pixels) // 4000))
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    order = np.argsort(-counts)

    bg_hex = (doc.screen.background or "#0f1115").lower()
    colors: list[ColorToken] = [ColorToken(name="background", hex=bg_hex, usage="screen", confidence=0.8)]
    max_sat = 0.0
    for rank, ci in enumerate(order[:5]):
        center = centers[ci]
        hexv = _to_hex(center)
        if hexv.lower() == bg_hex:
            continue
        mx, mn = center.max(), center.min()
        sat = float((mx - mn) / mx) if mx > 0 else 0.0
        share = counts[ci] / counts.sum()
        if share > 0.25 and sat < 0.2:
            name, usage, conf = "surface", "panels", 0.6
        elif sat > max_sat and sat > 0.25:
            max_sat = sat
            name, usage, conf = "primary", "actions", 0.55
        elif sat > 0.2:
            name, usage, conf = f"accent{'' if max_sat == 0 else '-2'}", "highlights", 0.45
        elif center.mean() > 150:
            name, usage, conf = "text-light", "text on dark", 0.5
        else:
            name, usage, conf = "text-dark", "text on light", 0.5
        colors.append(ColorToken(name=name, hex=hexv, usage=usage, confidence=conf))

    texts = [c for c in doc.components if c.type in ("text", "heading")]
    fonts: list[FontToken] = []
    body_h = sorted(c.bbox.height for c in texts if c.type == "text")
    if body_h:
        med = body_h[len(body_h) // 2]
        fonts.append(FontToken(size_px=max(10, round(med * 0.72)), weight=400, role="body", confidence=0.4))
    head_h = [c.bbox.height for c in texts if c.type == "heading"]
    if head_h:
        med = sorted(head_h)[len(head_h) // 2]
        fonts.append(FontToken(size_px=round(med * 0.72), weight=600, role="heading", confidence=0.4))
    if not fonts:
        fonts.append(FontToken(size_px=14, weight=400, role="body", confidence=0.2))

    buttons = [c for c in doc.components if c.type == "button"]
    radii = [RadiusToken(name="md", px=6.0, confidence=0.25)]
    if buttons:
        med_w = sorted(b.bbox.width for b in buttons)[len(buttons) // 2]
        radii.append(RadiusToken(name="control", px=round(min(10.0, med_w * 0.08)), confidence=0.2))

    spacing: list[SpacingToken] = []
    ys = sorted((c.bbox.y, c.bbox.height) for c in texts)
    gaps = [round(ys[i + 1][0] - (ys[i][0] + ys[i][1]), 1) for i in range(len(ys) - 1)]
    gaps = [g for g in gaps if 2 <= g <= 80]
    if gaps:
        spacing.append(SpacingToken(name="stack", px=float(sorted(gaps)[len(gaps) // 2]), confidence=0.4))
    spacing.append(SpacingToken(name="page", px=24.0, confidence=0.2))

    tokens = DesignTokens(
        colors=colors, fonts=fonts, radii=radii, spacing=spacing,
        grid={"columns": 12, "gutter_px": 16},
        raw={"source": "kmeans+ast", "k": int(k)},
    )
    return tokens


def tokens_to_design_md(tokens: DesignTokens, doc_metadata: dict[str, Any]) -> str:
    """Generate DESIGN.md — the inferred visual language description."""
    lines = ["# DESIGN — inferred visual language", ""]
    lines.append("## Colors")
    lines.append("| Token | Hex | Usage | Confidence |")
    lines.append("|---|---|---|---|")
    for c in tokens.colors:
        lines.append(f"| {c.name} | {c.hex} | {c.usage} | {c.confidence:.2f} |")
    lines += ["", "## Typography"]
    lines.append("| Role | Size (px) | Weight | Confidence |")
    lines.append("|---|---|---|---|")
    for f in tokens.fonts:
        lines.append(f"| {f.role} | {f.size_px} | {f.weight} | {f.confidence:.2f} |")
    lines += ["", "## Radius & spacing"]
    for r in tokens.radii:
        lines.append(f"- radius {r.name}: {r.px:.0f}px (confidence {r.confidence:.2f})")
    for s in tokens.spacing:
        lines.append(f"- space {s.name}: {s.px:.0f}px (confidence {s.confidence:.2f})")
    lines += ["", "## Notes",
              "- Tokens were inferred heuristically from the reference screenshot.",
              "- Low confidence values are honest: refine them in the editor.",
              f"- AST metadata: {doc_metadata}"]
    return "\n".join(lines) + "\n"
