from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import Adapter


class TauriAdapter(Adapter):
    name = "tauri"

    def detect(self, path: Path) -> bool:
        return (path / "src-tauri" / "tauri.conf.json").is_file()

    def inspect(self, path: Path) -> dict[str, Any]:
        conf_path = path / "src-tauri" / "tauri.conf.json"
        info: dict[str, Any] = {"adapter": self.name}
        if conf_path.is_file():
            try:
                conf = json.loads(conf_path.read_text(encoding="utf-8"))
                info["productName"] = conf.get("productName", "")
                info["identifier"] = conf.get("identifier", "")
                info["devUrl"] = conf.get("build", {}).get("devUrl", "")
            except (json.JSONDecodeError, OSError):
                info["error"] = "unreadable tauri.conf.json"
        return info

    def validate(self, path: Path) -> list[str]:
        problems = []
        src_tauri = path / "src-tauri"
        if not (src_tauri / "Cargo.toml").is_file():
            problems.append("src-tauri without Cargo.toml.")
        if not any(src_tauri.glob("src/*.rs")):
            problems.append("src-tauri without Rust sources.")
        return problems
