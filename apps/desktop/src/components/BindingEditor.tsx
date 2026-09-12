/** Smart Binder UI: suggestions for the selected component + binding editor
 *  (inputs/outputs/loading/error mappings) with CONFIRM / BREAK status flow. */
import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useEditor } from "../state/editorStore";
import type { Binding, Capability, Mapping, Suggestion } from "../types";

interface Props { componentId: string; }

export function BindingEditor({ componentId }: Props) {
  const editor = useEditor();
  const ws = editor.state.workspace;
  const comp = editor.byId(componentId);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [caps, setCaps] = useState<Record<string, Capability>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bindings, setBindings] = useState<Binding[]>([]);
  const [editing, setEditing] = useState<Binding | null>(null);

  const reloadBindings = useCallback(async () => {
    if (!ws) return;
    try {
      const all = await api.bindings(ws.id);
      setBindings(all.filter((b) => b.component_id === componentId));
    } catch (e) {
      setError(String(e));
    }
  }, [ws, componentId]);

  useEffect(() => { void reloadBindings(); }, [reloadBindings]);

  const suggest = async () => {
    if (!ws) return;
    setBusy(true); setError(null);
    try {
      const [res, allCaps] = await Promise.all([api.suggest(ws.id, componentId), api.capabilities(ws.id)]);
      setSuggestions(res.suggestions);
      setCaps(Object.fromEntries(allCaps.map((c) => [c.capability_id, c])));
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  };

  const create = async (s: Suggestion, status: Binding["status"]) => {
    if (!ws || !comp) return;
    setBusy(true); setError(null);
    try {
      const cap = caps[s.capability_id];
      const input_mapping: Mapping[] = (cap?.inputs ?? []).map((p) => ({
        source: "", target: p.name,
      }));
      const output_mapping: Mapping[] = (cap?.outputs.length ? cap.outputs : [{ name: "return", type: "unknown", required: true, description: "" }])
        .map((p) => ({ source: p.name, target: comp.id }));
      const b = await api.createBinding(ws.id, {
        component_id: componentId, event: comp.type === "input" || comp.type === "textarea" ? "onChange" : "onClick",
        target_capability: s.capability_id,
        input_mapping, output_mapping,
        loading_mapping: "", error_mapping: "error",
        confidence: s.score, status, rationale: s.rationale,
      });
      setEditing(b);
      await reloadBindings();
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  };

  const mine = bindings;

  return (
    <div className="insp-section binder">
      <div className="insp-label">SMART BIND</div>
      <button className="btn btn-secondary btn-block" disabled={busy || !ws} onClick={suggest}>
        {busy ? "…" : "Sugerir bindings"}
      </button>
      {error && <div className="error-note">{error}</div>}

      {suggestions.length > 0 && (
        <div className="suggestions">
          {suggestions.map((s) => {
            const cap = caps[s.capability_id];
            return (
              <div key={s.capability_id} className="suggestion">
                <div className="suggestion-head">
                  <span className="score">{Math.round(s.score * 100)}%</span>
                  <strong>{cap?.name ?? s.capability_id}</strong>
                </div>
                <div className="suggestion-sub">{cap?.qualified_name}</div>
                <ul className="rationale">
                  {s.rationale.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
                {(s.side_effects.length > 0) && (
                  <div className="side-effects">efectos: {s.side_effects.join(", ")}</div>
                )}
                <div className="suggestion-actions">
                  <button className="btn-mini btn-primary" disabled={busy}
                    onClick={() => create(s, "CONFIRMED")}>Confirmar</button>
                  <button className="btn-mini" disabled={busy}
                    onClick={() => create(s, "SUGGESTED")}>Solo sugerir</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {mine.length > 0 && (
        <div className="existing-bindings">
          <div className="insp-label">BINDINGS ({mine.length})</div>
          {mine.map((b) => (
            <div key={b.binding_id} className={`binding-row binding-${b.status.toLowerCase()}`}>
              <span className={`status status-${b.status.toLowerCase()}`}>{b.status}</span>
              <span className="binding-target">{b.target_name ?? b.target_capability}</span>
              <span className="binding-event">{b.event}</span>
              <button className="btn-mini" onClick={() => setEditing(b)}>edit</button>
              <button className="btn-mini btn-danger" onClick={async () => {
                if (!ws) return;
                await api.deleteBinding(ws.id, b.binding_id);
                void reloadBindings();
              }}>✕</button>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <BindingForm binding={editing} wsId={ws?.id ?? ""} caps={caps}
          onSaved={async (b) => { setEditing(b ?? null); await reloadBindings(); }}
          onCancel={() => setEditing(null)} />
      )}
    </div>
  );
}

function BindingForm({ binding, wsId, caps, onSaved, onCancel }: {
  binding: Binding; wsId: string; caps: Record<string, Capability>;
  onSaved: (b: Binding | null) => void; onCancel: () => void;
}) {
  const [b, setB] = useState<Binding>(binding);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cap = caps[b.target_capability];

  const patch = (p: Partial<Binding>) => setB((prev) => ({ ...prev, ...p }));

  const save = async () => {
    setBusy(true); setError(null);
    try {
      const updated = await api.updateBinding(wsId, b.binding_id, {
        event: b.event, input_mapping: b.input_mapping, output_mapping: b.output_mapping,
        loading_mapping: b.loading_mapping, error_mapping: b.error_mapping,
        status: b.status,
      });
      onSaved(updated);
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="binding-form">
      <div className="insp-label">EDITAR BINDING</div>
      <div className="kv"><span>SOURCE</span><code>{b.component_id}</code></div>
      <label className="field"><span>Evento</span>
        <select value={b.event} onChange={(e) => patch({ event: e.target.value })}>
          {["onClick", "onChange", "onSubmit", "onInput", "onFocus", "onBlur"].map((ev) =>
            <option key={ev}>{ev}</option>)}
        </select>
      </label>
      <label className="field"><span>Destino</span>
        <input value={cap?.qualified_name ?? b.target_capability} readOnly />
      </label>
      <div className="field"><span>Estado</span>
        <div className="status-picker">
          {(["SUGGESTED", "CONFIRMED", "BROKEN", "UNKNOWN"] as const).map((s) => (
            <button key={s} className={`btn-mini ${b.status === s ? "btn-primary" : ""}`}
              onClick={() => patch({ status: s })}>{s}</button>
          ))}
        </div>
      </div>

      <div className="insp-label">ENTRADAS</div>
      {(cap?.inputs ?? []).map((p) => {
        const m = b.input_mapping.find((x) => x.target === p.name);
        return (
          <div className="mapping-row" key={p.name}>
            <input placeholder="componente-origen" value={m?.source ?? ""}
              onChange={(e) => patch({
                input_mapping: upsert(b.input_mapping, p.name, e.target.value, "target"),
              })} />
            <span className="arrow">→</span>
            <code>{p.name}</code>
            {!p.required && <span className="dim">?</span>}
          </div>
        );
      })}

      <div className="insp-label">SALIDAS</div>
      {b.output_mapping.map((m, i) => (
        <div className="mapping-row" key={i}>
          <code>{m.source}</code>
          <span className="arrow">→</span>
          <input placeholder="componente-destino" value={m.target}
            onChange={(e) => patch({
              output_mapping: b.output_mapping.map((x, j) =>
                j === i ? { ...x, target: e.target.value } : x),
            })} />
        </div>
      ))}

      <div className="insp-label">CARGA / ERROR</div>
      <label className="field"><span>Estado de carga</span>
        <input value={b.loading_mapping} onChange={(e) => patch({ loading_mapping: e.target.value })} />
      </label>
      <label className="field"><span>Estado de error</span>
        <input value={b.error_mapping} onChange={(e) => patch({ error_mapping: e.target.value })} />
      </label>

      {error && <div className="error-note">{error}</div>}
      <div className="form-actions">
        <button className="btn-mini btn-primary" disabled={busy} onClick={save}>Guardar</button>
        <button className="btn-mini" onClick={onCancel}>Cerrar</button>
      </div>
    </div>
  );
}

function upsert(list: Mapping[], key: string, value: string, keyField: "source" | "target"): Mapping[] {
  const idx = list.findIndex((m) => m[keyField] === key);
  const other = keyField === "target" ? "source" : "target";
  if (idx === -1) {
    return [...list, keyField === "target" ? { source: value, target: key } : { source: key, target: value }];
  }
  return list.map((m, i) => (i === idx ? { ...m, [other]: value } : m));
}

export function describe(e: unknown): string {
  const err = e as { status?: number; message?: string };
  if (err?.status && err.message) {
    return `HTTP ${err.status}: ${err.message.slice(0, 300)}`;
  }
  return String(e);
}
