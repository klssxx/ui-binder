# VERIFICATION

Dos scores independientes por diseño (directiva §28): una UI visualmente
perfecta con funcionalidad perdida es un FALLO.

## Visual Fidelity Score

`POST /api/workspaces/{id}/visual-diff` (multipart `rendered`):

```
100 × (0.5·SSIM + 0.3·(1 − pixel_diff) + 0.2·edge_SSIM)
```

- Imagen renderizada se reescala al tamaño de la referencia (se registra).
- `pixel_diff`: proporción de píxeles con diferencia > 25 (grises).
- `SSIM`: implementación propia (ventana gaussiana 11×11, C1/C2 estándar).
- `edge_SSIM`: SSIM sobre mapas Canny — proxy de alineación estructural.
- **Regiones**: diff por bbox de cada componente del AST (peores 10).
- **Geometría**: si se puede analizar el render, matching greedy por centro
  (mismo tipo, tolerancia 60 px) → deltas medios de posición y dimensión.

Historial en `GET /diffs`; el último score alimenta /verify y el status bar.

## Functional Coverage Score

`POST /api/workspaces/{id}/verify` ejecuta:

1. **verifier**: cada binding contra el AST y las capabilities actuales →
   BROKEN con problemas legibles (target inexistente, firma cambiada…).
2. **orphan detector**: clasificación BOUND/UNBOUND/BROKEN/UNKNOWN/LEGACY.
3. coverage = 100 × bound / capabilities_detected.

El reporte se persiste (`verification_runs`) y expone ambos scores por
separado (`scores.visual_fidelity`, `scores.functional_coverage`).

## Gates de regresión

- `tests/test_vision.py` — golden reference (invariantes de detección).
- `tests/test_diff.py` — métricas sobre imágenes sintéticas conocidas.
- `tests/test_orphan.py` — los 4 estados + política DELETE NOTHING.
- `tests/test_smoke_e2e.py` — flujo completo §50 (detect→edit→bind→verify→
  diff→export→reload), incluido que las UNBOUND esperadas siguen presentes.
