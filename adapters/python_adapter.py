from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Adapter


class PythonAdapter(Adapter):
    name = "python"

    def detect(self, path: Path) -> bool:
        return any(path.rglob("*.py")) if path.is_dir() else False

    def inspect(self, path: Path) -> dict[str, Any]:
        py_files = [p for p in path.rglob("*.py")]
        return {"adapter": self.name, "python_files": len(py_files)}

    def capabilities(self, path: Path) -> list[dict[str, Any]]:
        from backend.analyzer.python_analyzer import analyze_python_file
        from backend.analyzer.capability_builder import _add_python
        from backend.schema.capability import CapabilityGraph

        graph = CapabilityGraph()
        modules = []
        for p in sorted(path.rglob("*.py"))[:400]:
            try:
                modules.append((p.relative_to(path).as_posix(), analyze_python_file(p)))
            except (SyntaxError, OSError):
                continue
        _add_python(graph, modules)
        return [c.model_dump() for c in graph.nodes]
