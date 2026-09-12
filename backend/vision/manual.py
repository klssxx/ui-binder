"""Manual provider — baseline producing an empty document for hand-built UIs."""
from __future__ import annotations

from typing import Any

from PIL import Image

from backend.schema.ui_schema import UIDocument, empty_document
from backend.vision.provider import VisionProvider, register


@register
class ManualVisionProvider(VisionProvider):
    name = "manual"

    def analyze(self, image: Image.Image) -> tuple[UIDocument, dict[str, Any]]:
        doc = empty_document(width=image.width, height=image.height)
        notes = {"provider": "manual", "components": 0,
                 "hint": "Empty screen; add components manually in the editor."}
        return doc, notes
