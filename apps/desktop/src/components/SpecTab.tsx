/** SPEC mode (F1): describes the interface in plain language → mounts on the canvas → connects to real project capabilities.
 * Items live in doc.metadata.spec_items (versioned, saved with the document). */
import { useMemo, useState } from "react";
import { api } from "../api/client";
import { useEditor } from "../state/editorStore";
import { COMPONENT_TYPES } from "../types";
import type { ComponentType, SpecItem, Suggestion } from "../types";

const DEFAULT_W: Record<string, number> = {
  button: 140, input: 260, text: 180, heading: 220, panel: 320, card: 300,
};
const DEFAULT_H: Record<string, number> = { button: 42, input: 36, text: 24, heading: 34, panel: 200, card: 160 };

export function SpecTab() {
  const editor = useEditor();
  const ws = editor.state.workspace;
  const doc = editor.state.doc;
  const items = useMemo<SpecItem[]>(
    () => (doc?.metadata?.spec_items as SpecItem[] | undefined) ?? [], [doc]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<ComponentType>("button");
  const [suggestFor, setSuggestFor] = useState<SpecItem | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [caps, setCaps] = useState<Record<string, { name: string; qualified_name: string }>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const saveItems = (next: SpecItem[]) => editor.patchMetadata({ spec_items: next });

  const addItem = () => {
    if (!name.trim()) return;
    saveItems([...items, {
      id: `spec_${Date.now().toString(36)}`, name: name.trim(),
      description: description.trim(), type, mounted_component_id: null,
    }]);
    setName(""); setDescription("");
  };

  const mount = (item: SpecItem) => {
    // auto-layout: column centered on the canvas (or over the reference image)
    const screenW = doc?.screen.width ?? 1280;
    const y = 120 + items.filter((i) => i.mounted_component_id).length * 90;
    const w = DEFAULT_W[item.type] ?? 160;
    const h = DEFAULT_H[item.type] ?? 40;
    const id = editor.addComponent(item.type, "screen", {
      x: Math.round(screenW / 2 - w / 2), y, width: w, height: h,
    });
    editor.updateComponent(id, {
      name: item.name, text: item.name,
      metadata: { confidence: 1.0, source: "spec" },
    });
    saveItems(items.map((i) => (i.id === item.id ? { ...i, mounted_component_id: id } : i)));
  };

  const suggest = async (item: SpecItem) => {
    if (!ws) return;
    setSuggestFor(item); setSuggestions([]); setError(null); setBusy(true);
    try {
      const [res, allCaps] = await Promise.all([api.specSuggest(ws.id, item), api.capabilities(ws.id)]);
      setSuggestions(res.suggestions);
      setCaps(Object.fromEntries(allCaps.map((c) => [c.capability_id, c])));
    } catch (e) {
      setError(String((e as { message?: string }).message ?? e));
    } finally { setBusy(false); }
  };

  const bindMounted = async (item: SpecItem, s: Suggestion, status: "CONFIRMED" | "SUGGESTED") => {
    if (!ws || !item.mounted_component_id) return;
    setBusy(true); setError(null);
    try {
      await api.createBinding(ws.id, {
        component_id: item.mounted_component_id,
        event: item.type === "input" || item.type === "textarea" ? "onChange" : "onClick",
        target_capability: s.capability_id,
        confidence: s.score, status, rationale: s.rationale,
      });
      editor.select(item.mounted_component_id);
    } catch (e) {
      setError(String((e as { message?: string }).message ?? e));
    } finally { setBusy(false); }
  };

  return (
    <div className="tab-col">
      <div className="tab-note">
        Describe los botones que tendrá la interfaz (nueva o sobre la importada). Móntalos en el lienzo
        y conéctalos con lo que el proyecto importado <strong>sabe hacer de verdad</strong>.
      </div>
      {items.length === 0 && !doc && <div className="empty-line">Crea un workspace con documento (importa imagen o añade un componente) para empezar.</div>}

      <div className="spec-form">
        <input placeholder="Nombre visible (p.ej. Generar informe)" value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") addItem(); }} />
        <input placeholder="Qué tiene que hacer (p.ej. genera y guarda un informe de ideas)"
          value={description} onChange={(e) => setDescription(e.target.value)} />
        <select value={type} onChange={(e) => setType(e.target.value as ComponentType)}>
          {COMPONENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <button className="btn-mini btn-primary" onClick={addItem}>Añadir</button>
      </div>

      {items.length > 0 && (
        <table className="data-table">
          <thead><tr><th>Nombre</th><th>Tipo</th><th>Descripción</th><th>Estado</th><th>Acciones</th></tr></thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td><strong>{item.name}</strong></td>
                <td><span className="kind">{item.type}</span></td>
                <td className="dim">{item.description || "—"}</td>
                <td>{item.mounted_component_id
                  ? <span className="status status-confirmed">montado</span>
                  : <span className="status status-suggested">pendiente</span>}</td>
                <td className="spec-actions">
                  {!item.mounted_component_id
                    ? <button className="btn-mini btn-primary" onClick={() => mount(item)}>Montar</button>
                    : <button className="btn-mini" onClick={() => editor.select(item.mounted_component_id!)}>Ver</button>}
                  <button className="btn-mini" onClick={() => void suggest(item)}>Conectar</button>
                  <button className="btn-mini btn-danger" onClick={() => saveItems(items.filter((i) => i.id !== item.id))}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {suggestFor && (
        <div className="spec-suggest">
          <div className="insp-label">
            CONEXIONES PARA «{suggestFor.name}» {busy && "— buscando…"}
          </div>
          {error && <div className="error-note">{error}</div>}
          {suggestions.length === 0 && !busy && !error && (
            <div className="empty-line">Sin coincidencias: analiza el proyecto primero o afina la descripción.</div>
          )}
          {suggestions.map((s) => {
            const cap = caps[s.capability_id];
            return (
              <div key={s.capability_id} className="suggestion">
                <div className="suggestion-head">
                  <span className="score">{Math.round(s.score * 100)}%</span>
                  <strong>{cap?.name ?? s.capability_id}</strong>
                </div>
                <div className="suggestion-sub">{cap?.qualified_name}</div>
                <ul className="rationale">{s.rationale.map((r, i) => <li key={i}>{r}</li>)}</ul>
                {suggestFor.mounted_component_id ? (
                  <div className="suggestion-actions">
                    <button className="btn-mini btn-primary" disabled={busy}
                      onClick={() => void bindMounted(suggestFor, s, "CONFIRMED")}>Confirmar binding</button>
                    <button className="btn-mini" disabled={busy}
                      onClick={() => void bindMounted(suggestFor, s, "SUGGESTED")}>Solo sugerir</button>
                  </div>
                ) : <div className="tab-note">Móntalo en el lienzo para poder crear el binding.</div>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
