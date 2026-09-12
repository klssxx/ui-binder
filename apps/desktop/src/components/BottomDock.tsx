/** BOTTOM dock: Trace | Bindings | Capabilities | Orphans | Diff | Logs. */
import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { SpecTab } from "./SpecTab";
import { useEditor } from "../state/editorStore";
import type {
  Binding, Capability, DiffMetrics, LogEntry, OrphanReport, TraceEvent, VerifyReport,
} from "../types";

export type DockTab = "trace" | "bindings" | "capabilities" | "orphans" | "diff" | "logs" | "spec";
const TABS: DockTab[] = ["spec", "trace", "bindings", "capabilities", "orphans", "diff", "logs"];
const TAB_LABEL: Record<DockTab, string> = { spec: "SPEC", trace: "TRAZA", bindings: "BINDINGS", capabilities: "CAPACIDADES", orphans: "HUÉRFANOS", diff: "COMPARACIÓN", logs: "LOGS" };

export function BottomDock({ tab, setTab, onFidelity }: {
  tab: DockTab; setTab: (t: DockTab) => void;
  onFidelity?: (v: number | null) => void;
}) {
  return (
    <div className="dock">
      <div className="dock-tabs">
        {TABS.map((t) => (
          <button key={t} className={`dock-tab ${tab === t ? "dock-tab-active" : ""}`}
            onClick={() => setTab(t)}>{TAB_LABEL[t]}</button>
        ))}
      </div>
      <div className="dock-body">
        {tab === "spec" && <SpecTab />}
        {tab === "trace" && <TraceTab />}
        {tab === "bindings" && <BindingsTab />}
        {tab === "capabilities" && <CapabilitiesTab />}
        {tab === "orphans" && <OrphansTab onCoverage={onFidelity} />}
        {tab === "diff" && <DiffTab />}
        {tab === "logs" && <LogsTab />}
      </div>
    </div>
  );
}

function useWorkspaceId(): string | null {
  return useEditor().state.workspace?.id ?? null;
}

function TraceTab() {
  const wsId = useWorkspaceId();
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [note] = useState(
    "TRACE MODE (parcial): almacenamiento y consulta reales. La instrumentación automática" +
    " del navegador (Playwright) está planificada — ver feature registry.");

  const load = useCallback(async () => {
    if (!wsId) return;
    setEvents(await api.traceEvents(wsId));
  }, [wsId]);

  useEffect(() => { void load(); }, [load]);
  if (!wsId) return <EmptyLine>Abre un workspace.</EmptyLine>;
  return (
    <div className="tab-col">
      <div className="tab-note">{note}</div>
      <button className="btn-mini" onClick={load}>Recargar</button>
      {events.length === 0 && <EmptyLine>Sin eventos de traza registrados.</EmptyLine>}
      {events.map((e, i) => (
        <div key={i} className="trace-line">
          <span className="mono dim">{e.ts}</span>
          <span className="trace-event">{e.event}</span>
          {e.component && <code>{e.component}</code>}
          {e.capability && <code>{e.capability}</code>}
          {e.error && <span className="error-note">{e.error}</span>}
        </div>
      ))}
    </div>
  );
}

