/** LEFT panel: component tree with selection, add, delete, visibility. */
import { useState } from "react";
import { useEditor } from "../state/editorStore";
import { COMPONENT_TYPES } from "../types";
import type { ComponentType, UIComponent } from "../types";

const TYPE_ICONS: Record<string, string> = {
  container: "▣", panel: "▤", card: "▢", text: "T", heading: "H", button: "⬭",
  input: "▭", textarea: "▬", select: "▼", checkbox: "☑", radio: "◉", image: "🖼",
  icon: "◆", table: "▦", chart: "📈", tabs: "⇥", sidebar: "▐", navbar: "▬",
  modal: "❐", divider: "—", custom: "?",
};

export function TreePanel() {
  const editor = useEditor();
  const [adding, setAdding] = useState(false);
  const [filter, setFilter] = useState("");

  const matches = (c: UIComponent): boolean =>
    !filter || c.name.toLowerCase().includes(filter.toLowerCase())
    || c.type.includes(filter.toLowerCase());

  const renderNode = (c: UIComponent, depth: number) => {
    if (!matches(c) && editor.childrenOf(c.id).length === 0) return null;
    const selected = editor.state.selectedId === c.id;
    return (
      <div key={c.id}>
        <div
          className={`tree-row ${selected ? "tree-row-selected" : ""}`}
          style={{ paddingLeft: 8 + depth * 14 }}
          onClick={() => editor.select(c.id)}
        >
          <span className="tree-icon">{TYPE_ICONS[c.type] ?? "?"}</span>
          <span className="tree-name">{c.name || c.id}</span>
          {c.bindings.length > 0 && <span className="tree-badge">b{c.bindings.length}</span>}
          <span className="tree-conf" title="confianza (F=hecho manual, H=alta, M=media, L=baja, ?=desconocida)">
            {bandLabel(Number(c.metadata.confidence ?? 0), c.metadata.source === "manual")}
          </span>
        </div>
        {editor.childrenOf(c.id).map((k) => renderNode(k, depth + 1))}
      </div>
    );
  };

  return (
    <div className="tree-panel">
      <div className="panel-header">
        <span>COMPONENTES</span>
        <button className="btn-mini" title="Añadir componente" onClick={() => setAdding((v) => !v)}>+</button>
      </div>
      {adding && (
        <div className="tree-add">
          <select id="tree-add-type" defaultValue="container">
            {COMPONENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button className="btn-mini btn-primary" onClick={() => {
            const type = (document.getElementById("tree-add-type") as HTMLSelectElement)
              .value as ComponentType;
            const parent = editor.state.selectedId;
            const box = parent && editor.byId(parent)
              ? { ...editor.byId(parent)!.bbox, x: editor.byId(parent)!.bbox.x + 20, y: editor.byId(parent)!.bbox.y + 20 }
              : { x: 40, y: 40, width: 180, height: type === "text" ? 24 : 60 };
            const id = editor.addComponent(type, parent ?? "screen",
              { ...box, width: Math.max(24, box.width), height: Math.max(16, box.height) });
            editor.select(id);
            setAdding(false);
          }}>Crear</button>
        </div>
      )}
      <input className="tree-filter" placeholder="filtrar…" value={filter}
        onChange={(e) => setFilter(e.target.value)} />
      <div className="tree-body">
        {editor.state.doc ? (
          <>
            <div className="tree-row tree-screen">🖥 pantalla {editor.state.doc.screen.width}×{editor.state.doc.screen.height}</div>
            {editor.childrenOf("screen").map((c) => renderNode(c, 1))}
          </>
        ) : (
          <div className="tree-empty">Sin componentes</div>
        )}
      </div>
      {editor.state.selectedId && (
        <div className="tree-actions">
          <button className="btn-mini" onClick={() => editor.duplicateComponent(editor.state.selectedId!)}
            title="Duplicar">⧉</button>
          <button className="btn-mini btn-danger" onClick={() => editor.deleteComponent(editor.state.selectedId!)}
            title="Eliminar (Supr)">✕</button>
        </div>
      )}
    </div>
  );
}

export function bandLabel(conf: number, manual: boolean): string {
  if (manual) return "F";
  if (conf >= 0.85) return "H";
  if (conf >= 0.6) return "M";
  if (conf > 0) return "L";
  return "?";
}
