"""Fuentes del sistema para el inspector tipográfico (F4).

Lee los nombres de familia REALES de los .ttf/.otf con fontTools (no adivina
por nombre de archivo). Cache en memoria del proceso.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["fonts"])

_CACHE: list[dict[str, Any]] | None = None

BASE_FONTS = [
    {"family": "system-ui", "origin": "base"},
    {"family": "Arial", "origin": "base"},
    {"family": "Helvetica", "origin": "base"},
    {"family": "Verdana", "origin": "base"},
    {"family": "Tahoma", "origin": "base"},
    {"family": "Trebuchet MS", "origin": "base"},
    {"family": "Times New Roman", "origin": "base"},
    {"family": "Georgia", "origin": "base"},
    {"family": "Courier New", "origin": "base"},
    {"family": "Consolas", "origin": "base"},
]


def _font_dirs() -> list[Path]:
    dirs = [Path("C:/Windows/Fonts")]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    return [d for d in dirs if d.is_dir()]


def _family_of(path: Path) -> str | None:
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(str(path), lazy=True, fontNumber=0)
        name = font["name"]
        for name_id in (16, 1):  # 16: familia tipográfica; 1: familia
            record = name.getDebugName(name_id)
            if record:
                return record.strip()
    except Exception:
        return None
    return None


@router.get("/fonts")
def list_fonts() -> dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return {"fonts": _CACHE, "count": len(_CACHE), "cached": True}
    families: dict[str, int] = {}
    for d in _font_dirs():
        for f in d.iterdir():
            if f.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            family = _family_of(f)
            if family:
                families[family] = families.get(family, 0) + 1
    out = BASE_FONTS + [
        {"family": fam, "origin": "sistema", "files": count}
        for fam, count in sorted(families.items(), key=lambda kv: kv[0].lower())
        if fam not in {b["family"] for b in BASE_FONTS}
    ]
    _CACHE = out
    return {"fonts": out, "count": len(out), "cached": False}
