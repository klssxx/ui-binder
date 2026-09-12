"""F4 frontend patch: fonts client + estilo tipográfico en canvas/preview + export."""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src"

# 1) cliente fonts()
p = BASE / "api" / "client.ts"
t = p.read_text(encoding="utf-8")
if "fonts:" not in t:
    t = t.replace('  ocrStatus:', '''  fonts: () => call<{ fonts: { family: string; origin: string }[]; count: number }>("/api/fonts"),

  ocrStatus:''')
    p.write_text(t, encoding="utf-8")
print("client ok")

# 2) Canvas: estilos tipográficos en el nodo
p = BASE / "components" / "Canvas.tsx"
t = p.read_text(encoding="utf-8")
t = t.replace("""  const styles: React.CSSProperties = {
    left: box.x, top: box.y, width: box.width, height: box.height,
    background: typeof c.styles.background === "string" ? c.styles.background : undefined,
    color: typeof c.styles.color === "string" ? c.styles.color : undefined,
    fontSize: c.styles.fontSize ? Number(c.styles.fontSize) : undefined,
    borderRadius: c.styles.radius ? Number(c.styles.radius) : undefined,
    opacity: c.styles.opacity != null ? Number(c.styles.opacity) : undefined,
  };""",
"""  const styles: React.CSSProperties = {
    left: box.x, top: box.y, width: box.width, height: box.height,
    background: typeof c.styles.background === "string" ? c.styles.background : undefined,
    color: typeof c.styles.color === "string" ? c.styles.color : undefined,
    fontSize: c.styles.fontSize ? Number(c.styles.fontSize) : undefined,
    fontFamily: typeof c.styles.fontFamily === "string" ? c.styles.fontFamily : undefined,
    fontWeight: c.styles.fontWeight != null ? Number(c.styles.fontWeight) : undefined,
    fontStyle: typeof c.styles.fontStyle === "string" ? c.styles.fontStyle : undefined,
    textAlign: typeof c.styles.textAlign === "string" ? c.styles.textAlign as React.CSSProperties["textAlign"] : undefined,
    textShadow: typeof c.styles.shadow === "string" ? c.styles.shadow : undefined,
    borderRadius: c.styles.radius ? Number(c.styles.radius) : undefined,
    opacity: c.styles.opacity != null ? Number(c.styles.opacity) : undefined,
  };""")
t = t.replace("""        c.text && <span className="node-text">{c.text}</span>""",
"""        c.text && (
          <span className="node-text" style={{
            width: "100%", display: "block", overflow: "hidden",
            textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>{c.text}</span>
        )""")
p.write_text(t, encoding="utf-8")
print("canvas ok")

# 3) Preview: mismos estilos
p = BASE / "components" / "PreviewPane.tsx"
t = p.read_text(encoding="utf-8")
t = t.replace("""      style={{
        left: c.bbox.x, top: c.bbox.y, width: c.bbox.width, height: c.bbox.height,
        background: typeof c.styles.background === "string" ? c.styles.background : undefined,
        color: typeof c.styles.color === "string" ? c.styles.color : undefined,
        fontSize: c.styles.fontSize ? Number(c.styles.fontSize) : undefined,
        borderRadius: c.styles.radius ? Number(c.styles.radius) : undefined,
      }}""",
"""      style={{
        left: c.bbox.x, top: c.bbox.y, width: c.bbox.width, height: c.bbox.height,
        background: typeof c.styles.background === "string" ? c.styles.background : undefined,
        color: typeof c.styles.color === "string" ? c.styles.color : undefined,
        fontSize: c.styles.fontSize ? Number(c.styles.fontSize) : undefined,
        fontFamily: typeof c.styles.fontFamily === "string" ? c.styles.fontFamily : undefined,
        fontWeight: c.styles.fontWeight != null ? Number(c.styles.fontWeight) : undefined,
        fontStyle: typeof c.styles.fontStyle === "string" ? c.styles.fontStyle : undefined,
        textAlign: typeof c.styles.textAlign === "string" ? (c.styles.textAlign as React.CSSProperties["textAlign"]) : undefined,
        textShadow: typeof c.styles.shadow === "string" ? c.styles.shadow : undefined,
        borderRadius: c.styles.radius ? Number(c.styles.radius) : undefined,
        opacity: c.styles.opacity != null ? Number(c.styles.opacity) : undefined,
      }}""")
p.write_text(t, encoding="utf-8")
print("preview ok")

# 4) CSS: color inputs
p = BASE / "styles" / "index.css"
t = p.read_text(encoding="utf-8")
if "color-inputs" not in t:
    t = t.replace("/* OCR (F3) */", """/* tipografía (F4) */
.color-field .color-inputs, .field .color-inputs {
  display: flex; align-items: center; gap: 6px;
}
.color-inputs input[type="color"] {
  width: 34px; height: 26px; padding: 1px; cursor: pointer; flex-shrink: 0;
}
.color-inputs input[type="text"], .color-inputs input:not([type]) { flex: 1; }

/* OCR (F3) */""")
    p.write_text(t, encoding="utf-8")
print("css ok")

# 5) export: estilos tipográficos en el código generado
p = Path(__file__).resolve().parent.parent / "backend" / "export" / "react_export.py"
t = p.read_text(encoding="utf-8")
t = t.replace('''    if s.get("background"):
        parts.append(f"background: '{s['background']}'")
    if s.get("color"):
        parts.append(f"color: '{s['color']}'")
    if s.get("fontSize"):
        parts.append(f"fontSize: '{s['fontSize']}'")
    if s.get("radius"):
        parts.append(f"borderRadius: '{s['radius']}px'")''',
'''    if s.get("background"):
        parts.append(f"background: '{s['background']}'")
    if s.get("color"):
        parts.append(f"color: '{s['color']}'")
    if s.get("fontSize"):
        parts.append(f"fontSize: '{s['fontSize']}'")
    for key in ("fontFamily", "fontWeight", "fontStyle", "textAlign", "shadow"):
        if s.get(key):
            parts.append(f"{key if key != 'shadow' else 'textShadow'}: '{s[key]}'")
    if s.get("opacity") is not None:
        parts.append(f"opacity: {s['opacity']}")
    if s.get("radius"):
        parts.append(f"borderRadius: '{s['radius']}px'")''')
p.write_text(t, encoding="utf-8")
print("export ok")
