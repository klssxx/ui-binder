"""Adapter interface — the plugin contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class Adapter(ABC):
    name: str = "abstract"

    @abstractmethod
    def detect(self, path: Path) -> bool:
        """Does this adapter apply to the project at ``path``?"""

    def inspect(self, path: Path) -> dict[str, Any]:
        """Framework-specific inspection summary."""
        return {"adapter": self.name}

    def capabilities(self, path: Path) -> list[dict[str, Any]]:
        """Capabilities contributed by this adapter."""
        return []

    def bindings_compat(self, path: Path) -> dict[str, Any]:
        """How bindings can be realized in this stack (events, state, calls)."""
        return {"adapter": self.name, "events": [], "state": []}

    def validate(self, path: Path) -> list[str]:
        """Sanity problems found for this adapter's stack."""
        return []
