/** PREVIEW: renders the reconstructed UI read-only.
 *  - Design preview: full render of the AST.
 *  - Connected preview: marks bound components; live network calls require the
 *    imported project to be running (documented limitation in v0.1). */
import { useState } from "react";
import { api } from "../api/client";
import { useEditor } from "../state/editorStore";
import type { UIComponent } from "../types";

export function PreviewPane({ onClose }: { onClose: () => void }) {
  const editor = useEditor();
  const doc = editor.state.doc;
  const ws = editor.state.workspace;
  const [mode, setMode] = useState<"design" | "connected">("design");
  const [trace, setTrace] = useState<string[]>([]);

  if (!doc) return <div className="preview-empty">Nada que previsualizar aún.</div>;

  const fireBound = async (c: UIComponent) => {
    if (mode !== "connected" || !ws || c.bindings.length === 0) return;
    setTrace((t) => [`CLICK ${c.name} (${c.id}) — binding ${c.bindings[0]}`, ...t].slice(0, 50));
    try {
      await api.addTraceEvent(ws.id, { event: "preview-click", component: c.id });
    } catch { /* trace is best-effort */ }
  };

  return (
    <div className="preview-pane">
      <div className="preview-toolbar">
        <button className={`btn-mini ${mode === "design" ? "btn-primary" : ""}`}
          onClick={() => setMode("design")}>Design</button>
        <button className={`btn-mini ${mode === "connected" ? "btn-primary" : ""}`}
          onClick={() => setMode("connected")}>Connected</button>
        <span className="dim">
          {mode === "connected"
            ? "los bindings confirmados requieren el proyecto importado corriendo"
            : "render fiel del AST reconstruido"}
        </span>
        <span className="spacer" />
        <button className="btn-mini" onClick={onClose}>✕ Cerrar preview</button>
      </div>
      {mode === "connected" && trace.length > 0 && (
        <div className="preview-trace">
          {trace.map((t, i) => <div key={i} className="mono dim">{t}</div>)}
        </div>
      )}
      <div className="preview-scroll">
        <div className="preview-stage" style={{
          width: doc.screen.width, height: doc.screen.height,
          background: doc.screen.background ?? "#101216",
        }}>
          {editor.childrenOf("screen").map((c) => (
            <PreviewNode key={c.id} component={c} mode={mode} onFire={fireBound} />
          ))}
        </div>
      </div>
    </div>
  );
}

function PreviewNode({ component: c, mode, onFire }: {
  component: UIComponent; mode: "design" | "connected";
  onFire: (c: UIComponent) => void;
}) {
  const editor = useEditor();
  const bound = mode === "connected" && c.bindings.length > 0;
  const Tag = (c.type === "button" ? "button" : "div") as keyof React.JSX.IntrinsicElements;
  return (
    <Tag
      className={`preview-node preview-${c.type} ${bound ? "preview-bound" : ""}`}
      style={{
        left: c.bbox.x, top: c.bbox.y, width: c.bbox.width, height: c.bbox.height,
        background: typeof c.styles.background === "string" ? c.styles.background : undefined,
        color: typeof c.styles.color === "string" ? c.styles.color : undefined,
        fontSize: c.styles.fontSize ? Number(c.styles.fontSize) : undefined,
        borderRadius: c.styles.radius ? Number(c.styles.radius) : undefined,
      }}
      onClick={() => onFire(c)}
    >
      {c.text && <span>{c.text}</span>}
      {editor.childrenOf(c.id).map((k) => (
        <PreviewNode key={k.id} component={k} mode={mode} onFire={onFire} />
      ))}
    </Tag>
  );
}
