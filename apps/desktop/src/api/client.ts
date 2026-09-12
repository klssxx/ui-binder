/** Typed API client. In dev, Vite proxies /api to the backend; in Tauri the
 *  backend URL defaults to http://127.0.0.1:8765 (VITE_API_BASE overrides). */
import type {
  Binding, Capability, DiffMetrics, Health, ImageRecord, LogEntry, Mapping,
  OrphanReport, ProjectInfo, Suggestion, TraceEvent, UIDocument, VerifyReport,
  Workspace,
} from "../types";

const BASE: string =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE ?? "";

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try { detail = await res.json(); } catch { /* keep statusText */ }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => call<Health>("/health"),

  listWorkspaces: () =>
    call<{ workspaces: Workspace[] }>("/api/workspaces").then((r) => r.workspaces),
  createWorkspace: (name: string) =>
    call<Workspace>("/api/workspaces", { method: "POST", ...json({ name }) }),
  updateWorkspace: (id: string, patch: { name?: string; notes?: string }) =>
    call<Workspace>(`/api/workspaces/${id}`, { method: "PATCH", ...json(patch) }),
  deleteWorkspace: (id: string) =>
    call<void>(`/api/workspaces/${id}`, { method: "DELETE" }),

  uploadImage: (wsId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return call<ImageRecord>(`/api/workspaces/${wsId}/images`, { method: "POST", body: form });
  },
  referenceImageUrl: (imageId: string) => `${BASE}/api/images/${imageId}/file`,

  analyzeUi: (wsId: string, provider = "heuristic") =>
    call<{ notes: Record<string, unknown>; components: number }>(
      `/api/workspaces/${wsId}/analyze-ui`, { method: "POST", ...json({ provider }) }),

  getUi: (wsId: string) => call<UIDocument>(`/api/workspaces/${wsId}/ui`),
  saveUi: (wsId: string, document: UIDocument) =>
    call<{ saved: boolean; components: number; version: number }>(
      `/api/workspaces/${wsId}/ui`, { method: "PUT", ...json({ document }) }),

  importProject: (wsId: string, path: string) =>
    call<{ frameworks: string[]; file_count: number }>(
      `/api/workspaces/${wsId}/import-project`, { method: "POST", ...json({ path }) }),
  getProject: (wsId: string) => call<ProjectInfo>(`/api/workspaces/${wsId}/project`),
  analyzeProject: (wsId: string) =>
    call<{ capabilities: number; edges: number }>(
      `/api/workspaces/${wsId}/analyze-project`, { method: "POST" }),

  capabilities: (wsId: string) =>
    call<{ capabilities: Capability[]; total: number }>(`/api/workspaces/${wsId}/capabilities`)
      .then((r) => r.capabilities),
  setLegacy: (wsId: string, capId: string, legacy: boolean) =>
    call<Capability>(`/api/workspaces/${wsId}/capabilities/${capId}`,
      { method: "PATCH", ...json({ legacy }) }),

  suggest: (wsId: string, componentId: string) =>
    call<{ suggestions: Suggestion[] }>(`/api/workspaces/${wsId}/suggest-bindings`,
      { method: "POST", ...json({ component_id: componentId }) }),

  bindings: (wsId: string) =>
    call<{ bindings: Binding[] }>(`/api/workspaces/${wsId}/bindings`).then((r) => r.bindings),
  createBinding: (wsId: string, b: Partial<Binding> & { component_id: string; target_capability: string }) =>
    call<Binding>(`/api/workspaces/${wsId}/bindings`, { method: "POST", ...json(b) }),
  updateBinding: (wsId: string, id: string, patch: Partial<Binding>) =>
    call<Binding>(`/api/workspaces/${wsId}/bindings/${id}`, { method: "PATCH", ...json(patch) }),
  deleteBinding: (wsId: string, id: string) =>
    call<void>(`/api/workspaces/${wsId}/bindings/${id}`, { method: "DELETE" }),
  verifyBindings: (wsId: string) =>
    call<{ results: { binding_id: string; status: string | null; problems: string[] }[] }>(
      `/api/workspaces/${wsId}/bindings/verify`, { method: "POST" }),

  verify: (wsId: string) =>
    call<VerifyReport>(`/api/workspaces/${wsId}/verify`, { method: "POST" }),
  visualDiff: (wsId: string, rendered: File) => {
    const form = new FormData();
    form.append("rendered", rendered);
    return call<{ diff_id: string; metrics: DiffMetrics }>(
      `/api/workspaces/${wsId}/visual-diff`, { method: "POST", body: form });
  },

  exportPlan: (wsId: string) =>
    call<Record<string, unknown>>(`/api/workspaces/${wsId}/export-plan`),
  exportProject: (wsId: string, targetDir: string) =>
    call<Record<string, unknown>>(`/api/workspaces/${wsId}/export`,
      { method: "POST", ...json({ target_dir: targetDir }) }),

  search: (wsId: string, q: string) =>
    call<Record<string, unknown>>(`/api/workspaces/${wsId}/search?q=${encodeURIComponent(q)}`),

  traceEvents: (wsId: string) =>
    call<{ events: TraceEvent[] }>(`/api/workspaces/${wsId}/trace/events`).then((r) => r.events),
  addTraceEvent: (wsId: string, event: Partial<TraceEvent>) =>
    call<{ recorded: boolean }>(`/api/workspaces/${wsId}/trace/events`,
      { method: "POST", ...json(event) }),

  logs: (wsId: string) =>
    call<{ logs: LogEntry[] }>(`/api/workspaces/${wsId}/logs`).then((r) => r.logs),

  snapshot: (wsId: string, label: string) =>
    call<{ id: string }>(`/api/workspaces/${wsId}/snapshots`, { method: "POST", ...json({ label }) }),
  snapshots: (wsId: string) =>
    call<{ snapshots: { id: string; label: string; created_at: string }[] }>(
      `/api/workspaces/${wsId}/snapshots`).then((r) => r.snapshots),
  restoreSnapshot: (wsId: string, id: string) =>
    call<{ restored: boolean }>(`/api/workspaces/${wsId}/snapshots/${id}/restore`, { method: "POST" }),
};

export type { Mapping };
