"""Adapter system — extensible framework support without rewriting the core.

Each adapter declares: detect(path) · inspect(path) · capabilities(path) ·
bindings_compat(path) · validate(path). Registry-based plugin discovery:
new adapters (Vue, Svelte, PySide6, ...) just register themselves.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Adapter
from .python_adapter import PythonAdapter
from .fastapi_adapter import FastAPIAdapter
from .react_adapter import ReactAdapter
from .vite_adapter import ViteAdapter
from .tauri_adapter import TauriAdapter

_REGISTRY: dict[str, type[Adapter]] = {}


def register(cls: type[Adapter]) -> type[Adapter]:
    _REGISTRY[cls.name] = cls
    return cls


for _cls in (PythonAdapter, FastAPIAdapter, ReactAdapter, ViteAdapter, TauriAdapter):
    register(_cls)


def adapters_for(path: Path) -> list[Adapter]:
    return [cls() for cls in _REGISTRY.values() if cls().detect(path)]


def all_adapters() -> list[type[Adapter]]:
    return sorted(_REGISTRY.values(), key=lambda c: c.name)
