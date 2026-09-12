# FEATURE REGISTRY — v0.1.0

Estados honestos (§72): IMPLEMENTED / PARTIAL / NOT_IMPLEMENTED ·
verificación: VERIFIED (con prueba) / TESTED / MANUAL.

## IMPLEMENTED · VERIFIED (con evidencia en tests/)

| Feature | Implementación | Verificación |
|---|---|---|
| Workspace CRUD + snapshots + restore | backend/persistence/store.py, api/workspaces.py | test_persistence.py, test_api.py |
| Image import PNG/JPEG/WEBP + validación | api/images.py | test_api.py (inválida → 422) |
| Vision analyzer heurístico local | backend/vision/heuristic.py | test_vision.py (golden, 8 tests) |
| Design tokens + DESIGN.md | backend/vision/tokens_extract.py | test_vision.py::test_tokens_extracted |
| UI schema v1 + validación estructural | backend/schema/ui_schema.py | test_schema.py (9 tests) |
| Editor visual (árbol/canvas/inspector/undo/redo) | apps/desktop/src | MANUAL (arranque verificado; lógica pura en vitest) |
| Edición de texto (AST, no píxeles) | Canvas inline + PUT /ui | test_smoke_e2e.py paso 5-6 |
| ManualVisionProvider (empty doc) | backend/vision/manual.py | test_vision.py |
| OpenAICompatibleVisionProvider | backend/vision/remote.py | test_remote_provider.py (transport stubbeado; sin live API) |
| Project import READ-ONLY + validaciones | api/projects.py, security/paths.py | test_api.py (ruta inválida/sistema → 422) |
| Analyzer Python (rutas FastAPI + modelos) | backend/analyzer/python_analyzer.py | test_analyzers.py |
| Analyzer JS/TS (AST Babel real) | packages/project-analyzer + node_bridge | test_analyzers.py::test_node_bridge_real_ast |
| Fallback regex marcado (baja confianza) | backend/analyzer/js_fallback.py | test_analyzers.py |
| Capability graph (calls/handles/fetches/renders) | backend/analyzer/capability_builder.py | test_analyzers.py::test_capability_graph_end_to_end |
| Adapters (python/fastapi/react/vite/tauri) | adapters/ | test_analyzers.py (detect/inspect reales) |
| Smart Binder determinista + rationale | backend/bindings/matcher.py | test_binder.py (11 tests) |
| Binding CRUD + duplicados 409 + sync AST | api/bindings.py | test_api.py, test_smoke_e2e.py |
| Binding verifier (firma, targets, eventos) | backend/bindings/verifier.py | test_binder.py |
| Orphan detector (5 estados, DELETE NOTHING) | backend/verification/orphan.py | test_orphan.py |
| Visual diff (pixel+SSIM+edge+regiones+geometría) | backend/diff/visual.py | test_diff.py (6 tests) |
| Visual Fidelity Score + Functional Coverage | verification + status bar | test_diff.py, test_smoke_e2e.py |
| Export seguro React/Vite/TS (dry-run + apply) | backend/export/react_export.py | test_export.py + test_smoke_e2e.py |
| Búsqueda global (componentes/caps/rutas/bindings/files) | api/search.py | test_api.py::test_search_groups |
| Trace events (almacenar/listar) | api/trace.py | test_api.py::test_trace_and_logs_roundtrip |
| Logging estructurado + redacción de secretos | backend/logging_setup.py | test_api.py::test_logs_redact_secrets |
| Command palette (Ctrl+K) + shortcuts | apps/desktop/src/components/CommandPalette.tsx | MANUAL |
| Preview Design + Connected (anotado) | PreviewPane.tsx | MANUAL |
| App de escritorio (pywebview/WebView2) | scripts/desktop_app.py | smoke real exit 0 |
| Exe portable (PyInstaller) | scripts/uibinder.spec | smoke del exe exit 0 |
| Sample app E2E + golden reference | samples/ | test_smoke_e2e.py (16 pasos) |

## PARTIAL

| Feature | Estado exacto | Qué falta |
|---|---|---|
| Trace mode | Almacenamiento/consulta + registro desde preview implementados; TESTED | Instrumentación automática del navegador (Playwright): NOT_IMPLEMENTED |
| Connected preview | Renderiza y anota bindings; registra clicks a trace | Llamadas en vivo al proyecto importado corriendo |
| OCR / capa de texto extraída | No hay OCR: posiciones inferidas + edición manual (política honesta del heuristic) | Integración opcional de un provider OCR |
| Remote vision provider | IMPLEMENTED + TESTED con stub HTTP | Sin verificación contra API live (sin key en CI) |
| Auto-improve loop | diff + métricas + localización de errores | Propuesta/aplicación automática de correcciones |

## NOT_IMPLEMENTED (v0.1)

- Instalador Tauri (NSIS/MSI): **BLOQUEADO** por falta de "C++ Build Tools"
  de Visual Studio (link.exe falla; ver docs/DECISIONS.md D1). El proyecto
  src-tauri está completo y configrado para cuando se instale.
- Instrumentación Playwright del trace mode.
- Migraciones de schema UI > v1 (mecanismo listo, solo existe v1).
- Export a stacks distintos de React/Vite (contrato adapter listo).

## EVIDENCIA GLOBAL (última ejecución)

- `pytest tests` → **74 passed**, exit 0, 12.2 s.
- `vitest run` → **6 passed**, exit 0.
- `tsc -b --noEmit` → exit 0. `vite build` → exit 0 (45 módulos).
- `desktop_app.py` smoke (UIBINDER_SMOKE_EXIT_MS) → exit 0.
- `dist/UIBinder/UIBinder.exe` smoke → exit 0 (datos en %LOCALAPPDATA%/UIBinder).
