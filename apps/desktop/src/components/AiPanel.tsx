/** Panel IA / fondo (F6): héroes con IA (opcional, avisado) + fondo local. */
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useEditor } from "../state/editorStore";
import type { ImageRecord } from "../types";

const HERO_PRESETS = [
  "héroe tecnológico abstracto azul, líneas limpias, sin texto",
  "fondo degradado oscuro elegante para panel de control",
  "ilustración minimalista de productividad, tonos fríos",
  "textura suave futurista con partículas",
];

const LOCAL_OPS: { op: string; label: string; params?: Record<string, unknown> }[] = [
  { op: "blur", label: "Desenfocar", params: { sigma: 14 } },
  { op: "darken", label: "Oscurecer", params: { factor: 0.5 } },
  { op: "lighten", label: "Aclarar", params: { factor: 0.2 } },
  { op: "color", label: "Color sólido", params: { hex: "#101216" } },
  { op: "gradient", label: "Degradado", params: { from: "#0c0e13", to: "#1b2436" } },
];

export function AiPanel({ onClose, reference, onReferenceChange }: {
  onClose: () => void;
  reference: { id: string; width: number; height: number } | null;
  onReferenceChange: (img: { id: string; width: number; height: number }) => void;
}) {
  const editor = useEditor();
  const ws = editor.state.workspace;
  const [status, setStatus] = useState<{ configured: boolean; privacy: string; env_file?: string } | null>(null);
  const [prompt, setPrompt] = useState(HERO_PRESETS[0]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    void api.imagegenStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  const generate = async () => {
    if (!ws) return;
    setBusy("Generando…"); setError(null); setInfo(null);
    try {
      const r = await api.generateHero(ws.id, prompt);
      const rec: ImageRecord = r.image;
      const screen = editor.state.doc?.screen;
      const w = Math.min(rec.width, screen?.width ?? rec.width);
      const scale = w / rec.width;
      const h = rec.height * scale;
      const id = editor.addComponent("image", "screen", {
        x: 0, y: 0, width: Math.round(w), height: Math.round(h),
      });
      editor.updateComponent(id, {
        name: "hero-ia",
        styles: { src: api.referenceImageUrl(rec.id) },
        metadata: { confidence: 1, source: "ia" },
      });
      setInfo("Héroe insertado como componente imagen (puedes moverlo o cubrir el lienzo).");
      editor.select(id);
    } catch (e) {
      setError(String((e as { message?: string }).message ?? e));
    } finally { setBusy(null); }
  };

  const applyLocal = async (op: string, params?: Record<string, unknown>) => {
    if (!ws) return;
    setBusy("Aplicando…"); setError(null); setInfo(null);
    try {
      const r = await api.backgroundOp(ws.id, op, params ?? {}, reference?.id);
      onReferenceChange({ id: r.image.id, width: r.image.width, height: r.image.height });
      setInfo(`Fondo alterado (${op}) — 100% local, nada se ha enviado a la nube.`);
    } catch (e) {
      setError(String((e as { message?: string }).message ?? e));
    } finally { setBusy(null); }
  };

  return (
    <div className="overlay overlay-transparent" onPointerDown={onClose}>
      <div className="modal modal-small type-popover ai-panel" onPointerDown={(e) => e.stopPropagation()}>
        <div className="modal-title">IA Y FONDO</div>

        <div className="insp-label">HÉROES CON IA {status && (
          status.configured
            ? <span className="status status-confirmed">proveedor configurado</span>
            : <span className="status status-broken">sin configurar</span>
        )}</div>
        <textarea className="ai-prompt" rows={3} value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe la imagen que quieres generar…" />
        <div className="ai-presets">
          {HERO_PRESETS.map((p) => (
            <button key={p} className="btn-mini" title={p}
              onClick={() => setPrompt(p)}>{p.slice(0, 26)}…</button>
          ))}
        </div>
        {status?.configured && (
          <p className="hint">⚠ {status.privacy}</p>
        )}
        {status && !status.configured && (
          <div className="hint">
            Sin proveedor configurado. Crea el archivo
            <code> {status.env_file ?? "%LOCALAPPDATA%/UIBinder/.env"} </code>
            con tres líneas:
            <pre className="env-example">{`UIBINDER_IMAGEGEN_BASE_URL=https://.../v1
UIBINDER_IMAGEGEN_MODEL=nombre-del-modelo
UIBINDER_IMAGEGEN_API_KEY=tu-clave`}</pre>
            y reinicia la app. Las herramientas de fondo locales siguen funcionando sin nube.
          </div>
        )}
        <button className="btn btn-primary btn-block" disabled={!ws || !!busy || !status?.configured}
          onClick={() => void generate()}>
          {busy === "Generando…" ? busy : "Generar héroe e insertarlo"}
        </button>

        <div className="insp-label">FONDO — HERRAMIENTAS LOCALES (SIN NUBE)</div>
        <div className="ai-presets">
          {LOCAL_OPS.map((o) => (
            <button key={o.op} className="btn-mini" disabled={!ws || !!busy}
              onClick={() => void applyLocal(o.op, o.params)}>{o.label}</button>
          ))}
        </div>
        <p className="hint">Se aplican sobre la imagen de referencia actual y crean una "
          nueva versión (puedes volver con una nueva operación).</p>

        {error && <div className="error-note">{error}</div>}
        {info && <div className="ok-note">{info}</div>}
        <div className="form-actions">
          <button className="btn-mini" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  );
}
