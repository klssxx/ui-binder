# ARCHITECTURE — UI Binder v0.1.0

## Principios (directiva §6)

- UI ≠ BUSINESS LOGIC: el frontend no conoce analizadores; el backend no conoce DOM.
- BINDING ≠ IMPLEMENTATION: el binding es un contrato de datos (JSON versionado),
  no código incrustado; el export lo *proyecta* a código.
- DESIGN ≠ PROJECT ANALYSIS: vision/ y analyzer/ son pipelines independientes que
  convergen en el binder.

## Vista general

```
┌────────────────────────── apps/desktop (React+TS+Vite) ─────────────────────────┐
│ Toolbar · TreePanel · Canvas (AST→nodos absolutos) · Inspector (SmartBind UI)   │
│ BottomDock (Trace|Bindings|Capabilities|Orphans|Diff|Logs) · StatusBar          │
│ CommandPalette (Ctrl+K) · SearchOverlay · PreviewPane · PromptModal             │
└───────────────┬───────────────────────────────────────────────┬────────────────┘
                │ fetch /api (JSON, schema v1)                  │
┌───────────────▼────────────── backend/api (FastAPI) ──────────▼────────────────┐
│ workspaces images ui projects capabilities bindings verification export search │
│ trace logs health                                                              │
├────────────────────────────────────────────────────────────────────────────────┤
│ vision/     heuristic (OpenCV, strong/weak ink) · manual · remote (opcional)   │
│             tokens_extract (kmeans + AST → design.tokens + DESIGN.md)          │
│ analyzer/   python_analyzer (ast) · node_bridge (Babel) · js_fallback (regex)  │
│             project_scanner (manifests 1 nivel) · capability_builder (grafo)   │
│ bindings/   matcher (scoring determinista) · verifier (validación vs AST/caps) │
│ verification/ orphan (BOUND/UNBOUND/BROKEN/UNKNOWN/LEGACY) + coverage          │
│ diff/       pixel + SSIM + edge-SSIM + regiones + geometría → fidelity score   │
│ export/     react_export (proyecto Vite autónomo; bindings→fetch)              │
│ adapters/   base + python + fastapi + react + vite + tauri (registry plugin)   │
│ persistence/ SQLite WAL + migraciones versionadas + WorkspaceStore             │
│ security/   rutas seguras (import read-only, export aislado)                   │
│ tracing/    recorder de eventos (parcial)                                      │
└────────────────────────────────────────────────────────────────────────────────┘
```

## Flujo de datos canónico

1. **Imagen** → `images` (sha256, dims) → referencia visual inmutable del workspace.
2. **analyze-ui** → `VisionProvider.analyze()` → `UIDocument` (schema v1) +
   `DesignTokens` + `DESIGN.md`. Persistido como wrapper `{ui, tokens, design_md}`
   en `ui_documents` (versionado por escritura).
3. **Editor** → PUT del documento completo; validación estructural server-side
   (ids únicos, padres existentes, reciprocidad children).
4. **import-project** (read-only) → `project_scanner` → manifests/frameworks/
   entrypoints/files → tabla `projects` + `project_files`.
5. **analyze-project** → analizadores por lenguaje → `CapabilityGraph`
   (nodos: function/method/class/route/component/hook/handler/service;
   aristas: calls/handles/fetches/renders) → tabla `capabilities`.
   Los params tipados con modelos Pydantic se **expanden a campos**.
6. **suggest-bindings** → `matcher` (puro, determinista) → sugerencias con
   score + rationale. **create binding** → validación (capability y componente
   existen; sin duplicados exactos) → tabla `bindings`; el AST refleja los
   bindings CONFIRMED en `component.events`.
7. **verify** → `verifier` + `orphan` → reporte persistido (`verification_runs`):
   broken/unbound/coverage + último Visual Fidelity.
8. **visual-diff** → render del usuario vs referencia → métricas + score
   (`visual_diffs`).
9. **export** → dry-run plan; apply valida destino vacío y aislado del
   proyecto importado; genera React/Vite/TS con runtime de bindings.

## Decisiones clave

- **SQLite con conexiones de vida corta + WAL**: simplicidad y lecturas
  concurrentes durante escrituras; todo el SQL vive en `WorkspaceStore`.
- **Documentos JSON versionados, no ORM**: el AST cambia más rápido que un
  esquema relacional; la versión va en cada fila y el schema pydantic valida.
- **Strong/weak ink en visión**: separa controles (contraste alto) de
  paneles sutiles; los perfiles de filas/columnas detectan navbar/sidebar
  sin fusionarse por antialiasing.
- **Bridge Node para AST JS/TS**: AST real (Babel) con degradación visible a
  regex de baja confianza — nunca silenciosa.
- **Undo/redo en frontend**: mutaciones locales + commit único al soltar el
  puntero; la historia no se contamina por frames de drag.

## Empaquetado

- **Ruta activa**: `scripts/desktop_app.py` (pywebview/WebView2 + uvicorn en
  hilo + StaticFiles del build) → PyInstaller onedir portable.
- **Ruta Tauri**: `apps/desktop/src-tauri` completo y configurado; su build
  requiere MSVC "C++ Build Tools" (bloqueo documentado en DECISIONS.md).
