/** RIGHT panel: contextual inspector with Diseño / Acción / Datos tabs (F8). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useEditor } from "../state/editorStore";
import { COMPONENT_TYPES } from "../types";
import type { ComponentType, UIComponent } from "../types";
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
  const [tab, setTab] = useState<"diseno" | "accion" | "datos">("diseno");

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

  const tabNames: [typeof tab, string][] = [
    ["diseno", "Diseño"], ["accion", "Acción"], ["datos", "Datos"],
  ];
  return (
    <div className="inspector">
      <div className="panel-header">
        {c ? (
          <div className="insp-tabs">
            {tabNames.map(([id, label]) => (
              <button key={id} className={`insp-tab ${tab === id ? "insp-tab-active" : ""}`}
                onClick={() => setTab(id)}>{label}</button>
            ))}
          </div>
        ) : <span>INSPECTOR</span>}
      </div>
      <div className="inspector-body">
        {c && tab === "accion" && (
          <div className="insp-section">
            <div className="insp-title">
              <strong>{c.type.toUpperCase()}</strong> <code>{c.name}</code>
              <span className={`conf conf-${band.toLowerCase()}`}>{band}</span>
            </div>
            <div className="insp-id">{c.id} · parent: {c.parent_id ?? "screen"}</div>
          </div>
        )}
        {c && tab === "datos" && (
          <div className="insp-section">
            <div className="insp-title">
              <strong>{c.type.toUpperCase()}</strong> <code>{c.name}</code>
              <span className={`conf conf-${band.toLowerCase()}`}>{band}</span>
            </div>
            <div className="insp-id">{c.id} · parent: {c.parent_id ?? "screen"}</div>
          </div>
        )}
        {c && tab === "diseno" && (
        <div className="insp-section">
          <div className="insp-title">
            <strong>{c.type.toUpperCase()}</strong> <code>{c.name}</code>
            <span className={`conf conf-${band.toLowerCase()}`}>{band}</span>
          </div>
          <div className="insp-id">{c.id} · parent: {c.parent_id ?? "screen"}</div>
        </div>
        )}

        {c && tab === "diseno" && (
        <>
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
            <label className="field color-field"><span>Color</span>
              <span className="color-inputs">
                <input type="color" value={/^#[0-9a-fA-F]{6}$/.test(String(c.styles.color ?? "")) ? String(c.styles.color) : "#e8eaf0"}
                  onChange={(e) => editor.setStyle(c.id, "color", e.target.value)} />
                <input value={String(c.styles.color ?? "")} placeholder="#rrggbb"
                  onChange={(e) => editor.setStyle(c.id, "color", e.target.value)} />
              </span>
            </label>
            <label className="field color-field"><span>Fondo</span>
              <span className="color-inputs">
                <input type="color" value={/^#[0-9a-fA-F]{6}$/.test(String(c.styles.background ?? "")) ? String(c.styles.background) : "#1b2029"}
                  onChange={(e) => editor.setStyle(c.id, "background", e.target.value)} />
                <input value={String(c.styles.background ?? "")} placeholder="#rrggbb / transparente"
                  onChange={(e) => editor.setStyle(c.id, "background", e.target.value)} />
              </span>
            </label>
            {styleField("radius", "Redondeo", "number")}
            {styleField("padding", "Relleno")}
            {styleField("border", "Borde")}
            <label className="field"><span>Opacidad %</span>
              <input type="range" min={0} max={100}
                value={Math.round(Number(c.styles.opacity ?? 1) * 100)}
                onChange={(e) => editor.setStyle(c.id, "opacity", Number(e.target.value) / 100)} />
            </label>
          </div>
        </div>

        <TypographySection editor={editor} component={c} />
        </>
        )}

        {c && tab === "accion" && (
          <>
            <div className="insp-section">
              <div className="insp-label">EVENTOS</div>
              <div className="insp-events">
                {c.bindings.length === 0 && (
                  <span className="dim">Este elemento aún no dispara nada: conecta una acción abajo.</span>
                )}
                {Object.entries(c.events).map(([k, v]) => (
                  <div key={k} className="kv"><span>{k}</span><code>{String(v)}</code></div>
                ))}
              </div>
            </div>
            <BindingEditor componentId={c.id} />
          </>
        )}

        {c && tab === "datos" && (
          <>
            <div className="insp-section">
              <div className="insp-label">METADATOS</div>
              <div className="kv"><span>source</span><code>{String(c.metadata.source ?? "?")}</code></div>
              <div className="kv"><span>confidence</span><code>{conf.toFixed(3)}</code></div>
              <div className="kv"><span>bindings</span><code>{c.bindings.length}</code></div>
            </div>
            <div className="insp-section">
              <div className="insp-label">AVANZADO</div>
              <p className="hint">IDs, firmas y grafo completo de capacidades: dock Diagnóstico → Bindings / Capacidades.</p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function TypographySection({ editor, component: c }: {
  editor: ReturnType<typeof useEditor>; component: UIComponent;
}) {
  const [fonts, setFonts] = useState<string[]>([]);
  useEffect(() => {
    void api.fonts().then((r) => setFonts(r.fonts.map((f) => f.family))).catch(() => setFonts([]));
  }, []);
  const hasShadow = Boolean(c.styles.shadow);
  return (
    <div className="insp-section">
      <div className="insp-label">TIPOGRAFÍA</div>
      <label className="field"><span>Fuente</span>
        <select value={String(c.styles.fontFamily ?? "")}
          onChange={(e) => editor.setStyle(c.id, "fontFamily", e.target.value || null)}>
          <option value="">(predeterminada)</option>
          {fonts.map((f) => <option key={f} value={f}
            style={{ fontFamily: f }}>{f}</option>)}
        </select>
      </label>
      <div className="field-grid">
        <label className="field"><span>Tamaño</span>
          <input type="number" value={String(c.styles.fontSize ?? "")} placeholder="px"
            onChange={(e) => editor.setStyle(c.id, "fontSize", e.target.value ? Number(e.target.value) : null)} />
        </label>
        <label className="field"><span>Peso</span>
          <select value={String(c.styles.fontWeight ?? "")}
            onChange={(e) => editor.setStyle(c.id, "fontWeight", e.target.value || null)}>
            <option value="">normal</option>
            {[300, 400, 500, 600, 700, 800].map((w) => <option key={w} value={w}>{w}</option>)}
          </select>
        </label>
        <label className="field"><span>Estilo</span>
          <select value={String(c.styles.fontStyle ?? "")}
            onChange={(e) => editor.setStyle(c.id, "fontStyle", e.target.value || null)}>
            <option value="">normal</option>
            <option value="italic">cursiva</option>
          </select>
        </label>
        <label className="field"><span>Alineación</span>
          <select value={String(c.styles.textAlign ?? "")}
            onChange={(e) => editor.setStyle(c.id, "textAlign", e.target.value || null)}>
            <option value="">izquierda</option>
            <option value="center">centro</option>
            <option value="right">derecha</option>
          </select>
        </label>
      </div>
      <div className="field">
        <span>Sombra de texto</span>
        <span className="color-inputs">
          <input type="checkbox" checked={hasShadow}
            onChange={(e) => editor.setStyle(c.id, "shadow",
              e.target.checked ? "0 2px 8px #000000cc" : null)} />
          <input type="color" value={(() => {
            const tail = String(c.styles.shadow ?? "").split(" ").pop() ?? "";
            return /^#[0-9a-fA-F]{6}$/.test(tail) ? tail : "#000000";
          })()}
            disabled={!hasShadow}
            onChange={(e) => editor.setStyle(c.id, "shadow", `0 2px 8px ${e.target.value}`)} />
          <span className="dim">{hasShadow ? "activada" : "sin sombra"}</span>
        </span>
      </div>
    </div>
  );
}
