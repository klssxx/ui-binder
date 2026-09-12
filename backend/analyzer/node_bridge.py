"""Node bridge — runs packages/project-analyzer/analyze.mjs for real AST analysis.

Falls back to a low-confidence regex scanner when Node or its dependencies are
unavailable. The fallback is clearly flagged in capability confidence.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from backend import config

_SCRIPT = config.REPO_ROOT / "packages" / "project-analyzer" / "analyze.mjs"

_node_cache: str | None = None


def node_available() -> bool:
    global _node_cache
    if _node_cache is None:
        _node_cache = shutil.which("node") or ""
    return bool(_node_cache)


def analyze_js_files(paths: list[Path]) -> list[dict[str, Any]]:
    """Analyze JS/TS files with Babel AST via the Node analyzer package."""
    if not paths:
        return []
    if not node_available():
        return _fallback(paths, reason="node-not-found")
    cmd = [node_available() and _node_cache or "node", str(_SCRIPT), *[str(p) for p in paths]]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=90, cwd=str(config.REPO_ROOT),
            encoding="utf-8", errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fallback(paths, reason=f"node-bridge-error:{exc.__class__.__name__}")
    if proc.returncode != 0:
        return _fallback(paths, reason=f"node-exit-{proc.returncode}:{proc.stderr.strip()[:200]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _fallback(paths, reason="node-output-not-json")


def _fallback(paths: list[Path], reason: str) -> list[dict[str, Any]]:
    from .js_fallback import regex_scan

    print(f"[analyzer] node bridge unavailable ({reason}); regex fallback engaged", file=sys.stderr)
    return regex_scan(paths, reason=reason)
