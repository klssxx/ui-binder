"""VisionProvider interface — pluggable UI reconstruction engines.

Combination model (directive §9):
  AUTO DETECTION (heuristic / remote) + MANUAL CORRECTION (editor) + OPTIONAL AI.
The core works fully offline with LocalHeuristicVisionProvider.

Modes:
  LOCAL:  heuristic only, no image leaves the machine.
  REMOTE: external provider only.
  AUTO:   local first, escalate to remote if confidence < threshold.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from PIL import Image

from backend.schema.ui_schema import UIDocument
from backend.vision.contract import VisionResult


class VisionProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def analyze(self, image: Image.Image) -> tuple[UIDocument, dict[str, Any]]:
        """Produce a UI AST + analysis notes from a screenshot."""

    def analyze_rich(self, image: Image.Image) -> VisionResult:
        """Full analysis with rich contract. Default wraps analyze()."""
        doc, notes = self.analyze(image)
        from backend.vision.contract import DetectedComponent, VisionUsage, VisionProvenance
        components = []
        for c in doc.components:
            dc = DetectedComponent(
                type=c.type,
                bbox={"x": c.bbox.x, "y": c.bbox.y, "width": c.bbox.width, "height": c.bbox.height},
                text=c.text,
                confidence=c.metadata.get("confidence", 0.5),
            )
            components.append(dc)
        usage = VisionUsage(provider=notes.get("provider", self.name), model=notes.get("model", ""))
        provenance = VisionProvenance(
            provider=notes.get("provider", self.name),
            model=notes.get("model", ""),
            mode="LOCAL",
            privacy="no data leaves the machine",
        )
        return VisionResult(components=components, usage=usage, provenance=provenance)


_REGISTRY: dict[str, type[VisionProvider]] = {}


def register(cls: type[VisionProvider]) -> type[VisionProvider]:
    _REGISTRY[cls.name] = cls
    return cls


def list_providers() -> list[str]:
    return sorted(_REGISTRY)


def get_provider(name: Optional[str] = None) -> VisionProvider:
    from .manual import ManualVisionProvider

    key = (name or "heuristic").lower()
    if key == "manual":
        return ManualVisionProvider()
    if key in _REGISTRY:
        return _REGISTRY[key]()
    if key == "remote":
        from .remote import OpenAICompatibleVisionProvider
        return OpenAICompatibleVisionProvider()
    if key == "mistral":
        from .remote import OpenAICompatibleVisionProvider
        # Mistral uses the same OpenAI-compatible interface
        return OpenAICompatibleVisionProvider()
    if key == "auto":
        from .auto import AutoVisionProvider
        return AutoVisionProvider()
    return _REGISTRY["heuristic"]()
