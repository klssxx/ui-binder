# DECISIONS — registro de decisiones arquitectónicas

## D1 — Shell de escritorio: pywebview primero, Tauri listo pero bloqueado

- **Problem**: la directiva prioriza Tauri; la máquina tiene Rust 1.97 pero
  la build muere en `link.exe` (falta la workload "C++ Build Tools" de VS;
  `vswhere` no encuentra `VC.Tools.x86.x64`).
- **Options**: (a) instalar VS Build Tools (multi-GB, cambio de sistema, sin
  autorización); (b) entregar solo web dev; (c) empaquetar el mismo
  frontend+backend con pywebview/WebView2 + PyInstaller (Ruta A del playbook
  win-app-build).
- **Decision**: (c). `scripts/desktop_app.py` + `scripts/uibinder.spec`
  producen `dist/UIBinder/` portable; `apps/desktop/src-tauri/` queda completo
  (conf, iconos, Rust) para activarse cuando se instalen las Build Tools
  (`npm run tauri -w apps/desktop`).
- **Trade-offs**: sin instalador NSIS/MSI por ahora; a cambio, exe verificado
  hoy. Evidencia: smoke de la GUI real exit 0.

## D2 — Visión en dos niveles de tinta (strong/weak)

- **Problem**: un solo umbral fusiona paneles sutiles con botones/texto
  (mega-blobs) y el antialiasing de divisores conecta navbar+sidebar en un
  blob de pantalla completa.
- **Options**: umbral único con morfología agresiva; jerarquía strong(>45)/
  weak(>12) con carve-out de strong, erosión 2×2 y perfiles de banda para
  navbar/sidebar.
- **Decision**: jerarquía + perfiles estructurales. 21 componentes correctos
  en el golden (botones/input/heading/chart/navbar/sidebar/panel/textos).
- **Trade-offs**: dos pases de morfología; determinista y testeado.

## D3 — AST JS/TS vía bridge Node (Babel) con fallback regex marcado

- **Problem**: parsear TSX desde Python sin dependencias pesadas.
- **Decision**: `packages/project-analyzer/analyze.mjs` (@babel/parser +
  traverse) invocado por lotes; si Node o sus deps faltan, `js_fallback`
  (regex) marca `fallback: true` y confianza ≤ 0.35 — degradación visible,
  nunca silenciosa.

## D4 — Parámetros de modelo Pydantic expandidos a campos

- **Problem**: `api_generate(request: GenerateRequest)` hacía que el binder
  validara contra el input "request" y marcara BROKEN bindings correctos.
- **Decision**: `capability_builder._expand_params` sustituye el parámetro
  por los campos del modelo (prompt, mode…) con required por defecto.

## D5 — Matcher determinista con stems de prefijo-5

- **Problem**: botones ES («Generar») contra rutas EN (/api/generate) no
  solapan tokens exactos.
- **Decision**: señales léxico verbal ES/EN + equivalencia stem por prefijo
  de 5 caracteres, pesos fijos documentados en docs/BINDING_MODEL.md.
  Sin ML; determinismo testeado.

## D6 — Persistencia: documentos JSON versionados sobre SQLite

- **Decision**: SQL solo para entidades relacionales (workspaces, images,
  bindings, capabilities, runs); el AST vive como documento JSON versionado
  por escritura con validación pydantic en la frontera. Migraciones
  versionadas en `backend/persistence/db.py`.

## D7 — Undo/redo con commit único al soltar

- **Decision**: el drag/resize vive en estado local del canvas y muta el AST
  una sola vez en pointer-up; la historia queda limpia (1 paso por gesto).

## D8 — Export siempre a directorio nuevo

- **Decision**: `is_safe_export_target` exige destino vacío y no solapado
  con el proyecto importado; dry-run (`export-plan`) disponible antes de
  escribir. Cumple NON-DESTRUCTIVE FIRST (§66).
