# UI SCHEMA — v1

Representación intermedia canónica de la interfaz reconstruida. Todo lo
persistido pasa por este schema; nada depende de clases internas sin versión.

## UIDocument

```jsonc
{
  "ui_schema_version": 1,
  "screen": { "id": "screen", "width": 1280, "height": 800,
              "background": "#101216", "preset": null },
  "components": [ /* Component[] */ ],
  "metadata": { "provider": "heuristic" }
}
```

`screen` es la raíz **pseudo-componente** (`id = "screen"`, no aparece en
`components`). `preset` recuerda el modo responsivo del canvas
(desktop-1920, laptop, tablet, mobile, custom).

## Component

| Campo | Tipo | Notas |
|---|---|---|
| `id` | str | único; reservado el prefijo canónico `component_NNNN` para visión |
| `type` | enum | 22 tipos: screen, container, panel, card, text, heading, button, input, textarea, select, checkbox, radio, image, icon, table, chart, tabs, sidebar, navbar, modal, divider, custom |
| `name` | str | editable, semilla del scoring del binder |
| `parent_id` | str\|null | `screen` o el id de otro componente |
| `children` | [str] | orden = z-order dentro del padre |
| `bbox` | {x,y,width,height} | coordenadas absolutas en píxeles del screen |
| `text` | str\|null | solo portadores de texto |
| `styles` | dict | background, color, fontSize, radius, padding, margin, border, shadow, opacity… |
| `states` | dict | estados declarados (loading, error…) |
| `events` | dict | espejo de bindings confirmados, p.ej. `{"onClick": "bind_x"}` |
| `bindings` | [str] | ids de bindings que apuntan a este componente |
| `metadata` | dict | `confidence` (0-1), `source` (heuristic/manual/remote), extras |

## Invariantes (validadas en cada PUT)

1. ids únicos; `screen` reservado.
2. `parent_id` nulo, `screen`, o id existente (nunca de sí mismo).
3. todo hijo listado en `children` del padre (reciprocidad y orden).
4. bbox con width/height > 0.

`UIDocument.validate_structure()` devuelve problemas legibles; la API
responde 422 con la lista.

## CustomComponent

Todo lo no clasificable se conserva como `type: "custom"` con bbox y metadata
— **nunca se descarta**. El inspector permite reclasificar manualmente.

## Versionado y migraciones

- `ui_schema_version` viaja dentro del documento.
- El wrapper persistido es `{ui, tokens, design_md}`; `tokens` (DesignTokens)
  y `design_md` se preservan entre PUTs del editor.
- DB migraciones independientes (`schema_migrations`), hoy: v1.
