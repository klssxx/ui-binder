/** Mirror of backend/schema/ui_schema v1 — kept compatible via tests. */

export type ComponentType =
  | "screen" | "container" | "panel" | "card" | "text" | "heading" | "button"
  | "input" | "textarea" | "select" | "checkbox" | "radio" | "image" | "icon"
  | "table" | "chart" | "tabs" | "sidebar" | "navbar" | "modal" | "divider" | "custom";

export const COMPONENT_TYPES: ComponentType[] = [
  "container", "panel", "card", "text", "heading", "button", "input", "textarea",
  "select", "checkbox", "radio", "image", "icon", "table", "chart", "tabs",
  "sidebar", "navbar", "modal", "divider", "custom",
];

export interface BBox { x: number; y: number; width: number; height: number; }

export interface UIComponent {
  id: string;
  type: ComponentType;
  name: string;
  parent_id: string | null;
  children: string[];
  bbox: BBox;
  text: string | null;
  styles: Record<string, unknown>;
  states: Record<string, unknown>;
  events: Record<string, unknown>;
  bindings: string[];
  metadata: Record<string, unknown>;
}

export interface Screen {
  id: string;
  width: number;
  height: number;
  background: string | null;
  preset: string | null;
}

export interface StrokePoint { x: number; y: number; }
export interface Stroke {
  id: string;
  tool: "pencil" | "rect" | "ellipse" | "line" | "arrow";
  color: string;
  width: number;
  opacity: number;
  points: StrokePoint[];
}

export interface UIDocument {
  ui_schema_version: number;
  screen: Screen;
  components: UIComponent[];
  strokes?: Stroke[];
  metadata: Record<string, unknown>;
}

export interface Workspace {
  id: string;
  name: string;
  status: string;
  notes: string;
  created_at: string;
  updated_at: string;
  has_ui_document?: boolean;
  ui_version?: number;
}

export interface ImageRecord {
  id: string;
  workspace_id: string;
  role: string;
  filename: string;
  path: string;
  width: number;
  height: number;
  size_bytes: number;
  format: string;
  sha256: string;
  created_at: string;
}

export interface Param { name: string; type: string; required: boolean; description: string; }

export interface Capability {
  capability_id: string;
  kind: string;
  name: string;
  qualified_name: string;
  description: string;
  inputs: Param[];
  outputs: Param[];
  side_effects: string[];
  origin_file: string;
  origin_line: number;
  framework: string;
  http_method: string;
  http_path: string;
  dependencies: string[];
  legacy: boolean;
  confidence: number;
}

export interface Mapping { source: string; target: string; transform?: string | null; note?: string | null; }

export interface Binding {
  binding_id: string;
  component_id: string;
  event: string;
  target_capability: string;
  input_mapping: Mapping[];
  output_mapping: Mapping[];
  loading_mapping: string;
  error_mapping: string;
  transformations: string[];
  confidence: number;
  status: "SUGGESTED" | "CONFIRMED" | "BROKEN" | "UNKNOWN";
  rationale: string[];
  target_name?: string | null;
  target_broken?: boolean;
}

export interface Suggestion {
  capability_id: string;
  score: number;
  rationale: string[];
  inputs: Param[];
  outputs: Param[];
  side_effects: string[];
}

export interface OrphanReport {
  capabilities_detected: number;
  bound: number;
  unbound: number;
  broken: number;
  unknown: number;
  legacy: number;
  policy: string;
  detail: {
    BOUND: SlimCap[]; UNBOUND: SlimCap[]; BROKEN: SlimCap[];
    UNKNOWN: SlimCap[]; LEGACY: SlimCap[];
  };
}

export interface SlimCap {
  capability_id: string; kind: string; name: string;
  qualified_name: string; origin_file: string; confidence: number;
}

export interface VerifyReport {
  visual_fidelity: number | null;
  functional_coverage: number;
  broken_bindings: number;
  unbound_capabilities: number;
  orphan: OrphanReport;
  binding_checks: { binding_id: string; status: string | null; problems: string[] }[];
  scores: { visual_fidelity: number | null; functional_coverage: number; note: string };
}

export interface DiffMetrics {
  image_size: number[];
  pixel_diff: number;
  ssim: number;
  edge_ssim: number;
  visual_fidelity_score: number;
  worst_regions: { id: string; type: string; pixel_diff: number }[];
  region_count: number;
  geometry: { available: boolean; matched?: number; mean_position_delta_px?: number; mean_dimension_delta_px?: number };
  formula: string;
}

export interface LogEntry { ts: string; level: string; message: string; context: Record<string, unknown>; }
export interface TraceEvent { ts: string; event: string; component?: string; capability?: string; network?: Record<string, unknown>; result?: string; error?: string; }

export interface ProjectInfo {
  id: string;
  workspace_id: string;
  path: string;
  read_only: boolean;
  frameworks: string[];
  languages: string[];
  entrypoints: string[];
  summary: Record<string, unknown>;
  files?: { rel_path: string; language: string }[];
}

export interface Health {
  status: string;
  app: string;
  version: string;
  database: { state: string; path: string };
  vision_provider: { available: string[]; configured: string; remote_configured: boolean };
  workspaces: { count: number };
}

export interface SpecItem {
  id: string;
  name: string;
  description: string;
  type: ComponentType;
  mounted_component_id?: string | null;
}

export interface OcrLine {
  text: string;
  bbox: BBox;
  confidence: number;
  color: string;
  fontSize: number;
}
