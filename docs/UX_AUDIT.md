# UX AUDIT — F8 baseline (2026-09-13)

Top fricciones de la v0.2, clasificadas. Métrica: acciones tras seleccionar elemento.

| # | Problema | Actual | Propuesto | Clicks actual→objetivo | Severidad | Riesgo |
|---|---|---|---|---|---|---|
| 1 | Dock de diagnóstico (250px) ocupa pantalla siempre aunque el 90% del tiempo no se usa | Dock fijo abajo | Colapsable con memoria, barra fina "Diagnóstico ▴" | 0→0 (gana espacio) | Critical | Bajo |
| 2 | Inspector muestra TODO siempre (ruido: metadatos, eventos crudos junto a color/fuente) | 8 secciones planas | Pestañas Diseño/Acción/Datos según selección | 0→0 (menos ruido) | Critical | Bajo |
| 3 | Toolbar con 9 botones permanentes (verificar/exportar son de flujo largo) | 9 botones | 6 primarios + menú ⋯ (Verificar, Exportar, Snapshot, Workspaces) | 0→1 para secundarios | High | Bajo |
| 4 | Cambiar de herramienta requiere ir a la paleta flotante | click en icono | Atajos V/R/L/P/E + tooltip con la tecla | 1→0 | High | Bajo |
| 5 | Smart Bind enterrado al final del inspector | scroll largo | Pestaña "Acción" primera clase | ~2→0 (pestaña) | High | Bajo |
| 6 | Previsualizar requiere botón superior | botón | mantener + shortcut Ctrl+P? (posible conflicto imprimir; usar solo botón) | — | Medium | — |
| 7 | Sin multi-selección (shift/marquee) — bloquea align/distribute | — | F9 | — | High | Medio |
| 8 | Sin snapping/guías — posicionar a ojo | — | F9 | — | High | Medio |
| 9 | Sin auto layout — espaciado manual | — | F10 | — | Critical | Alto |
| 10 | Sin biblioteca de componentes — recréalos a mano | — | F11 | — | High | Medio |
| 11 | Design tokens inferidos no editables desde UI | solo DESIGN.md generado | F12 | — | Medium | Bajo |
| 12 | Import requiere diálogo de archivo | selector | Ctrl+V + drag&drop (F13) | 3→1 | High | Medio |
| 13 | Sin menú contextual (clic derecho) | — | F9/F14 | — | Medium | Bajo |
| 14 | Onboarding inexistente (pantalla en blanco para usuario nuevo) | — | F16 | — | Medium | Bajo |
| 15 | Errores tostados desaparecen a los 6s sin historial | toast | mantener + copia en Logs (ya existe) | — | Low | — |
| 16 | Estado de guardado no visible salvo "● sin guardar" | parcial | "Guardando…/Guardado" discreto en StatusBar (F16) | — | Low | Bajo |
| 17 | Align/distribute inexistentes | — | F9 (tras multi-select) | — | High | Medio |
| 18 | Specs (F1) desconectadas del flujo diario (dock escondido tras el fix del bucle) | pestaña SPEC | mantener en Diagnóstico + acceso desde toolbar? | — | Medium | Bajo |
| 19 | Confidence bands (H/M/L/F) sin leyenda | tooltip largo | leyenda corta en ayudas (F16) | — | Low | — |
| 20 | Selección múltiple de capas en árbol (shift/ctrl) | — | F9 | — | Medium | Bajo |

Journeys (baseline aproximada, v0.2):
- A (captura→editar texto): 4 acciones humanas · B (frame→botón→estilo): 5 · C (multiselec→autolayout): N/A hoy · D (componente): N/A hoy · E (bind): 3-4 · F (preview responsive): 3 · G (diff): 4 + interpretar métricas · H (export): 3.
- Objetivos v0.3: A≤2, B≤3, E≤3 tras seleccionar, resto documentado por fase.

Decisiones F8 (formato §48):
- Problema: ruido permanente de diagnóstico + inspector plano.
- Alternativas: (a) paneles flotantes, (b) pestañas + colapso, (c) modo zen.
- Decisión: (b).
- Por qué reduce fricción: canvas gana ~250px, la acción (Smart Bind) pasa a pestaña de primer nivel, los secundarios salen de la toolbar.
- Riesgo: descubrimiento de funciones ocultas → mitigado con etiquetas visibles (Diagnóstico ▴, ⋯) y atajos.
- Verificación: build + smoke visual + suites.
