/** RIGHT panel: full inspector — content, style, events/bindings, data, state. */
import { useEditor } from "../state/editorStore";
import { COMPONENT_TYPES } from "../types";
import type { ComponentType } from "../types";
import { BindingEditor } from "./BindingEditor";

export function Inspector() {
  const editor = useEditor();
  const c = editor.selected();

  if (!c) {
    return (
      <div className="inspector">
        <div className="panel-header"><span>INSPECTOR</span></div>
        <div className="inspector-empty">Selecciona un componente en el lienzo o en el árbol.</div>
      </div>
    );
  }

  const num = (key: string, label: string) => (
    <label className="field">
      <span>{label}</span>
      <input type="number" value={Number(c.bbox[key as keyof typeof c.bbox] ?? 0)}
        onChange={(e) => editor.updateBBox(c.id, { [key]: Number(e.target.value) })} />
    </label>
  );

  const styleField = (key: string, label: string, type: "text" | "number" = "text") => (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={String(c.styles[key] ?? "")}
        placeholder="—"
        onChange={(e) =>
          editor.setStyle(c.id, key, type === "number" ? Number(e.target.value) : e.target.value)}
      />
    </label>
  );

  const conf = Number(c.metadata.confidence ?? 0);
  const band = c.metadata.source === "manual" ? "FACT"
    : conf >= 0.85 ? "HIGH" : conf >= 0.6 ? "MEDIUM" : conf > 0 ? "LOW" : "UNKNOWN";

  return (
    <div className="inspector">
      <div className="panel-header"><span>INSPECTOR</span></div>
      <div className="inspector-body">
        <div className="insp-section">
          <div className="insp-title">
            <strong>{c.type.toUpperCase()}</strong> <code>{c.name}</code>
            <span className={`conf conf-${band.toLowerCase()}`}>{band}</span>
          </div>
          <div className="insp-id">{c.id} · parent: {c.parent_id ?? "screen"}</div>
        </div>

        <div className="insp-section">
          <div className="insp-label">CONTENIDO</div>
          <label className="field"><span>Nombre</span>
            <input value={c.name} onChange={(e) => editor.updateComponent(c.id, { name: e.target.value })} />
          </label>
          <label className="field"><span>Texto</span>
            <input value={c.text ?? ""} placeholder="(sin texto)"
              onChange={(e) => editor.setText(c.id, e.target.value)} />
          </label>
          <label className="field"><span>Tipo</span>
            <select value={c.type} onChange={(e) =>
              editor.updateComponent(c.id, { type: e.target.value as ComponentType })}>
              {COMPONENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
        </div>

        <div className="insp-section">
          <div className="insp-label">GEOMETRÍA</div>
          <div className="field-grid">
            {num("x", "X")}{num("y", "Y")}{num("width", "Ancho")}{num("height", "Alto")}
          </div>
        </div>

        <div className="insp-section">
          <div className="insp-label">ESTILO</div>
          <div className="field-grid">
            {styleField("background", "Fondo")}
            {styleField("color", "Color")}
            {styleField("fontSize", "Tamaño fuente", "number")}
            {styleField("fontFamily", "Fuente")}
            {styleField("radius", "Redondeo", "number")}
            {styleField("padding", "Relleno")}
            {styleField("margin", "Margen")}
            {styleField("border", "Borde")}
            {styleField("shadow", "Sombra")}
            {styleField("opacity", "Opacidad", "number")}
          </div>
        </div>

        <div className="insp-section">
          <div className="insp-label">EVENTOS</div>
          <div className="insp-events">
            {c.bindings.length === 0 && <span className="dim">Sin bindings. Usa SMART BIND más abajo.</span>}
            {Object.entries(c.events).map(([k, v]) => (
              <div key={k} className="kv"><span>{k}</span><code>{String(v)}</code></div>
            ))}
          </div>
        </div>

        <BindingEditor componentId={c.id} />

        <div className="insp-section">
          <div className="insp-label">METADATOS</div>
          <div className="kv"><span>source</span><code>{String(c.metadata.source ?? "?")}</code></div>
          <div className="kv"><span>confidence</span><code>{conf.toFixed(3)}</code></div>
        </div>
      </div>
    </div>
  );
}
