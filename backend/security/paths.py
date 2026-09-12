"""Filesystem safety helpers.

Imported projects are READ-ONLY by contract: every read goes through
``ensure_inside`` and no write API ever receives an imported project path.
"""
from __future__ import annotations

from pathlib import Path, PurePath

_FORBIDDEN_PROJECT_PARENTS = [
    "c:\\windows",
    "c:\\program files",
    "c:\\program files (x86)",
    "c:\\programdata",
]


def ensure_inside(root: Path, candidate: Path) -> Path:
    """Resolve ``candidate`` and assert it stays under ``root``. Raises ValueError."""
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise ValueError(f"Path escapes allowed root: {candidate} (root: {root})")
    return candidate_resolved


def is_safe_project_path(path_str: str) -> tuple[bool, str]:
    """Validate a user-supplied project directory for READ-ONLY import."""
    if not path_str or not path_str.strip():
        return False, "Empty path."
    p = Path(path_str.strip().strip('"'))
    if not p.exists():
        return False, f"Path does not exist: {p}"
    if not p.is_dir():
        return False, f"Path is not a directory: {p}"
    resolved = str(p.resolve()).lower()
    for forbidden in _FORBIDDEN_PROJECT_PARENTS:
        if resolved == forbidden or resolved.startswith(forbidden + "\\"):
            return False, "System directories cannot be imported."
    # Windows drive roots like C:\ are too broad to index meaningfully.
    if p.expanduser().absolute().resolve().parent == p.expanduser().absolute().resolve():
        return False, "Drive roots cannot be imported; pick a project folder."
    return True, "ok"


def is_safe_export_target(target: Path, source_project: Path | None) -> tuple[bool, str]:
    """Export must write to a fresh directory, never into the imported project."""
    if not target.is_absolute():
        return False, "Export target must be an absolute path."
    if source_project is not None:
        src = source_project.resolve()
        tgt = target.resolve()
        if tgt == src or src in tgt.parents or tgt in src.parents:
            return False, "Export target must not overlap the imported project."
    if target.exists():
        if not target.is_dir():
            return False, "Export target exists and is not a directory."
        if any(target.iterdir()):
            return False, "Export target directory is not empty."
    parent = target.parent
    if not parent.exists():
        return False, f"Export target parent does not exist: {parent}"
    return True, "ok"
