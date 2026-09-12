/** Status bar: always-visible counters (directive §61). */
import { useEditor } from "../state/editorStore";

export function StatusBar({ capabilities, bindings, broken, unbound, fidelity, coverage }: {
  capabilities: number; bindings: number; broken: number; unbound: number;
  fidelity: number | null; coverage: number | null;
}) {
  const editor = useEditor();
  const components = editor.state.doc?.components.length ?? 0;
  return (
    <div className="statusbar">
      <span>Componentes: <strong>{components}</strong></span>
      <span>Capacidades: <strong>{capabilities}</strong></span>
      <span>Bindings: <strong>{bindings}</strong></span>
      <span className={broken > 0 ? "bad" : ""}>Rotos: <strong>{broken}</strong></span>
      <span className={unbound > 0 ? "warn" : ""}>Sin vincular: <strong>{unbound}</strong></span>
      <span>Fidelidad visual: <strong>{fidelity != null ? `${fidelity}%` : "—"}</strong></span>
      <span>Cobertura: <strong>{coverage != null ? `${coverage}%` : "—"}</strong></span>
      <span className="spacer" />
      <span className="dim">schema v{editor.state.doc?.ui_schema_version ?? 1} ·
        v{editor.state.lastSavedVersion}</span>
    </div>
  );
}
