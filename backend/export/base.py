"""Exporter ABC and registry for multi-target export.

New exporters (react-vite-ts, pyside6-widgets, ...) register themselves
here. The API layer dispatches by target_id; default stays React for
backward compatibility.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ExportPlan:
    """Honest description of what an exporter will produce."""

    def __init__(self) -> None:
        self.target: str = ""
        self.target_label: str = ""
        self.files_created: list[str] = []
        self.components_total: int = 0
        self.components_native: int = 0
        self.components_fallback: int = 0
        self.bindings_total: int = 0
        self.bindings_realizable: int = 0
        self.bindings_unresolved: int = 0
        self.warnings: list[str] = []
        self.layout_fallbacks: list[str] = []
        self.unsupported: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class Exporter(ABC):
    """Target-specific code generator."""

    target_id: str = "abstract"
    label: str = "Abstract exporter"

    @abstractmethod
    def plan(
        self,
        document: Any,
        bindings: list[dict[str, Any]],
        capabilities: list[dict[str, Any]],
        tokens: dict[str, Any] | None,
    ) -> ExportPlan:
        """Dry-run: describe what would be generated without writing."""

    @abstractmethod
    def validate(
        self,
        document: Any,
        bindings: list[dict[str, Any]],
        capabilities: list[dict[str, Any]],
        tokens: dict[str, Any] | None,
    ) -> list[str]:
        """Pre-flight warnings. Empty = no concerns."""

    @abstractmethod
    def export(
        self,
        document: Any,
        bindings: list[dict[str, Any]],
        capabilities: list[dict[str, Any]],
        tokens: dict[str, Any] | None,
        target: Path,
        source_project: Path | None = None,
        image_resolver=None,
    ) -> dict[str, Any]:
        """Generate the project. Returns a plan dict."""


_REGISTRY: dict[str, type[Exporter]] = {}


def register_exporter(cls: type[Exporter]) -> type[Exporter]:
    _REGISTRY[cls.target_id] = cls
    return cls


def get_exporter(target_id: str) -> type[Exporter]:
    if target_id not in _REGISTRY:
        raise ValueError(
            f"Unknown export target '{target_id}'. Available: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[target_id]


def available_exporters() -> list[type[Exporter]]:
    return sorted(_REGISTRY.values(), key=lambda c: c.target_id)
