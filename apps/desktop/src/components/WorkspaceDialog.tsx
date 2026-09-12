/** Workspace modal: create / open / delete workspaces (no native prompt —
 *  window.prompt is unreliable inside the Tauri webview). */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useEditor } from "../state/editorStore";
import type { Workspace } from "../types";

export function WorkspaceDialog({ onClose, onOpened }: {
  onClose: () => void; onOpened: (ws: Workspace) => void;
}) {
  const editor = useEditor();
  const [list, setList] = useState<Workspace[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.listWorkspaces().then(setList).catch((e) => setError(String(e)));
  }, []);

  const create = async () => {
    if (!name.trim()) return;
    try {
      const ws = await api.createWorkspace(name.trim());
      onOpened(ws);
    } catch (e) {
      setError(describeError(e));
    }
  };

  return (
    <div className="overlay" onPointerDown={onClose}>
      <div className="modal" onPointerDown={(e) => e.stopPropagation()}>
        <div className="modal-title">WORKSPACES</div>
        <div className="ws-create">
          <input autoFocus placeholder="Nombre del nuevo workspace" value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void create(); }} />
          <button className="btn-mini btn-primary" onClick={create}>Crear</button>
        </div>
        {error && <div className="error-note">{error}</div>}
        <div className="ws-list">
          {list.length === 0 && <div className="empty-line">Aún no hay workspaces.</div>}
          {list.map((ws) => (
            <div key={ws.id}
              className={`ws-row ${editor.state.workspace?.id === ws.id ? "ws-row-current" : ""}`}>
              <div className="ws-info" onClick={() => { onOpened(ws); }}>
                <strong>{ws.name}</strong>
                <span className="dim">{ws.id} · {ws.has_ui_document ? "con UI" : "vacío"} ·
                  {new Date(ws.updated_at).toLocaleString()}</span>
              </div>
              <button className="btn-mini btn-danger" title="Eliminar workspace"
                onClick={async () => {
                  try {
                    await api.deleteWorkspace(ws.id);
                    setList((l) => l.filter((w) => w.id !== ws.id));
                    if (editor.state.workspace?.id === ws.id) editor.setWorkspace(null);
                  } catch (e) { setError(describeError(e)); }
                }}>✕</button>
            </div>
          ))}
        </div>
        <div className="form-actions">
          <button className="btn-mini" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  );
}

function describeError(e: unknown): string {
  const err = e as { status?: number; message?: string };
  return err?.message ? `HTTP ${err.status ?? ""} ${err.message.slice(0, 300)}` : String(e);
}
