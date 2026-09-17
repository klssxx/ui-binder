"""Project scanner — walk an imported project READ-ONLY and index its shape."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from backend import config

_SOURCE_EXT = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".css": "css", ".html": "html", ".json": "json", ".rs": "rust", ".md": "markdown",
}


def scan_project(root: Path) -> dict[str, Any]:
    """Index a project directory. Never writes, never executes anything."""
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"No es un directorio: {root}")

    files: list[dict[str, Any]] = []
    languages: dict[str, int] = {}
    count = 0
    for path in sorted(root.rglob("*")):
        if count > config.SCAN_MAX_FILES:
            break
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            if path.name in config.SCAN_IGNORED_DIRS:
                continue
            continue
        parts = set(rel.split("/"))
        if parts & config.SCAN_IGNORED_DIRS:
            continue
        if path.stat().st_size > config.SCAN_MAX_FILE_BYTES:
            continue
        count += 1
        lang = _SOURCE_EXT.get(path.suffix.lower(), "")
        if lang:
            languages[lang] = languages.get(lang, 0) + 1
            files.append({"path": path, "rel_path": rel, "language": lang})

    manifests = _read_manifests(root)
    frameworks = _detect_frameworks(manifests, files, root)
    entrypoints = _detect_entrypoints(root, manifests)

    return {
        "root": str(root),
        "file_count": count,
        "source_files": [{"rel_path": f["rel_path"], "language": f["language"]} for f in files],
        "languages": sorted(languages, key=lambda k: -languages[k]),
        "manifests": manifests,
        "frameworks": frameworks,
        "entrypoints": entrypoints,
    }


def _read_manifests(root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    # root + one level deep (monorepo layouts: backend/ + frontend/)
    bases = [root, *sorted(d for d in root.iterdir() if d.is_dir()
                          and d.name not in config.SCAN_IGNORED_DIRS and not d.name.startswith("."))][:8]
    for base in bases:
        prefix = "" if base == root else base.name + "/"
        pkg = base / "package.json"
        if pkg.is_file():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                out.append({
                    "type": "package.json", "path": f"{prefix}package.json",
                    "name": data.get("name", ""),
                    "dependencies": sorted(set(list(data.get("dependencies", {})) + list(data.get("devDependencies", {})))),
                    "scripts": data.get("scripts", {}),
                })
            except (json.JSONDecodeError, OSError):
                out.append({"type": "package.json", "path": f"{prefix}package.json", "error": "unreadable"})
        for req in sorted(base.glob("requirements*.txt")):
            try:
                deps = [l.strip() for l in req.read_text(encoding="utf-8").splitlines()
                        if l.strip() and not l.startswith("#")]
                out.append({"type": "requirements", "path": f"{prefix}{req.name}",
                            "dependencies": deps})
            except OSError:
                pass
        pyproject = base / "pyproject.toml"
        if pyproject.is_file():
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                project = data.get("project", {})
                out.append({
                    "type": "pyproject.toml", "path": f"{prefix}pyproject.toml",
                    "name": project.get("name", ""),
                    "dependencies": project.get("dependencies", []),
                })
            except (tomllib.TOMLDecodeError, OSError):
                out.append({"type": "pyproject.toml", "path": f"{prefix}pyproject.toml", "error": "unreadable"})
    tauri_conf = root / "src-tauri" / "tauri.conf.json"
    if tauri_conf.is_file():
        try:
            data = json.loads(tauri_conf.read_text(encoding="utf-8"))
            out.append({"type": "tauri.conf.json", "path": "src-tauri/tauri.conf.json",
                        "productName": data.get("productName", ""),
                        "identifier": data.get("identifier", "")})
        except (json.JSONDecodeError, OSError):
            out.append({"type": "tauri.conf.json", "path": "src-tauri/tauri.conf.json", "error": "unreadable"})
    return out


def _detect_frameworks(manifests: list[dict[str, Any]], files: list[dict[str, Any]],
                       root: Path) -> list[str]:
    found: set[str] = set()
    for m in manifests:
        deps = m.get("dependencies", [])
        if "react" in deps:
            found.add("react")
        if "vite" in deps:
            found.add("vite")
        if "@tauri-apps/api" in deps:
            found.add("tauri")
        if "vue" in deps:
            found.add("vue")
        if "svelte" in deps:
            found.add("svelte")
        if "next" in deps:
            found.add("next")
        for dep in deps:
            if dep.lower().startswith("fastapi") or dep.lower().startswith("uvicorn"):
                found.add("fastapi")
    if any(m.get("type") == "tauri.conf.json" for m in manifests):
        found.add("tauri")
    if any(m.get("type") == "requirements" for m in manifests):
        for m in manifests:
            if m.get("type") == "requirements" and any(
                d.lower().startswith("fastapi") for d in m.get("dependencies", [])
            ):
                found.add("fastapi")
    rels = {f["rel_path"] for f in files}
    if "src-tauri/tauri.conf.json" in rels or (root / "src-tauri").is_dir():
        found.add("tauri")
    if any(r.startswith("vite.config") for r in rels):
        found.add("vite")
    # imports as fallback signal (subproject without its own manifest, e.g. monorepo samples)
    py_files = [f for f in files if f["language"] == "python"][:200]
    for f in py_files:
        try:
            head = f["path"].read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        if "fastapi" in head:
            found.add("fastapi")
    return sorted(found)


def _detect_entrypoints(root: Path, manifests: list[dict[str, Any]]) -> list[str]:
    entrypoints: list[str] = []
    candidates = [
        "index.html", "src/main.tsx", "src/main.jsx", "src/main.ts", "src/index.tsx",
        "src/index.jsx", "src/App.tsx", "src/App.jsx", "main.py", "app.py",
        "src/main.py", "backend/app.py", "src-tauri/tauri.conf.json",
        # one level deep (monorepo layouts)
        "frontend/index.html", "frontend/src/main.tsx", "frontend/src/App.tsx",
        "backend/main.py", "backend/app.py",
    ]
    for cand in candidates:
        if (root / cand).is_file():
            entrypoints.append(cand)
    for m in manifests:
        if m.get("type") == "package.json":
            scripts = m.get("scripts", {})
            if "dev" in scripts or "start" in scripts:
                entrypoints.append("package.json#scripts." + ("dev" if "dev" in scripts else "start"))
            if m.get("name"):
                entrypoints.append(f"package:{m['name']}")
    return sorted(set(entrypoints))
