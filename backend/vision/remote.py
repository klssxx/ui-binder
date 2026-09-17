"""OpenAICompatibleVisionProvider — optional remote multimodal reconstruction.

Configuration via environment only (UIBINDER_VISION_BASE_URL / _MODEL / _API_KEY).
The key is never persisted and never logged. The app works fully without it.

Supports rich visual contract: role, parent_hint, group_hint, styles, state.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import time
from typing import Any

from PIL import Image

from backend import config
from backend.schema.ui_schema import BBox, Component, UIDocument
from backend.vision.contract import DetectedComponent, VisionProvenance, VisionResult, VisionUsage

_PROMPT = (
    "You are a UI reconstruction engine. Analyze the screenshot and return STRICT JSON "
    "with shape {\"components\": [{\"type\": str, \"bbox\": {\"x\": float, \"y\": float, "
    "\"width\": float, \"height\": float}, \"text\": str|null, \"confidence\": float, "
    "\"role\": str|null, \"parent_hint\": str|null, \"group_hint\": str|null, "
    "\"styles\": {str: str}, \"state\": {str: str}, \"visual_semantic\": str|null}]}. "
    "Allowed types: container, panel, card, text, heading, button, input, textarea, "
    "select, checkbox, radio, image, icon, table, chart, tabs, sidebar, navbar, modal, "
    "divider, custom. "
    "Allowed roles: primary, secondary, danger, success, warning, info, link, nav, form, "
    "header, footer, content, sidebar, overlay, cta, badge, tag, avatar. "
    "styles keys: background, color, border, border_radius, font_family, font_size, "
    "font_weight, opacity, text_align, shadow, padding, margin. "
    "state keys: enabled, disabled, selected, checked, focused, active, readonly, required, "
    "loading, error, empty, filled. "
    "visual_semantic: one of the allowed types or 'unknown'. "
    "Use pixel coordinates relative to the full image. No prose, only JSON."
)

_ALLOWED_TYPES = {
    "container", "panel", "card", "text", "heading", "button", "input", "textarea",
    "select", "checkbox", "radio", "image", "icon", "table", "chart", "tabs",
    "sidebar", "navbar", "modal", "divider", "custom",
}

_ALLOWED_ROLES = {
    "primary", "secondary", "danger", "success", "warning", "info", "link", "nav",
    "form", "header", "footer", "content", "sidebar", "overlay", "cta", "badge",
    "tag", "avatar",
}


def _image_hash(image: Image.Image) -> str:
    """Generate a hash for the image for tracking."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return hashlib.sha256(buf.getvalue()).hexdigest()[:16]


