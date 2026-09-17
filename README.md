# UI BINDER — UI RECONSTRUCTOR + SMART APPLICATION BINDER

Herramienta de escritorio **local-first** que reconstruye una interfaz desde una
captura, la convierte en componentes editables, analiza proyectos existentes
(read-only), detecta sus **capabilities**, sugiere **bindings** visuales y
verifica que la UI reconstruida no pierda funcionalidad.

```
IMAGEN → ESTRUCTURA → COMPONENTES → EDICIÓN → ANÁLISIS DEL PROYECTO
       → BINDINGS → VERIFICACIÓN → APLICACIÓN FUNCIONAL
```

## Qué es

- **Import** de screenshots (PNG/JPEG/WEBP) por selector o drag&drop.
- **Vision analyzer heurístico local** (OpenCV; sin OCR, sin red): regiones,
  paneles, navbar/sidebar, botones, inputs con borde, textos, charts, dividers,
  con confianza por detección y jerarquía por contención.
- **Editor visual** profesional: árbol de componentes, canvas con
  seleccionar/mover/redimensionar/editar texto inline, inspector completo
  (geometría, estilos, eventos, metadata), undo/redo, snapshots.
- **Project analyzer**: Python vía `ast` real; JS/TS/TSX vía AST Babel (Node);
  fallback regex marcado con confianza baja. Detecta funciones, clases, rutas
  FastAPI (con modelos Pydantic expandidos a campos), componentes React, hooks,
  handlers, fetch calls y construye el **capability graph**.
- **Smart Binder** determinista y auditable: sugiere conexiones
  componente↔capability con score y rationale (léxico verbal ES/EN, stems por
  prefijo, prior por tipo, cola de ruta).
- **Orphan detector**: BOUND / UNBOUND / BROKEN / UNKNOWN / LEGACY —
  *ninguna capability se elimina nunca automáticamente*.
- **Visual diff**: pixel diff + SSIM + SSIM de bordes + diff por regiones +
  deltas geométricos → **Visual Fidelity Score** (independiente del
  **Functional Coverage Score**).
- **Export seguro**: genera un proyecto React/Vite/TS **o PySide6/Widgets**
  nuevo en un directorio vacío; jamás toca el proyecto importado; los bindings
  CONFIRMED contra rutas se convierten en llamadas fetch reales (React) o
  signal/slot connections (PySide6).

## Instalación

Requisitos: Python 3.11+ y Node 18+.

```bash
# backend
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.txt

# frontend + analizador AST (workspaces npm)
npm install
npm run build            # compila apps/desktop/dist
```

## Ejecución

```bash
# desarrollo (backend 8765 + vite 5173, con recarga)
python scripts/dev.py

# app de escritorio desde origen (WebView2 + backend en un proceso)
python scripts/desktop_app.py

# exe portable (PyInstaller) → dist/UIBinder/UIBinder.exe
.venv/Scripts/python.exe -m PyInstaller scripts/uibinder.spec --noconfirm --workpath build/pyinstaller

# tests
.venv/Scripts/python.exe -m pytest tests            # backend (189 tests)
npm test                                             # frontend (vitest, 6 tests)
```

## Tests

```
Backend:  189 passed
Frontend: 6 passed
Total:    195 passed
```

## Flujo básico (Quick Start)

1. Abrir UI Binder → **NEW WORKSPACE**.
2. **IMPORT IMAGE** (screenshot) → **ANALYZE UI**.
3. Editar componentes/textos en el canvas e inspector (Ctrl+Z/Y, Ctrl+S).
4. **IMPORT PROJECT** (ruta del proyecto; se abre READ-ONLY) →
   **ANALYZE PROJECT**.
5. Seleccionar un botón → inspector → **SMART BIND** → sugerencias con score →
   **Confirmar** → editar mappings (inputs/outputs/loading/error).
6. **VERIFY** → orphan detector + cobertura funcional + bindings rotos.
7. **PREVIEW** (Design / Connected).
8. **EXPORT** a un directorio nuevo y vacío (dry-run disponible:
   `GET /api/workspaces/{id}/export-plan`). Selecciona target:
   **React / Vite / TypeScript** o **PySide6 / Widgets**.

## Arquitectura

Ver [ARCHITECTURE.md](ARCHITECTURE.md). Resumen de capas:

| Capa | Ubicación |
|---|---|
| UI (React/TS/Vite) | `apps/desktop/src` |
| API (FastAPI) | `backend/api` |
| Vision + tokens | `backend/vision` |
| Analizadores (ast/Babel) | `backend/analyzer` + `packages/project-analyzer` |
| Binder + verificación | `backend/bindings`, `backend/verification` |
| Diff visual | `backend/diff` |
| Persistencia (SQLite) | `backend/persistence` |
| Export + adapters | `backend/export`, `adapters/` |
| Shell desktop | `scripts/desktop_app.py` (pywebview) + `apps/desktop/src-tauri` |

## Seguridad

- Proyectos importados **read-only** por contrato; cualquier escritura exige
  export a directorio nuevo (validado, no solapado con el origen).
- No se ejecuta código de proyectos importados: solo análisis estático.
- API keys solo por variables de entorno (`.env.example`); nunca se persisten
  ni loguean (redacción automática de secretos en logs).
- Proveedores cloud opcionales y claramente marcados (la nota de análisis
  avisa cuando una imagen se envía a un endpoint externo).
- Funciona 100% offline (provider heurístico local).
- Exportación **transactional**: staging directory + promote atómico.
- Validación de paths: rechaza symlinks, directorios del sistema, raíces de unidad.

## Limitaciones conocidas (v0.1.0)

- La visión heurística **no tiene OCR**: los textos detectados son posiciones
  inferidas; el texto real se edita a mano en el inspector (por diseño honesto).
- Trace mode: almacenamiento/consulta reales, pero la instrumentación automática
  del navegador (Playwright) no está implementada.
- Connected preview: renderiza y anota bindings; las llamadas en vivo requieren
  que el proyecto importado esté corriendo en su puerto.
- Instalador Tauri bloqueado por falta de "C++ Build Tools" de Visual Studio
  en esta máquina (ver docs/DECISIONS.md y FEATURE REGISTRY); el ejecutable
  portable se entrega vía PyInstaller (WebView2).
- PySide6 runtime smoke test no ejecutable en venv controlado (PySide6 no instalado).
  Tests de compilación, sintaxis y codegen pasan.

## Versiones

- App: `0.1.0` · UI schema: `1` · Migraciones DB: `1` · Export targets: `react-vite-ts`, `pyside6-widgets`
