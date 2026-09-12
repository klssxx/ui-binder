"""VisionProvider interface — pluggable UI reconstruction engines.

Combination model (directive §9):
  AUTO DETECTION (heuristic / remote) + MANUAL CORRECTION (editor) + OPTIONAL AI.
The core works fully offline with LocalHeuristicVisionProvider.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from PIL import Image

from backend.schema.ui_schema import UIDocument


class VisionProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def analyze(self, image: Image.Image) -> tuple[UIDocument, dict[str, Any]]:
        """Produce a UI AST + analysis notes from a screenshot."""


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
    return _REGISTRY["heuristic"]()
