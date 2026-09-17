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
        return False, "Ruta vacía."
    p = Path(path_str.strip().strip('"'))
    if not p.exists():
        return False, f"La ruta no existe: {p}"
    if not p.is_dir():
        return False, f"La ruta no es un directorio: {p}"
    resolved = str(p.resolve()).lower()
    for forbidden in _FORBIDDEN_PROJECT_PARENTS:
        if resolved == forbidden or resolved.startswith(forbidden + "\\"):
            return False, "No se pueden importar directorios del sistema."
    # Windows drive roots like C:\ are too broad to index meaningfully.
    if p.expanduser().absolute().resolve().parent == p.expanduser().absolute().resolve():
        return False, "No se puede importar una raíz de unidad; elige una carpeta de proyecto."
    return True, "ok"


def is_safe_export_target(target: Path, source_project: Path | None) -> tuple[bool, str]:
    """Export must write to a fresh directory, never into the imported project."""
    if not target.is_absolute():
        return False, "El destino de exportación debe ser una ruta absoluta."
    # Security: never export to a symlink (can point anywhere)
    if target.is_symlink():
        return False, "El destino de exportación no puede ser un enlace simbólico."
    # P0: nunca exportar a directorios del sistema ni a raíces de unidad.
    resolved = str(target.resolve()).lower()
    for forbidden in _FORBIDDEN_PROJECT_PARENTS:
        if resolved == forbidden or resolved.startswith(forbidden + "\\"):
            return False, "No se puede exportar a un directorio del sistema."
    if target.parent == target:
        return False, "No se puede exportar a una raíz de unidad; elige una carpeta concreta."
    if source_project is not None:
        src = source_project.resolve()
        tgt = target.resolve()
        if tgt == src or src in tgt.parents or tgt in src.parents:
            return False, "El destino de exportación no puede solaparse con el proyecto importado."
    if target.exists():
        if not target.is_dir():
            return False, "El destino de exportación existe y no es un directorio."
        if any(target.iterdir()):
            return False, "El directorio de destino de la exportación no está vacío."
    parent = target.parent
    if not parent.exists():
        return False, f"El directorio padre del destino no existe: {parent}"
    return True, "ok"
