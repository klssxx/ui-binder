from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Adapter


class ViteAdapter(Adapter):
    name = "vite"

    def detect(self, path: Path) -> bool:
        if any(path.glob("vite.config.*")):
            return True
        pkg = path / "package.json"
        if pkg.is_file():
            try:
                import json
                data = json.loads(pkg.read_text(encoding="utf-8"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                if "vite" in deps:
                    return True
            except (json.JSONDecodeError, OSError):
                pass
        return False

    def inspect(self, path: Path) -> dict[str, Any]:
        config = next(iter(path.glob("vite.config.*")), None)
        scripts: dict[str, str] = {}
        pkg = path / "package.json"
        if pkg.is_file():
            try:
                import json
                scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
            except (json.JSONDecodeError, OSError):
                pass
        return {"adapter": self.name,
                "config": config.name if config else None,
                "scripts": scripts}

    def validate(self, path: Path) -> list[str]:
        problems = []
        if not (path / "index.html").is_file():
            problems.append("Vite project without index.html at root.")
        return problems