class OpenAICompatibleVisionProvider:
    name = "remote"

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None, timeout: float = 60.0):
        self.base_url = (base_url or config.VISION_BASE_URL).rstrip("/")
        self.model = model or config.VISION_MODEL
        self._api_key = api_key or config.VISION_API_KEY
        self.timeout = timeout
        if not self.base_url or not self.model or not self._api_key:
            raise RuntimeError(
                "El proveedor de visión remoto no está configurado. Define UIBINDER_VISION_BASE_URL, "
                "UIBINDER_VISION_MODEL y UIBINDER_VISION_API_KEY (ver .env.example)."
            )

    def analyze(self, image: Image.Image) -> tuple[UIDocument, dict[str, Any]]:
        import httpx

        t_start = time.time()
        img_hash = _image_hash(image)

        b64 = self._encode(image)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]},
            ],
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            latency = (time.time() - t_start) * 1000
            usage = VisionUsage(
                provider=self.name, model=self.model, latency_ms=latency,
                success=False, image_hash=img_hash,
            )
            provenance = VisionProvenance(
                provider=self.name, model=self.model, mode="REMOTE",
                privacy="image was sent to external endpoint",
                fallback_used=True, warnings=[str(e)],
            )
            raise RuntimeError(f"Remote vision failed: {e}") from e

        raw = self._extract_json(content)
        doc = self._to_document(raw, image)
        
        latency = (time.time() - t_start) * 1000
        confidences = [c.metadata.get("confidence", 0.5) for c in doc.components]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        usage = VisionUsage(
            provider=self.name, model=self.model, latency_ms=latency,
            success=True, image_hash=img_hash,
        )
        provenance = VisionProvenance(
            provider=self.name, model=self.model, mode="REMOTE",
            privacy="image was sent to external endpoint",
            confidence_avg=avg_conf,
        )
        
        notes = {
            "provider": self.name, "model": self.model,
            "components": len(doc.components), "privacy": "image was sent to external endpoint",
            "usage": usage.__dict__, "provenance": provenance.__dict__,
        }
        return doc, notes

    def analyze_rich(self, image: Image.Image) -> VisionResult:
        """Full analysis with rich contract."""
        doc, notes = self.analyze(image)
        components = []
        for c in doc.components:
            dc = DetectedComponent(
                type=c.type,
                bbox={"x": c.bbox.x, "y": c.bbox.y, "width": c.bbox.width, "height": c.bbox.height},
                text=c.text,
                confidence=c.metadata.get("confidence", 0.5),
                role=c.metadata.get("role"),
                parent_hint=c.metadata.get("parent_hint"),
                group_hint=c.metadata.get("group_hint"),
                styles=c.metadata.get("styles", {}),
                state=c.metadata.get("state", {}),
                visual_semantic=c.metadata.get("visual_semantic"),
            )
            components.append(dc)
        
        usage = VisionUsage(**notes.get("usage", {}))
        prov_dict = notes.get("provenance", {})
        provenance = VisionProvenance(**prov_dict)
        
        return VisionResult(
            components=components, usage=usage, provenance=provenance,
            raw_response=None,
        )

    @staticmethod
    def _encode(image: Image.Image) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.S)
        candidate = fenced.group(1) if fenced else content
        start, end = candidate.find("{"), candidate.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Remote provider returned no JSON object.")
        return json.loads(candidate[start:end + 1])

    def _to_document(self, raw: dict[str, Any], image: Image.Image) -> UIDocument:
        components: list[Component] = []
        for i, item in enumerate(raw.get("components", []), start=1):
            type_ = str(item.get("type", "custom")).lower()
            if type_ not in _ALLOWED_TYPES:
                type_ = "custom"
            
            bbox_raw = item.get("bbox", {})
            try:
                bbox = BBox(
                    x=float(bbox_raw.get("x", 0)), y=float(bbox_raw.get("y", 0)),
                    width=float(bbox_raw.get("width", 1)), height=float(bbox_raw.get("height", 1)),
                )
            except Exception:
                continue
            
            conf = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
            
            # Extract rich fields
            role = item.get("role")
            if role and str(role).lower() not in _ALLOWED_ROLES:
                role = None
            parent_hint = item.get("parent_hint")
            group_hint = item.get("group_hint")
            styles = item.get("styles", {})
            state = item.get("state", {})
            visual_semantic = item.get("visual_semantic")
            
            metadata = {"confidence": conf, "source": self.name}
            if role:
                metadata["role"] = role
            if parent_hint:
                metadata["parent_hint"] = parent_hint
            if group_hint:
                metadata["group_hint"] = group_hint
            if styles:
                metadata["styles"] = styles
            if state:
                metadata["state"] = state
            if visual_semantic:
                metadata["visual_semantic"] = visual_semantic
            
            components.append(Component(
                id=f"component_{i:04d}", type=type_,
                name=f"{type_}-{i:04d}", parent_id="screen", children=[],
                bbox=bbox, text=item.get("text"), metadata=metadata,
            ))
        
        # Assign parents by containment
        ordered = sorted(components, key=lambda c: -c.bbox.area())
        by_id = {c.id: c for c in ordered}
        for c in ordered:
            parent = None
            for other in ordered:
                if other is c or other.bbox.area() <= c.bbox.area():
                    continue
                if other.contains(c):
                    if parent is None or other.bbox.area() < parent.bbox.area():
                        parent = other
            c.parent_id = (parent.id if parent else "screen")
            if c.parent_id in by_id and c.id != c.parent_id:
                by_id[c.parent_id].children.append(c.id)
        
        return UIDocument(
            screen={"id": "screen", "width": float(image.width), "height": float(image.height)},
            components=components, metadata={"provider": self.name},
        )
