/** RIGHT panel: full inspector — content, style, events/bindings, data, state. */
import { useEditor } from "../state/editorStore";
import { COMPONENT_TYPES } from "../types";
import type { ComponentType } from "../types";
import { BindingEditor } from "./BindingEditor";

export const PRESETS: Record<string, [number, number]> = {
  "Escritorio 1920": [1920, 1080],
  "Escritorio 1366": [1366, 768],
  "Portátil": [1536, 864],
  "Tablet": [820, 1180],
  "Móvil": [390, 844],
};

export function Inspector() {
  const editor = useEditor();
  const c = editor.selected();

  if (!c) {
    const screen = editor.state.doc?.screen;
    return (
      <div className="inspector">
        <div className="panel-header"><span>INSPECTOR</span></div>
        <div className="inspector-body">
          <div className="insp-section">
            <div className="insp-label">LIENZO</div>
            {screen ? (
              <>
                <label className="field"><span>Preset</span>
                  <select value={screen.preset ?? "custom"}
                    onChange={(e) => {
                      const preset = e.target.value;
                      if (preset === "custom") { editor.setScreen(screen.width, screen.height, null); return; }
                      const [w, h] = PRESETS[preset];
                      editor.setScreen(w, h, preset);
                    }}>
                    {Object.entries(PRESETS).map(([k, v]) => (
                      <option key={k} value={k}>{k} ({v[0]}×{v[1]})</option>
                    ))}
                    <option value="custom">Personalizado</option>
                  </select>
                </label>
                <div className="field-grid">
                  <label className="field"><span>Ancho</span>
                    <input type="number" value={screen.width}
                      onChange={(e) => editor.setScreen(Math.max(50, Number(e.target.value)), screen.height, null)} />
                  </label>
                  <label className="field"><span>Alto</span>
                    <input type="number" value={screen.height}
                      onChange={(e) => editor.setScreen(screen.width, Math.max(50, Number(e.target.value)), null)} />
                  </label>
                </div>
                <p className="hint">Cambia el tamaño del lienzo donde trabajas. Los componentes y la imagen de referencia se conservan.</p>
              </>
            ) : <span className="dim">Sin documento: importa una imagen o añade componentes.</span>}
          </div>
          <div className="insp-section">
            <div className="insp-label">AYUDA</div>
            <p className="hint">Selecciona un componente en el lienzo o en el árbol para editar contenido, estilo y bindings. Sin selección, aquí ajustas el lienzo.</p>
          </div>
        </div>
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
