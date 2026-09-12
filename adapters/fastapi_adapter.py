from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Adapter
from .python_adapter import PythonAdapter


class FastAPIAdapter(Adapter):
    name = "fastapi"

    def detect(self, path: Path) -> bool:
        markers = ("requirements.txt", "pyproject.toml")
        for marker in markers:
            f = path / marker
            if f.is_file():
                try:
                    text = f.read_text(encoding="utf-8", errors="replace").lower()
                except OSError:
                    continue
                if "fastapi" in text or "uvicorn" in text:
                    return True
        # import-level fallback (e.g. monorepo sample without its own requirements)
        for p in list(path.rglob("*.py"))[:200]:
            try:
                if "from fastapi" in p.read_text(encoding="utf-8", errors="replace")[:2000]:
                    return True
            except OSError:
                continue
        return False

    def inspect(self, path: Path) -> dict[str, Any]:
        routes = [c for c in self.capabilities(path) if c.get("kind") == "route"]
        return {"adapter": self.name, "routes": len(routes)}

    def capabilities(self, path: Path) -> list[dict[str, Any]]:
        caps = PythonAdapter().capabilities(path)
        return [c for c in caps if c.get("framework") == "fastapi"]

    def bindings_compat(self, path: Path) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "events": ["HTTP request"],
            "state": ["response payload"],
            "call_style": "fetch(method, path) with JSON body",
        }

    def validate(self, path: Path) -> list[str]:
        problems = []
        if not (path / "requirements.txt").is_file() and not (path / "pyproject.toml").is_file():
            problems.append("No requirements.txt/pyproject.toml found for the FastAPI project.")
        return problems
