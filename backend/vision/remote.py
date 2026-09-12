"""OpenAICompatibleVisionProvider — optional remote multimodal reconstruction.

Configuration via environment only (UIBINDER_VISION_BASE_URL / _MODEL / _API_KEY).
The key is never persisted and never logged. The app works fully without it.

Implementation status: IMPLEMENTED, verification PARTIAL — exercised in tests
with a stubbed HTTP layer; no live provider is called from the test suite.
"""
from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

from PIL import Image

from backend import config
from backend.schema.ui_schema import BBox, Component, UIDocument

_PROMPT = (
    "You are a UI reconstruction engine. Analyze the screenshot and return STRICT JSON "
    "with shape {\"components\": [{\"type\": str, \"bbox\": {\"x\": float, \"y\": float, "
    "\"width\": float, \"height\": float}, \"text\": str|null, \"confidence\": float}]}. "
    "Allowed types: container, panel, card, text, heading, button, input, textarea, "
    "select, checkbox, radio, image, icon, table, chart, tabs, sidebar, navbar, modal, "
    "divider. Use pixel coordinates relative to the full image. No prose, only JSON."
)

_ALLOWED_TYPES = {
    "container", "panel", "card", "text", "heading", "button", "input", "textarea",
    "select", "checkbox", "radio", "image", "icon", "table", "chart", "tabs",
    "sidebar", "navbar", "modal", "divider",
}


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
                "Remote vision provider is not configured. Set UIBINDER_VISION_BASE_URL, "
                "UIBINDER_VISION_MODEL and UIBINDER_VISION_API_KEY (see .env.example)."
            )

    def analyze(self, image: Image.Image) -> tuple[UIDocument, dict[str, Any]]:
        import httpx  # already a backend dependency

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
        # Privacy: this call sends the screenshot to the configured external endpoint.
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        raw = self._extract_json(content)
        doc = self._to_document(raw, image)
        notes = {"provider": self.name, "model": self.model, "components": len(doc.components),
                 "privacy": "image was sent to the configured external endpoint"}
        return doc, notes

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
            components.append(Component(
                id=f"component_{i:04d}", type=type_,  # type: ignore[arg-type]
                name=f"{type_}-{i:04d}", parent_id="screen", children=[],
                bbox=bbox, text=item.get("text"), metadata={"confidence": conf, "source": self.name},
            ))
        # Assign parents by containment, same as heuristic assembly.
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
