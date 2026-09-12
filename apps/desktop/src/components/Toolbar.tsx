/** Top toolbar: the main actions of the tool (directive §60). */
import { useRef } from "react";
import { useEditor } from "../state/editorStore";

export interface ToolbarActions {
  newWorkspace(): void;
  switchWorkspace(): void;
  importScreenshot(file: File): void;
  analyzeUi(): void;
  importProject(): void;
  analyzeProject(): void;
  verify(): void;
  exportProject(): void;
  save(): void;
  snapshot(): void;
  togglePreview(): void;
  openPalette(): void;
  openSearch(): void;
}

export function Toolbar({ actions, busy, health }: {
  actions: ToolbarActions; busy: string | null; health: "ok" | "degraded" | "checking";
}) {
  const editor = useEditor();
  const fileRef = useRef<HTMLInputElement | null>(null);
  const ws = editor.state.workspace;

  return (
    <div className="toolbar">
      <div className="toolbar-brand">
        <span className="logo">◈</span>
        <span className="brand"><strong>UIEDITION</strong></span>
        <span className={`health health-${health}`} title={health}>●</span>
      </div>

      <div className="toolbar-ws">
        {ws ? <><span className="ws-name">{ws.name}</span>
          <span className="ws-dirty">{editor.state.dirty ? "● sin guardar" : ""}</span></>
          : <span className="dim">sin workspace</span>}
      </div>

      <div className="toolbar-actions">
        <ToolBtn label="Nuevo workspace" onClick={actions.newWorkspace} />
        <ToolBtn label="Importar imagen" onClick={() => fileRef.current?.click()} />
        <ToolBtn label="Analizar UI" onClick={actions.analyzeUi} primary />
        <ToolBtn label="Importar proyecto" onClick={actions.importProject} />
        <ToolBtn label="Analizar proyecto" onClick={actions.analyzeProject} primary />
        <ToolBtn label="Guardar" onClick={actions.save} />
        <ToolBtn label="Verificar" onClick={actions.verify} />
        <ToolBtn label="Previsualizar" onClick={actions.togglePreview} />
        <ToolBtn label="Exportar" onClick={actions.exportProject} />
      </div>

      <div className="toolbar-right">
        {busy && <span className="busy">{busy}…</span>}
        <button className="btn-mini" title="Buscar (Ctrl+Mayús+F)" onClick={actions.openSearch}>⌕</button>
        <button className="btn-mini" title="Paleta de comandos (Ctrl+K)" onClick={actions.openPalette}>⌘K</button>
      </div>

      <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) actions.importScreenshot(f);
          e.target.value = "";
        }} />
    </div>
  );
}

function ToolBtn({ label, onClick, primary }: { label: string; onClick: () => void; primary?: boolean }) {
  return (
    <button className={`tool-btn ${primary ? "tool-btn-primary" : ""}`} onClick={onClick}>
      {label}
    </button>
  );
}
