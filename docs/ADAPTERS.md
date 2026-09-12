# ADAPTERS

## Contrato

Cada adapter (`adapters/base.py`) declara:

```python
class Adapter(ABC):
    name: str
    def detect(self, path) -> bool          # ¿aplica a este proyecto?
    def inspect(self, path) -> dict         # resumen del stack
    def capabilities(self, path) -> list    # capabilities que aporta
    def bindings_compat(self, path) -> dict # eventos/estado/estilo de llamada
    def validate(self, path) -> list[str]   # problemas de sanidad
```

Registro tipo plugin (`adapters/__init__.py::register`): añadir Vue, Svelte,
Angular, PySide6, Avalonia o Flutter es implementar la clase y registrarla —
el core (analyzer/binder/export) no cambia.

## Implementaciones actuales (todas reales)

| Adapter | detect | aportes |
|---|---|---|
| `python` | `**/*.py` | funciones/clases/métodos vía `ast` |
| `fastapi` | requirements/pyproject con fastapi o `from fastapi` | rutas con modelos expandidos |
| `react` | package.json con react o `*.tsx/*.jsx` | componentes, hooks, handlers, fetch (Babel AST) |
| `vite` | `vite.config.*` o dependencia vite | scripts, entrypoints, validaciones |
| `tauri` | `src-tauri/tauri.conf.json` | producto, identificador, validaciones |

`adapters_for(path)` devuelve los que detectan el proyecto; `import-project`
los usa para el resumen inicial y `analyze-project` consume el grafo unificado.
