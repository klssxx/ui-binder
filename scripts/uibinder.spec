# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for UI Binder (Ruta A del playbook win-app-build).
# Build:  .venv/Scripts/python.exe -m PyInstaller scripts/uibinder.spec --noconfirm
# Output: dist/UIBinder/  (carpeta portable)

import os
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent  # repo root (spec lives in scripts/)
WEBDIST = ROOT / "apps" / "desktop" / "dist"

if not (WEBDIST / "index.html").is_file():
    raise SystemExit("apps/desktop/dist missing — run `npm run build` in apps/desktop first")

a = Analysis(
    [str(ROOT / "scripts" / "desktop_app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(WEBDIST), "webdist")],
    hiddenimports=[
        "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
        "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan", "uvicorn.lifespan.on",
        "backend", "backend.api", "backend.schema", "backend.vision", "backend.analyzer",
        "backend.bindings", "backend.verification", "backend.persistence",
        "backend.export", "backend.diff", "backend.security", "backend.tracing",
        "adapters",
        "webview.platforms.edgechromium", "webview.platforms.winforms",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UIBinder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "apps" / "desktop" / "src-tauri" / "icons" / "icon.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="UIBinder",
)
