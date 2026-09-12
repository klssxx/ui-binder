from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Adapter


class ReactAdapter(Adapter):
    name = "react"

    def detect(self, path: Path) -> bool:
        pkg = path / "package.json"
        if pkg.is_file():
            try:
                import json
                data = json.loads(pkg.read_text(encoding="utf-8"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "react" in deps:
                    return True
            except (json.JSONDecodeError, OSError):
                pass
        return any(path.rglob("*.tsx")) or any(path.rglob("*.jsx"))

    def inspect(self, path: Path) -> dict[str, Any]:
        components = [c for c in self.capabilities(path) if c.get("kind") == "component"]
        return {"adapter": self.name, "components": len(components)}

    def capabilities(self, path: Path) -> list[dict[str, Any]]:
        from backend.analyzer.node_bridge import analyze_js_files
        files = [p for p in sorted(path.rglob("*.ts")) + sorted(path.rglob("*.tsx"))
                 + sorted(path.rglob("*.js")) + sorted(path.rglob("*.jsx"))
                 if "node_modules" not in p.parts][:200]
        results = analyze_js_files(files)
        from backend.analyzer.capability_builder import _add_js
        from backend.schema.capability import CapabilityGraph
        graph = CapabilityGraph()
        rel_by_abs = {str(rooted): rooted.relative_to(path).as_posix() for rooted in files}
        _add_js(graph, results, rel_by_abs)
        return [c.model_dump() for c in graph.nodes]

    def bindings_compat(self, path: Path) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "events": ["onClick", "onChange", "onSubmit", "onInput", "onFocus", "onBlur"],
            "state": ["useState", "useReducer", "store"],
            "call_style": "async handler function",
        }
