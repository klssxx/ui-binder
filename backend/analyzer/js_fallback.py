"""Regex fallback scanner — LOW confidence, used only when the Node AST bridge fails.

The directive forbids relying *solely* on regex: this module exists so the
pipeline degrades visibly instead of silently. Every capability it produces is
marked confidence<=0.35 and metadata.fallback=true.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_FN_RE = re.compile(r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)")
_ARROW_RE = re.compile(r"(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(")
_EXPORT_RE = re.compile(r"export\s+(?:const|function|class|default)\s+([A-Za-z_$][\w$]*)")
_FETCH_RE = re.compile(r"fetch\(\s*[\"'`]([^\"'`]+)[\"'`]")
_COMP_RE = re.compile(r"(?:export\s+)?function\s+([A-Z][\w$]*)")


def regex_scan(paths: list[Path], reason: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for p in paths:
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ext = p.suffix.lower().lstrip(".")
        names = sorted(set(_FN_RE.findall(source)) | set(_ARROW_RE.findall(source)))
        results.append({
            "file": str(p),
            "language": "ts" if ext.startswith("ts") else "js",
            "fallback": True,
            "fallback_reason": reason,
            "functions": [{"name": n, "line": 0, "params": [], "async": False, "doc": ""} for n in names],
            "classes": [],
            "reactComponents": [{"name": n, "line": 0, "props": [], "doc": ""} for n in sorted(set(_COMP_RE.findall(source)))],
            "customHooks": [],
            "hooksUsed": [],
            "eventHandlers": [],
            "fetchCalls": [{"url": u, "method": "GET", "line": 0} for u in sorted(set(_FETCH_RE.findall(source)))],
            "routes": [],
            "exports": sorted(set(_EXPORT_RE.findall(source))),
        })
    return results