function BindingsTab() {
  const wsId = useWorkspaceId();
  const [bindings, setBindings] = useState<Binding[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!wsId) return;
    try {
      setBindings(await api.bindings(wsId));
    } catch (e) { setError(String(e)); }
  }, [wsId]);
  useEffect(() => { void load(); }, [load]);

  if (!wsId) return <EmptyLine>Abre un workspace.</EmptyLine>;
  if (error) return <EmptyLine>{error}</EmptyLine>;
  if (bindings.length === 0) return <EmptyLine>Sin bindings. Selecciona un botón y usa SMART BIND en el inspector.</EmptyLine>;
  return (
    <table className="data-table">
      <thead><tr><th>ID</th><th>Componente</th><th>Evento</th><th>Target</th><th>Conf</th><th>Status</th></tr></thead>
      <tbody>
        {bindings.map((b) => (
          <tr key={b.binding_id} className={b.status === "BROKEN" ? "row-broken" : ""}>
            <td className="mono dim">{b.binding_id.slice(0, 16)}</td>
            <td className="mono">{b.component_id}</td>
            <td>{b.event}</td>
            <td>{b.target_name ?? b.target_capability}</td>
            <td>{Math.round(b.confidence * 100)}%</td>
            <td><span className={`status status-${b.status.toLowerCase()}`}>{b.status}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CapabilitiesTab() {
  const wsId = useWorkspaceId();
  const [caps, setCaps] = useState<Capability[]>([]);
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    if (!wsId) return;
    setCaps(await api.capabilities(wsId));
  }, [wsId]);
  useEffect(() => { void load(); }, [load]);

  if (!wsId) return <EmptyLine>Abre un workspace.</EmptyLine>;
  const shown = caps.filter((c) =>
    !q || c.name.toLowerCase().includes(q.toLowerCase())
    || c.qualified_name.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="tab-col">
      <div className="tab-toolbar">
        <input className="tree-filter" placeholder="filtrar capacidad…" value={q}
          onChange={(e) => setQ(e.target.value)} />
        <span className="dim">{caps.length} capacidades detectadas</span>
        <button className="btn-mini" onClick={load}>Recargar</button>
      </div>
      <table className="data-table">
        <thead><tr><th>Tipo</th><th>Nombre</th><th>Origen</th><th>HTTP</th><th>Conf</th><th>Estado</th></tr></thead>
        <tbody>
          {shown.map((c) => (
            <tr key={c.capability_id}>
              <td><span className="kind kind-{c.kind}">{c.kind}</span></td>
              <td title={c.description}>{c.name}</td>
              <td className="mono dim">{c.origin_file}:{c.origin_line}</td>
              <td className="mono">{c.http_method ? `${c.http_method} ${c.http_path}` : ""}</td>
              <td>{Math.round(c.confidence * 100)}%</td>
              <td>{c.legacy ? "LEGACY" : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {caps.length === 0 && <EmptyLine>Sin capacidades. IMPORTAR PROYECTO → ANALIZAR PROYECTO.</EmptyLine>}
    </div>
  );
}

function OrphansTab({ onCoverage }: { onCoverage?: (v: number | null) => void }) {
  const wsId = useWorkspaceId();
  const [report, setReport] = useState<VerifyReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    if (!wsId) return;
    setBusy(true); setError(null);
    try {
      const r = await api.verify(wsId);
      setReport(r);
      onCoverage?.(r.scores.functional_coverage);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }, [wsId, onCoverage]);

  useEffect(() => { void run(); }, [run]);

  if (!wsId) return <EmptyLine>Abre un workspace.</EmptyLine>;
  if (error) return <EmptyLine>{error}</EmptyLine>;
  if (!report) return <EmptyLine>{busy ? "Verificando…" : "Pulsa VERIFICAR en la barra superior."}</EmptyLine>;
  const o = report.orphan;
  return (
    <div className="tab-col">
      <div className="coverage-strip">
        <Metric label="Detectadas" value={o.capabilities_detected} />
        <Metric label="Vinculadas" value={o.bound} tone="good" />
        <Metric label="Sin vincular" value={o.unbound} tone="warn" />
        <Metric label="Rotas" value={o.broken} tone={o.broken ? "bad" : undefined} />
        <Metric label="Desconocidas" value={o.unknown} />
        <Metric label="Legado" value={o.legacy} />
        <Metric label="Cobertura funcional" value={`${report.scores.functional_coverage}%`} tone="good" />
        <Metric label="Fidelidad visual" value={report.scores.visual_fidelity != null
          ? `${report.scores.visual_fidelity}%` : "—"} />
        <button className="btn-mini" disabled={busy} onClick={run}>Re-verificar</button>
      </div>
      <div className="tab-note">{o.policy}</div>
      {(["UNBOUND", "BROKEN", "UNKNOWN", "LEGACY"] as const).map((group) =>
        o.detail[group].length > 0 && (
          <div key={group} className="orphan-group">
            <div className="insp-label">{group} ({o.detail[group].length})</div>
            {o.detail[group].map((c) => (
              <div key={c.capability_id} className="orphan-line">
                <code>{c.name}</code>
                <span className="dim">{c.qualified_name}</span>
              </div>
            ))}
          </div>
        ))}
    </div>
  );
}

function DiffTab() {
  const wsId = useWorkspaceId();
  const editor = useEditor();
  const [metrics, setMetrics] = useState<DiffMetrics | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = async (file: File) => {
    if (!wsId) return;
    setBusy(true); setError(null);
    try {
      const res = await api.visualDiff(wsId, file);
      setMetrics(res.metrics);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };

  if (!wsId) return <EmptyLine>Abre un workspace.</EmptyLine>;
  return (
    <div className="tab-col">
      <div className="tab-toolbar">
        <label className="btn-mini btn-primary">
          {busy ? "Calculando…" : "Subir screenshot renderizado"}
          <input type="file" accept="image/png,image/jpeg,image/webp" hidden
            onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])} />
        </label>
        <span className="dim">Compara la referencia con el render real → Visual Fidelity Score</span>
      </div>
      {error && <div className="error-note">{error}</div>}
      {metrics && (
        <div className="diff-results">
          <div className="big-score">{metrics.visual_fidelity_score}%<span>fidelidad visual</span></div>
          <div className="diff-metrics">
            <div>diferencia de píxeles: {(metrics.pixel_diff * 100).toFixed(2)}%</div>
            <div>SSIM: {metrics.ssim.toFixed(4)}</div>
            <div>edge SSIM: {metrics.edge_ssim.toFixed(4)}</div>
            <div>regiones: {metrics.region_count}</div>
            {metrics.geometry.available && (
              <div>Δposición media: {metrics.geometry.mean_position_delta_px}px ·
                Δdimensión media: {metrics.geometry.mean_dimension_delta_px}px</div>
            )}
            <div className="dim">{metrics.formula}</div>
          </div>
          {metrics.worst_regions.length > 0 && (
            <table className="data-table">
              <thead><tr><th>Componente</th><th>Tipo</th><th>pixel diff</th></tr></thead>
              <tbody>
                {metrics.worst_regions.map((r) => (
                  <tr key={r.id} className="clickable" onClick={() => editor.select(r.id)}>
                    <td className="mono">{r.id}</td><td>{r.type}</td>
                    <td>{(r.pixel_diff * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      {!metrics && !busy && <EmptyLine>Sin comparación aún. Exporta, renderiza y sube el screenshot.</EmptyLine>}
    </div>
  );
}

function LogsTab() {
  const wsId = useWorkspaceId();
  const [logs, setLogs] = useState<LogEntry[]>([]);

  const load = useCallback(async () => {
    if (!wsId) return;
    setLogs(await api.logs(wsId));
  }, [wsId]);
  useEffect(() => { void load(); }, [load]);

  if (!wsId) return <EmptyLine>Abre un workspace.</EmptyLine>;
  return (
    <div className="tab-col">
      <div className="tab-toolbar">
        <button className="btn-mini" onClick={load}>Recargar</button>
        <span className="dim">{logs.length} entradas</span>
      </div>
      {logs.map((l, i) => (
        <div key={i} className={`log-line log-${l.level.toLowerCase()}`}>
          <span className="mono dim">{l.ts}</span>
          <span className="log-level">{l.level}</span>
          <span>{l.message}</span>
        </div>
      ))}
      {logs.length === 0 && <EmptyLine>Sin logs todavía.</EmptyLine>}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className={`metric ${tone ?? ""}`}>
      <span className="metric-value">{value}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}

function EmptyLine({ children }: { children: React.ReactNode }) {
  return <div className="empty-line dim">{children}</div>;
}
