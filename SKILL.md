---
name: ui-binder
description: Reconstrucción de UI desde screenshots, análisis read-only de proyectos, bindings visuales componente↔capability y verificación de fidelidad con UI Binder (INNOVATIONS/TOOLS/UI_BINDER).
---

# SKILL — UI BINDER

## Trigger

Activa este skill cuando el usuario pida: reconstruir una UI, importar un
screenshot y mapearlo, analizar un proyecto existente, crear/reparar un
binding, verificar fidelidad visual o funcional, añadir un adapter, o
realizar un export con UI Binder.

## Contexto del repositorio

- Raíz: `C:\Users\KLSX\Music\INNOVATIONS\TOOLS\UI_BINDER`
- Stack: FastAPI + SQLite (backend), React/TS/Vite (frontend), visión OpenCV,
  AST Python (`ast`) y JS/TS (Babel vía Node bridge), pywebview/PyInstaller
  (escritorio) + Tauri preparado (ver docs/DECISIONS.md D1).
- Datos de usuario: `%LOCALAPPDATA%/UIBinder` (override dev:
  `UIBINDER_DATA_DIR=./data`).

## Workflow

INSPECT → PLAN → MODIFY → TEST → VERIFY

1. **INSPECT**: lee `STATE.json`, `docs/FEATURES.md` y el módulo implicado
   antes de tocar nada. Todo afirma con `archivo:línea`.
2. **PLAN**: el cambio mínimo que funciona (Modify Before Duplicate).
3. **MODIFY**: respeta las capas (UI ≠ lógica; binding ≠ implementación).
4. **TEST**: `.venv/Scripts/python.exe -m pytest tests` (74 tests, basetemp
   local ya configurado) + `npm test` + `npm run build` si tocaste frontend.
5. **VERIFY**: para cambios de visión/regresión usa el golden
   (`samples/golden-reference`); para flujos, `tests/test_smoke_e2e.py`.

## Comandos

```bash
python scripts/dev.py                # backend + frontend (dev)
python scripts/desktop_app.py        # escritorio desde origen
.venv/Scripts/python.exe -m PyInstaller scripts/uibinder.spec --noconfirm --workpath build/pyinstaller
.venv/Scripts/python.exe -m pytest tests
python scripts/make_golden.py        # regenerar golden reference
```

## Invariants (nunca violar)

- **No destruir el proyecto fuente**: import es read-only; export siempre a
  directorio nuevo vacío (`is_safe_export_target`).
- **No eliminar funcionalidad silenciosamente**: DELETE NOTHING; las
  capabilities se clasifican (BOUND/UNBOUND/BROKEN/UNKNOWN/LEGACY) y LEGACY
  exige acción explícita del usuario.
- **No asumir que un elemento visual sustituye una capability existente**:
  la ausencia en la captura no significa ausencia en el producto.
- **No afirmar verificación sin evidencia**: comandos reales, exit codes y
  conteos; estados IMPLEMENTED/PARTIAL/NOT_IMPLEMENTED/VERIFIED honestos en
  docs/FEATURES.md.
- **Sin secretos**: keys solo por env; logs con redacción automática.
- **Confianza ≠ hecho**: FACT solo para ediciones manuales del usuario.

## Mapa rápido

| Tarea | Dónde |
|---|---|
| Añadir tipo de componente | backend/schema/ui_schema.py + apps/desktop/src/types.ts + tests de schema |
| Añadir provider de visión | backend/vision/ (register) |
| Añadir adapter (Vue, PySide6…) | adapters/ + register |
| Ajustar scoring del binder | backend/bindings/matcher.py + docs/BINDING_MODEL.md + tests/test_binder.py |
| Cambiar schema UI | subir `ui_schema_version` + migración si toca DB |
| Export a otro stack | backend/export/ |
