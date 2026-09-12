/** Ctrl+K command palette + global search overlay. */
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useEditor } from "../state/editorStore";
import type { ToolbarActions } from "./Toolbar";

interface Command { id: string; label: string; hint?: string; run: () => void; }

export function CommandPalette({ actions, onClose }: { actions: ToolbarActions; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [index, setIndex] = useState(0);
  const editor = useEditor();

  const commands = useMemo<Command[]>(() => [
    { id: "import-screenshot", label: "Import screenshot", hint: "imagen de referencia",
      run: () => (document.querySelector<HTMLInputElement>(".toolbar input[type=file]")?.click()) },
    { id: "analyze-ui", label: "Analyze UI", hint: "reconstruir desde screenshot", run: actions.analyzeUi },
    { id: "import-project", label: "Import project", hint: "ruta del proyecto externo", run: actions.importProject },
    { id: "analyze-project", label: "Analyze project", hint: "capabilities + grafo", run: actions.analyzeProject },
    { id: "check-bindings", label: "Check bindings", hint: "verificar targets rotos", run: async () => {
      const ws = editor.state.workspace;
      if (ws) await api.verifyBindings(ws.id);
    } },
    { id: "check-orphans", label: "Check orphans", hint: "cobertura funcional", run: actions.verify },
    { id: "visual-diff", label: "Run visual diff", hint: "subir render", run: actions.verify },
    { id: "export", label: "Export project", hint: "directorio nuevo y vacío", run: actions.exportProject },
    { id: "save", label: "Save UI document", hint: "Ctrl+S", run: actions.save },
    { id: "snapshot", label: "Create snapshot", run: actions.snapshot },
    { id: "preview", label: "Toggle preview", run: actions.togglePreview },
    { id: "undo", label: "Undo", hint: "Ctrl+Z", run: editor.undo },
    { id: "redo", label: "Redo", hint: "Ctrl+Y", run: editor.redo },
    { id: "new-workspace", label: "New workspace", run: actions.newWorkspace },
    { id: "switch-workspace", label: "Switch workspace", run: actions.switchWorkspace },
  ], [actions, editor]);

  const filtered = commands.filter((c) =>
    !q || c.label.toLowerCase().includes(q.toLowerCase()));

  useEffect(() => { setIndex(0); }, [q]);

  const runAt = (i: number) => {
    const cmd = filtered[i];
    if (cmd) { onClose(); cmd.run(); }
  };

  return (
    <div className="overlay" onPointerDown={onClose}>
      <div className="palette" onPointerDown={(e) => e.stopPropagation()}>
        <input autoFocus className="palette-input" placeholder="Escribe un comando…"
          value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setIndex((i) => Math.min(i + 1, filtered.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setIndex((i) => Math.max(i - 1, 0)); }
            if (e.key === "Enter") runAt(index);
            if (e.key === "Escape") onClose();
          }} />
        <div className="palette-list">
          {filtered.map((c, i) => (
            <div key={c.id} className={`palette-item ${i === index ? "palette-item-active" : ""}`}
              onMouseEnter={() => setIndex(i)} onClick={() => runAt(i)}>
              <span>{c.label}</span>
              {c.hint && <span className="dim">{c.hint}</span>}
            </div>
          ))}
          {filtered.length === 0 && <div className="empty-line">Sin coincidencias</div>}
        </div>
      </div>
    </div>
  );
}

export function SearchOverlay({ onClose, onSelectComponent }: {
  onClose: () => void; onSelectComponent: (id: string) => void;
}) {
  const editor = useEditor();
  const ws = editor.state.workspace;
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Record<string, Array<Record<string, string>>> | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!ws || q.trim().length < 2) { setResults(null); return; }
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        setResults(await api.search(ws.id, q.trim()) as Record<string, Array<Record<string, string>>>);
      } finally { setBusy(false); }
    }, 250);
    return () => clearTimeout(t);
  }, [q, ws]);

  const groups: [string, string][] = [
    ["components", "UI"], ["capabilities", "Capabilities"], ["routes", "API"],
    ["bindings", "Bindings"], ["files", "Files"],
  ];

  return (
    <div className="overlay" onPointerDown={onClose}>
      <div className="palette palette-wide" onPointerDown={(e) => e.stopPropagation()}>
        <input autoFocus className="palette-input" placeholder="Buscar en todo: evaluate, generar, /api…"
          value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Escape") onClose(); }} />
        <div className="palette-list">
          {busy && <div className="empty-line">Buscando…</div>}
          {results && groups.map(([key, label]) => {
            const rows = results[key] ?? [];
            if (rows.length === 0) return null;
            return (
              <div key={key} className="search-group">
                <div className="insp-label">{label}</div>
                {rows.map((r, i) => (
                  <div key={i} className="palette-item clickable"
                    onClick={() => {
                      if (key === "components" && r.id) { onSelectComponent(r.id); }
                      onClose();
                    }}>
                    <span>{r.name ?? r.qualified_name ?? r.rel_path ?? r.binding_id ?? r.id}</span>
                    <span className="dim">{r.type ?? r.kind ?? r.status ?? r.language ?? ""}</span>
                  </div>
                ))}
              </div>
            );
          })}
          {results && groups.every(([key]) => (results[key] ?? []).length === 0) && (
            <div className="empty-line">Sin resultados para «{q}»</div>
          )}
        </div>
      </div>
    </div>
  );
}
