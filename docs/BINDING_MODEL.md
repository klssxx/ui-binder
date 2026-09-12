# BINDING MODEL

## Entidad Binding

| Campo | Descripción |
|---|---|
| `binding_id` | identificador estable |
| `component_id` | componente del AST (SOURCE) |
| `event` | onClick, onChange, onSubmit, onInput, onFocus, onBlur |
| `target_capability` | capability del grafo (TARGET) |
| `input_mapping` | [{source: componente/prop, target: parámetro}] |
| `output_mapping` | [{source: resultado/prop, target: componente/estado}] |
| `loading_mapping` | clave de estado UI durante la ejecución |
| `error_mapping` | clave de estado UI para errores |
| `transformations` | transforms nombradas (trim, number…) |
| `confidence` | 0-1 del matcher |
| `status` | SUGGESTED · CONFIRMED · BROKEN · UNKNOWN |
| `rationale` | señales que puntuaron (auditable) |

## SMART MATCH SCORING (determinista y documentado)

Señales y pesos (recorte final a [0, 0.98]; solo la confirmación del usuario
es un FACT):

| Señal | Peso | Rationale |
|---|---|---|
| match exacto de nombre normalizado | +0.55 | `exact name match: 'x' ≈ 'y'` |
| léxico verbal compartido ES/EN (generate/generar, evaluate/evaluar, save/guardar, load/cargar, export/exportar, search/buscar, run/ejecutar, compare/comparar, restore/restaurar, open/abrir, delete/eliminar, cancel, analyze, verify) | +0.14/verbo (máx 0.24) | `verb match: [...]` |
| par de tokens iguales | +0.25 | `token match: [...]` |
| pares stem-equivalentes (prefijo 5) | +0.12 | `stem-matched tokens: ['generar≈generate']` |
| solape tipo-Jaccard con stems | hasta +0.12 | (implícito) |
| >1 token del componente matchea | +0.05 | (implícito) |
| nombre de parámetro ≈ término del componente | +0.08 | `parameter name matches...` |
| prior por tipo (button→route/function/handler…) | +0.08 | `type prior: ...` |
| cola de ruta con tolerancia de stem (`generar` → `/api/generate`) | +0.18 | `route path tail matches: /generate` |
| capability LEGACY | score × 0.5 | advertido |

Umbral de sugerencia: < 0.15 no se ofrece. Sin ML: mismo input → mismo output
(test de determinismo en `tests/test_binder.py`).

## Estados y transiciones

- SUGGESTED → CONFIRMED (usuario) → BROKEN (verificador detecta target
  inexistente, componente fuera del AST, evento no soportado, o firma
  cambiada: inputs requeridos sin mapear / mapeos fuera de firma).
- UNKNOWN se reserva para detecciones de confianza < 0.4 en el orphan detector.

## Verificación (verifier.py)

Por binding: existencia del target, existencia del componente, evento
soportado, y **correspondencia de firma**: los inputs requeridos de la
capability deben estar mapeados y los mapeos deben existir en la firma.
Un output sin usar NO es error (es oportunidad).

## Orphan detector (DELETE NOTHING)

| Estado | Condición |
|---|---|
| BOUND | ≥1 binding CONFIRMED |
| UNBOUND | sin bindings |
| BROKEN | solo bindings rotos |
| UNKNOWN | confianza < 0.4 |
| LEGACY | marcado explícitamente por el usuario |

**Ninguna capability se elimina automáticamente**; marcar LEGACY o borrar
requiere acción explícita. Visual Fidelity y Functional Coverage son scores
independientes: una UI perfecta con funcionalidad perdida es un FALLO.
