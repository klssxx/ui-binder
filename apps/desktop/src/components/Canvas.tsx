/** Lienzo: AST como nodos absolutos + imagen de referencia + herramientas
 *  (puntero / recuadro / lazo) + edición inline. El delta de arrastre vive en
 *  estado local; el AST se muta una sola vez al soltar (historia limpia). */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useEditor } from "../state/editorStore";
import type { BBox, OcrLine, Stroke, StrokePoint, UIComponent } from "../types";
import { StrokeLayer, strokeSvg } from "./StrokeLayer";
import { AiPanel } from "./AiPanel";

const TEXT_TYPES = new Set(["text", "heading", "button", "input", "textarea", "select"]);
const HANDLES = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];
const CONTAINER_TYPES = ["container", "panel", "card", "sidebar", "navbar", "modal", "tabs"];
const POPOVER_TYPES = ["button", "input", "textarea", "text", "heading", "panel", "card",
  "container", "image", "icon", "select", "checkbox", "radio", "table", "chart", "divider", "custom"];

export type Tool = "select" | "rect" | "lasso" | "pencil" | "eraser"
  | "shape-rect" | "shape-ellipse" | "shape-line" | "shape-arrow";

interface Selection {
  kind: "rect" | "lasso";
  x0: number; y0: number; x1: number; y1: number;
  points: { x: number; y: number }[];
}

interface DragState {
  mode: "move" | "resize";
  id: string;
  handle?: string;
  startX: number;
  startY: number;
  dx: number;
  dy: number;
  origin?: BBox;
}

export function liveResize(origin: BBox, handle: string, dx: number, dy: number): BBox {
  let { x, y, width, height } = origin;
  if (handle.includes("e")) width = Math.max(4, width + dx);
  if (handle.includes("s")) height = Math.max(4, height + dy);
  if (handle.includes("w")) { const w = Math.max(4, width - dx); x += width - w; width = w; }
  if (handle.includes("n")) { const h = Math.max(4, height - dy); y += height - h; height = h; }
  return { x, y, width, height };
}

export function Canvas({ reference, onReferenceChange }: {
  reference: { id: string; width: number; height: number } | null;
  onReferenceChange?: (img: { id: string; width: number; height: number }) => void;
}) {
  const editor = useEditor();
  const { doc } = editor.state;
  const referenceUrl = reference ? api.referenceImageUrl(reference.id) : null;
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showReference, setShowReference] = useState(true);
  const [tool, setTool] = useState<Tool>("select");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pending, setPending] = useState<{ bbox: BBox; lasso?: { x: number; y: number }[] } | null>(null);
  const [drawPoints, setDrawPoints] = useState<StrokePoint[] | null>(null);
  const [showAi, setShowAi] = useState(false);
  const [penColor, setPenColor] = useState("#4f8cff");
  const [penWidth, setPenWidth] = useState(4);
  const [palettePos, setPalettePos] = useState<{ x: number; y: number } | null>(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem("uibinder.palettePos") ?? "null");
      return parsed && typeof parsed.x === "number" && typeof parsed.y === "number" ? parsed : null;
    } catch { return null; }
  });
  const [paletteDragging, setPaletteDragging] = useState(false);
  const paletteOffset = useRef({ dx: 0, dy: 0 });
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [viewport, setViewport] = useState({ w: 1280, h: 800 });
  const panState = useRef<{ sx: number; sy: number; px: number; py: number } | null>(null);
  const [panning, setPanning] = useState(false);

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const measure = () => setViewport({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stageW = doc?.screen.width ?? reference?.width ?? 1280;
  const stageH = doc?.screen.height ?? reference?.height ?? 800;
  const allStrokes = doc?.strokes ?? [];

  const fitAll = useCallback(() => {
    const el = viewportRef.current;
    if (!el) return;
    const z = Math.min(1, (el.clientWidth - 64) / stageW, (el.clientHeight - 64) / stageH);
    setZoom(Math.max(0.15, Math.round(z * 100) / 100));
    setPan({ x: 0, y: 0 });
  }, [stageW, stageH]);

  useLayoutEffect(() => { fitAll(); }, [doc, stageW, stageH, fitAll]);

  /** Zoom centrado en una caja (selección terminada) — por transformación. */
  const zoomToBox = useCallback((b: BBox) => {
    const pad = 70;
    const z = Math.min(3, Math.max(0.2, Math.min(
      (viewport.w - pad * 2) / Math.max(b.width, 40),
      (viewport.h - pad * 2) / Math.max(b.height, 40))));
    const zz = Math.round(z * 100) / 100;
    setZoom(zz);
    setPan({
      x: viewport.w / 2 - (b.x + b.width / 2) * zz - (viewport.w - stageW * zz) / 2,
      y: viewport.h / 2 - (b.y + b.height / 2) * zz - (viewport.h - stageH * zz) / 2,
    });
  }, [viewport, stageW, stageH]);

  /** Al soltar una selección (recuadro o lazo), encuadra la zona para verla bien. */
  useEffect(() => {
    if (pending) zoomToBox(pending.bbox);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending]);

  // ---- paleta flotante: arrastre por el grip + memoria de posición
  const onGripDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault(); e.stopPropagation();
    const rect = (e.currentTarget as HTMLElement).parentElement!.getBoundingClientRect();
    paletteOffset.current = { dx: e.clientX - rect.left, dy: e.clientY - rect.top };
    setPalettePos((prev) => prev ?? { x: rect.left, y: rect.top });
    setPaletteDragging(true);
  }, []);

  useEffect(() => {
    if (!paletteDragging) return;
    const onMove = (e: PointerEvent) => {
      setPalettePos({
        x: Math.max(4, Math.min(e.clientX - paletteOffset.current.dx, window.innerWidth - 64)),
        y: Math.max(4, Math.min(e.clientY - paletteOffset.current.dy, window.innerHeight - 90)),
      });
    };
    const onUp = () => {
      setPaletteDragging(false);
      setPalettePos((p) => {
        if (p) { try { localStorage.setItem("uibinder.palettePos", JSON.stringify(p)); } catch { /* noop */ } }
        return p;
      });
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [paletteDragging]);

  const toStage = (e: React.PointerEvent | PointerEvent) => {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return { x: (e.clientX - rect.left) / zoom, y: (e.clientY - rect.top) / zoom };
  };

  const smallestContainer = (b: BBox): string | null => {
    const comps = editor.state.doc?.components ?? [];
    let best: string | null = null;
    let bestArea = Infinity;
    for (const c of comps) {
      const o = c.bbox;
      const contains = o.x - 2 <= b.x && o.y - 2 <= b.y
        && o.x + o.width + 2 >= b.x + b.width
        && o.y + o.height + 2 >= b.y + b.height;
      if (contains && CONTAINER_TYPES.includes(c.type) && o.width * o.height < bestArea) {
        best = c.id;
        bestArea = o.width * o.height;
      }
    }
    return best;
  };

  const isDrawTool = (tl: Tool) =>
    tl === "pencil" || tl === "shape-rect" || tl === "shape-ellipse"
    || tl === "shape-line" || tl === "shape-arrow";

  const finishDrawing = useCallback(() => {
    setDrawPoints((pts) => {
      if (pts && pts.length >= 2) {
        const toolMap: Record<string, Stroke["tool"]> = {
          "shape-rect": "rect", "shape-ellipse": "ellipse",
          "shape-line": "line", "shape-arrow": "arrow",
        };
        const strokeTool = toolMap[tool] ?? "pencil";
        const trimmed = strokeTool === "pencil" && pts.length < 3 ? null : pts;
        if (trimmed) {
          editor.addStroke({
            id: `stroke_${Date.now().toString(36)}`,
            tool: strokeTool, color: penColor, width: penWidth, opacity: 1,
            points: trimmed,
          });
        }
      }
      return null;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool, penColor, penWidth]);

  const eraseAt = (e: React.PointerEvent | PointerEvent) => {
    const p = toStage(e);
    editor.eraseStrokesNear(p.x, p.y, 14 / zoom + 4);
  };

  const finishSelection = useCallback(() => {
    setSelection((s) => {
      if (!s) return null;
      const x = Math.min(s.x0, s.x1);
      const y = Math.min(s.y0, s.y1);
      const width = Math.abs(s.x1 - s.x0);
      const height = Math.abs(s.y1 - s.y0);
      if (width >= 8 && height >= 8) {
        setPending({
          bbox: { x: Math.round(x), y: Math.round(y), width: Math.round(width), height: Math.round(height) },
          lasso: s.kind === "lasso" ? s.points.slice() : undefined,
        });
      }
      return null;
    });
  }, []);

  const commit = useCallback(() => {
    if (!drag) return;
    const c = editor.byId(drag.id);
    if (c) {
      if (drag.mode === "move" && (drag.dx !== 0 || drag.dy !== 0)) {
        editor.updateBBox(drag.id, {
          x: Math.round(c.bbox.x + drag.dx),
          y: Math.round(c.bbox.y + drag.dy),
        });
      } else if (drag.mode === "resize" && drag.origin && drag.handle) {
        const live = liveResize(drag.origin, drag.handle, drag.dx, drag.dy);
        editor.updateBBox(drag.id, {
          x: Math.round(live.x), y: Math.round(live.y),
          width: Math.max(4, Math.round(live.width)),
          height: Math.max(4, Math.round(live.height)),
        });
      }
    }
    setDrag(null);
  }, [drag, editor]);

  useEffect(() => {
    if (!selection) return;
    const onMove = (e: PointerEvent) => {
      const p = toStage(e);
      setSelection((s) => (s ? { ...s, x1: p.x, y1: p.y, points: [...s.points, p] } : s));
    };
    const onUp = () => finishSelection();
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection, zoom, finishSelection]);

  useEffect(() => {
    if (!drawPoints) return;
    const onMove = (e: PointerEvent) => {
      const p = toStage(e);
      setDrawPoints((pts) => {
        if (!pts) return pts;
        const last = pts[pts.length - 1];
        if (tool !== "pencil" || Math.hypot(p.x - last.x, p.y - last.y) > 2) {
          return tool === "pencil" ? [...pts, p] : [pts[0], p];
        }
        return pts;
      });
    };
    const onUp = () => finishDrawing();
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drawPoints, tool, zoom, finishDrawing]);

  useEffect(() => {
    if (tool !== "eraser") return;
    const onMove = (e: PointerEvent) => {
      if (e.buttons === 1) eraseAt(e);
    };
    window.addEventListener("pointermove", onMove);
    return () => window.removeEventListener("pointermove", onMove);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool, zoom]);

  // Rueda: zoom hacia el cursor (F8.5, pan libre por transformación).
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      const frameLeft = pan.x + (viewport.w - stageW * zoom) / 2;
      const frameTop = pan.y + (viewport.h - stageH * zoom) / 2;
      const contentX = (cx - frameLeft) / zoom;
      const contentY = (cy - frameTop) / zoom;
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      const next = Math.min(4, Math.max(0.1, Math.round(zoom * factor * 100) / 100));
      if (next === zoom) return;
      setZoom(next);
      setPan({
        x: (cx - contentX * next) - (viewport.w - stageW * next) / 2,
        y: (cy - contentY * next) - (viewport.h - stageH * next) / 2,
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoom, pan, stageW, stageH, viewport]);

  // Pan libre (F8.5): arrastrar el fondo mueve la vista en CUALQUIER dirección,
  // incluida la diagonal y con contenido más pequeño que el viewport.
  const isBackground = (target: EventTarget | null): boolean => {
    const el = target as HTMLElement | null;
    if (!el || !el.classList) return false;
    return el === viewportRef.current || el.classList.contains("stage-frame")
      || el.classList.contains("canvas-stage") || el.classList.contains("canvas-reference")
      || el.classList.contains("canvas-empty-overlay");
  };

  useEffect(() => {
    if (!panning) return;
    const start = panState.current;
    if (!start) return;
    const onMove = (e: PointerEvent) => {
      setPan({ x: start.px + (e.clientX - start.sx), y: start.py + (e.clientY - start.sy) });
    };
    const onUp = () => { setPanning(false); panState.current = null; };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [panning]);

  // Atajos de herramienta (F8): V seleccionar · R recuadro · L lazo · P lápiz · E borrador
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA"
        || target.tagName === "SELECT" || target.isContentEditable)) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const map: Record<string, Tool> = { v: "select", r: "rect", l: "lasso", p: "pencil", e: "eraser" };
      if (e.ctrlKey && e.key === "0") { e.preventDefault(); fitAll(); return; }
      const tool = map[e.key.toLowerCase()];
      if (tool) { setTool(tool); return; }
      if (e.key === "Escape") { setTool("select"); setSelection(null); setPending(null); setEditingId(null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!drag) return;
    const onMove = (e: PointerEvent) => {
      const dx = (e.clientX - drag.startX) / zoom;
      const dy = (e.clientY - drag.startY) / zoom;
      setDrag((d) => (d ? { ...d, dx, dy } : d));
    };
    const onUp = () => commit();
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [drag, zoom, commit]);

  const startSelection = (e: React.PointerEvent) => {
    if (tool === "select" || e.button !== 0) return;
    const p = toStage(e);
    if (isDrawTool(tool)) {
      setDrawPoints([p, p]);
      return;
    }
    if (tool === "eraser") {
      eraseAt(e);
      return;
    }
    setSelection({ kind: tool, x0: p.x, y0: p.y, x1: p.x, y1: p.y, points: [p] });
  };

  const selectionOverlay = selection && (
    selection.kind === "rect" || selection.points.length < 3 ? (
      <div className="selection-rect" style={{
        left: Math.min(selection.x0, selection.x1),
        top: Math.min(selection.y0, selection.y1),
        width: Math.abs(selection.x1 - selection.x0),
        height: Math.abs(selection.y1 - selection.y0),
      }} />
    ) : (
      <svg className="selection-lasso" style={{ left: 0, top: 0, width: stageW, height: stageH }}>
        <polygon points={selection.points.map((p) => `${p.x},${p.y}`).join(" ")}
          fill="rgba(79,140,255,0.12)" stroke="var(--accent)" strokeWidth="1.5" />
      </svg>
    )
  );

  const palette = (
    <div
      className={`tool-palette ${palettePos ? "palette-free" : ""} ${paletteDragging ? "palette-dragging" : ""}`}
      style={palettePos ? { left: palettePos.x, top: palettePos.y } : undefined}
      onPointerDown={(e) => e.stopPropagation()}
    >
      <div className="palette-grip" title="Arrastra para mover la paleta a cualquier lado"
        onPointerDown={onGripDown}>⠿</div>
      {([
        ["select", "▶", "Puntero: seleccionar y mover componentes"],
        ["rect", "▭", "Recuadro: selecciona un área y conviértela en componente"],
        ["lasso", "✎", "Lazo: selección de forma libre"],
      ] as [Tool, string, string][]).map(([tl, icon, title]) => (
        <button key={tl} className={`tool-palette-btn ${tool === tl ? "tool-palette-active" : ""}`}
          title={title} onClick={() => setTool(tl)}>{icon}</button>
      ))}
      <div className="tool-palette-sep" />
      {([
        ["pencil", "✏", "Lápiz: dibuja a mano alzada"],
        ["eraser", "⌫", "Borrador: arrastra sobre un trazo para eliminarlo"],
        ["shape-rect", "▭", "Rectángulo"],
        ["shape-ellipse", "◯", "Elipse"],
        ["shape-line", "／", "Línea"],
        ["shape-arrow", "→", "Flecha"],
      ] as [Tool, string, string][]).map(([tl, icon, title]) => (
        <button key={tl} className={`tool-palette-btn ${tool === tl ? "tool-palette-active" : ""}`}
          title={title} onClick={() => setTool(tl)}>{icon}</button>
      ))}
      <div className="tool-palette-sep" />
      <input type="color" className="tool-palette-color" value={penColor}
        title="Color del trazo" onChange={(e) => setPenColor(e.target.value)} />
      <select className="tool-palette-width" value={penWidth}
        title="Grosor del trazo" onChange={(e) => setPenWidth(Number(e.target.value))}>
        {[2, 4, 8, 14, 24].map((w) => <option key={w} value={w}>{w}px</option>)}
      </select>
      <button className="tool-palette-btn" title="Borrar todos los trazos"
        onClick={() => editor.clearStrokes()}>🗑</button>
      <div className="tool-palette-sep" />
      <button className="tool-palette-btn" title="IA y fondo: generar héroes o alterar el fondo"
        onClick={() => setShowAi(true)}>✨</button>
    </div>
  );

  const zoomBar = (
    <div className="canvas-zoom">
      <button className="ref-toggle" title="Volver al encuadre completo"
        onClick={(e) => { e.stopPropagation(); fitAll(); }}>ajustar</button>
      {Math.round(zoom * 100)}%
      {referenceUrl && (
        <button className={`ref-toggle ${showReference ? "ref-toggle-on" : ""}`}
          onClick={(e) => { e.stopPropagation(); setShowReference((v) => !v); }}
          title="Mostrar u ocultar la imagen de referencia como fondo">
          referencia
        </button>
      )}
    </div>
  );

  if (!doc) {
    return (
      <div className={`canvas-scroll ${tool === "select" ? "pan-ready" : ""} ${panning ? "panning" : ""}`}
      ref={viewportRef}
      onPointerDown={(e) => {
        editor.select(null); setEditingId(null);
        if (tool === "select" && isBackground(e.target)) {
          const el = viewportRef.current!;
          panState.current = { sx: e.clientX, sy: e.clientY, px: pan.x, py: pan.y };
          setPanning(true);
          return;
        }
        startSelection(e);
      }}>
        {palette}
        {zoomBar}
        <div className="stage-frame" style={{
          position: "absolute",
          left: pan.x + (viewport.w - stageW * zoom) / 2,
          top: pan.y + (viewport.h - stageH * zoom) / 2,
          width: stageW * zoom, height: stageH * zoom,
        }}>
        <div className="canvas-stage" ref={stageRef} style={{
          width: stageW, height: stageH, background: "#101216",
          transform: `scale(${zoom})`, transformOrigin: "top left",
        }}>
          {referenceUrl && showReference && (
            <img className="canvas-reference" src={referenceUrl}
              alt="imagen de referencia" draggable={false} style={{ opacity: 1 }} />
          )}
          {selectionOverlay}
          {drawPoints && (
            <svg className="strokes-layer" width={stageW} height={stageH}>
              {strokeSvg({
                id: "preview", tool: tool === "pencil" ? "pencil"
                  : tool === "shape-rect" ? "rect" : tool === "shape-ellipse" ? "ellipse"
                  : tool === "shape-arrow" ? "arrow" : "line",
                color: penColor, width: penWidth, opacity: 0.8, points: drawPoints,
              })}
            </svg>
          )}
          <StrokeLayer strokes={allStrokes} width={stageW} height={stageH} />
          <div className="canvas-empty-overlay">
            <h2>Imagen importada — sin reconstruir</h2>
            <p>Pulsa <strong>ANALIZAR UI</strong> para detectar componentes, o usa
              <strong> ▭ / ✎ </strong> para trazar los tuyos sobre la imagen.</p>
          </div>
        </div>
        </div>
        {showAi && (
          <AiPanel onClose={() => setShowAi(false)} reference={reference}
            onReferenceChange={(img) => onReferenceChange?.(img)} />
        )}
        {pending && (
          <TypePopover pending={pending} wsId={editor.state.workspace?.id ?? null}
            onReferenceChange={onReferenceChange} onCancel={() => setPending(null)}
            onCreate={(type) => {
              const id = editor.addComponent(type, "screen", pending.bbox);
              editor.updateComponent(id, {
                metadata: {
                  confidence: 1.0, source: "manual",
                  ...(pending.lasso ? { lasso: pending.lasso } : {}),
                },
              });
              setPending(null); editor.select(id); setTool("select");
            }} />
        )}
      </div>
    );
  }

  const liveBox = (c: UIComponent): BBox => {
    if (!drag || drag.id !== c.id) return c.bbox;
    if (drag.mode === "move") return { ...c.bbox, x: c.bbox.x + drag.dx, y: c.bbox.y + drag.dy };
    if (drag.origin && drag.handle) return liveResize(drag.origin, drag.handle, drag.dx, drag.dy);
    return c.bbox;
  };

  return (
    <div className={`canvas-scroll ${tool === "select" ? "pan-ready" : ""} ${panning ? "panning" : ""}`}
      ref={viewportRef}
      onPointerDown={(e) => {
        editor.select(null); setEditingId(null);
        if (tool === "select" && isBackground(e.target)) {
          const el = viewportRef.current!;
          panState.current = { sx: e.clientX, sy: e.clientY, px: pan.x, py: pan.y };
          setPanning(true);
          return;
        }
        startSelection(e);
      }}>
      {palette}
      {zoomBar}
      <div className="stage-frame" style={{
        position: "absolute",
        left: pan.x + (viewport.w - stageW * zoom) / 2,
        top: pan.y + (viewport.h - stageH * zoom) / 2,
        width: stageW * zoom, height: stageH * zoom,
      }}>
      <div className="canvas-stage" ref={stageRef} style={{
        width: stageW, height: stageH,
        background: doc.screen.background ?? "#101216",
        transform: `scale(${zoom})`, transformOrigin: "top left",
      }}>
        {referenceUrl && showReference && (
          <img className="canvas-reference" src={referenceUrl} alt="imagen de referencia" draggable={false} />
        )}
        {selectionOverlay}
        {drawPoints && (
          <svg className="strokes-layer" width={stageW} height={stageH}>
            {strokeSvg({
              id: "preview", tool: tool === "pencil" ? "pencil"
                : tool === "shape-rect" ? "rect" : tool === "shape-ellipse" ? "ellipse"
                : tool === "shape-arrow" ? "arrow" : "line",
              color: penColor, width: penWidth, opacity: 0.8, points: drawPoints,
            })}
          </svg>
        )}
        <StrokeLayer strokes={allStrokes} width={stageW} height={stageH} />
        {editor.childrenOf("screen").map((c) => (
          <CanvasNode key={c.id} component={c} liveBox={liveBox} editingId={editingId}
            setEditingId={setEditingId}
            onStartMove={(e, c2) => {
              if (tool !== "select") return;
              e.stopPropagation();
              editor.select(c2.id);
              setDrag({ mode: "move", id: c2.id, startX: e.clientX, startY: e.clientY, dx: 0, dy: 0 });
            }}
            onStartResize={(e, c2, handle) => {
              e.stopPropagation();
              setDrag({ mode: "resize", id: c2.id, handle, startX: e.clientX, startY: e.clientY,
                dx: 0, dy: 0, origin: { ...c2.bbox } });
            }} />
        ))}
      </div>
      </div>
      {showAi && (
        <AiPanel onClose={() => setShowAi(false)} reference={reference}
          onReferenceChange={(img) => onReferenceChange?.(img)} />
      )}
      {pending && (
        <TypePopover pending={pending} wsId={editor.state.workspace?.id ?? null}
            onReferenceChange={onReferenceChange} onCancel={() => setPending(null)}
          onCreate={(type) => {
            const parent = smallestContainer(pending.bbox);
            const id = editor.addComponent(type, parent ?? "screen", pending.bbox);
            editor.updateComponent(id, {
              metadata: {
                confidence: 1.0, source: "manual",
                ...(pending.lasso ? { lasso: pending.lasso } : {}),
              },
            });
            setPending(null); editor.select(id); setTool("select");
          }} />
      )}
    </div>
  );
}

function TypePopover({ pending, onCancel, onCreate, wsId, onReferenceChange }: {
  pending: { bbox: BBox; lasso?: { x: number; y: number }[] };
  onCancel: () => void;
  onCreate: (type: UIComponent["type"]) => void;
  wsId: string | null;
  onReferenceChange?: (img: { id: string; width: number; height: number }) => void;
}) {
  const editor = useEditor();
  const [type, setType] = useState<UIComponent["type"]>("button");
  const [ocrLines, setOcrLines] = useState<OcrLine[] | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [eraseToo, setEraseToo] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const readOcr = async () => {
    if (!wsId) return;
    setBusy("Leyendo texto…"); setError(null);
    try {
      const r = await api.ocrRead(wsId, pending.bbox);
      setOcrLines(r.lines);
      setPicked(new Set(r.lines.map((_, i) => i)));
    } catch (e) {
      setError(String((e as { message?: string }).message ?? e));
    } finally { setBusy(null); }
  };

  const createTextComponents = async () => {
    if (!ocrLines) return;
    const chosen = ocrLines.filter((_, i) => picked.has(i));
    for (const line of chosen) {
      const id = editor.addComponent(
        line.fontSize >= 26 ? "heading" : "text", "screen", line.bbox);
      editor.updateComponent(id, {
        text: line.text,
        styles: { color: line.color, fontSize: line.fontSize },
        metadata: { confidence: line.confidence, source: "ocr" },
      });
    }
    if (eraseToo && chosen.length > 0 && wsId) {
      setBusy("Borrando el original…");
      try {
        const r = await api.ocrErase(wsId, chosen.map((l) => l.bbox));
        onReferenceChange?.({ id: r.image.id, width: r.image.width, height: r.image.height });
      } catch (e) {
        setError(`Textos creados, pero el borrado falló: ${String((e as { message?: string }).message ?? e)}`);
      } finally { setBusy(null); }
    }
    onCancel();
  };

  return (
    <div className="overlay overlay-transparent" onPointerDown={onCancel}>
      <div className="modal modal-small type-popover" onPointerDown={(e) => e.stopPropagation()}>
        <div className="modal-title">CREAR COMPONENTE DE LA SELECCIÓN</div>
        <div className="kv"><span>Zona</span>
          <code>{Math.round(pending.bbox.width)}×{Math.round(pending.bbox.height)} px
            en ({Math.round(pending.bbox.x)}, {Math.round(pending.bbox.y)})
            {pending.lasso ? " · lazo libre" : " · recuadro"}</code>
        </div>

        {ocrLines === null ? (
          <>
            <label className="field"><span>Tipo</span>
              <select value={type} onChange={(e) => setType(e.target.value as UIComponent["type"])}>
                {POPOVER_TYPES.map((tp) => <option key={tp} value={tp}>{tp}</option>)}
              </select>
            </label>
            <button className="btn btn-secondary btn-block" disabled={!wsId || !!busy}
              onClick={() => void readOcr()}>
              {busy ?? "Leer el texto de esta zona (OCR)"}
            </button>
            {!wsId && <p className="hint">Abre un workspace para usar el OCR.</p>}
            <div className="form-actions">
              <button className="btn-mini btn-primary" onClick={() => onCreate(type)}>Crear</button>
              <button className="btn-mini" onClick={onCancel}>Cancelar</button>
            </div>
          </>
        ) : (
          <>
            <div className="insp-label">TEXTO ENCONTRADO ({ocrLines.length})</div>
            {ocrLines.length === 0 && (
              <p className="hint">El OCR no encontró texto en la zona. Vuelve atrás y crea el componente a mano.</p>
            )}
            {ocrLines.map((line, i) => (
              <label key={i} className="ocr-line">
                <input type="checkbox" checked={picked.has(i)}
                  onChange={(e) => setPicked((s) => {
                    const n = new Set(s);
                    if (e.target.checked) n.add(i); else n.delete(i);
                    return n;
                  })} />
                <span style={{ color: line.color }}>{line.text}</span>
                <span className="dim">{Math.round(line.confidence * 100)}% · {line.fontSize}px</span>
              </label>
            ))}
            {ocrLines.length > 0 && (
              <label className="ocr-line">
                <input type="checkbox" checked={eraseToo}
                  onChange={(e) => setEraseToo(e.target.checked)} />
                <span>Borrar el texto original de la imagen (inpainting)</span>
              </label>
            )}
            {error && <div className="error-note">{error}</div>}
            <div className="form-actions">
              <button className="btn-mini btn-primary" disabled={!!busy || picked.size === 0}
                onClick={() => void createTextComponents()}>
                {busy ?? `Crear ${picked.size} texto(s)`}
              </button>
              <button className="btn-mini" disabled={!!busy} onClick={() => setOcrLines(null)}>Atrás</button>
              <button className="btn-mini" onClick={onCancel}>Cancelar</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

interface NodeProps {
  component: UIComponent;
  liveBox: (c: UIComponent) => BBox;
  editingId: string | null;
  setEditingId: (id: string | null) => void;
  onStartMove: (e: React.PointerEvent, c: UIComponent) => void;
  onStartResize: (e: React.PointerEvent, c: UIComponent, handle: string) => void;
}

function CanvasNode({ component: c, liveBox, editingId, setEditingId, onStartMove, onStartResize }: NodeProps) {
  const editor = useEditor();
  const box = liveBox(c);
  const selected = editor.state.selectedId === c.id;
  const dragging = editor.state.selectedId === c.id && box !== c.bbox;
  const editing = editingId === c.id;

  const styles: React.CSSProperties = {
    left: box.x, top: box.y, width: box.width, height: box.height,
    background: typeof c.styles.background === "string" ? c.styles.background : undefined,
    color: typeof c.styles.color === "string" ? c.styles.color : undefined,
    fontSize: c.styles.fontSize ? Number(c.styles.fontSize) : undefined,
    fontFamily: typeof c.styles.fontFamily === "string" ? c.styles.fontFamily : undefined,
    fontWeight: c.styles.fontWeight != null ? Number(c.styles.fontWeight) : undefined,
    fontStyle: typeof c.styles.fontStyle === "string" ? c.styles.fontStyle : undefined,
    textAlign: typeof c.styles.textAlign === "string" ? c.styles.textAlign as React.CSSProperties["textAlign"] : undefined,
    textShadow: typeof c.styles.shadow === "string" ? c.styles.shadow : undefined,
    borderRadius: c.styles.radius ? Number(c.styles.radius) : undefined,
    opacity: c.styles.opacity != null ? Number(c.styles.opacity) : undefined,
  };

  return (
    <div
      className={`node node-${c.type} ${selected ? "node-selected" : ""} ${dragging ? "node-dragging" : ""}`}
      style={styles}
      data-uib-id={c.id}
      onPointerDown={(e) => { if (c.type !== "divider" && !editing) onStartMove(e, c); }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        if (TEXT_TYPES.has(c.type)) setEditingId(c.id);
      }}
      title={`${c.name} · ${c.type} · conf ${String(c.metadata.confidence ?? "?")}`}
    >
      {c.type === "image" && typeof c.styles.src === "string" && !editing && (
        <img src={c.styles.src} alt="" draggable={false}
          style={{ width: "100%", height: "100%", objectFit: "cover", pointerEvents: "none" }} />
      )}
      {editing ? (
        <input className="node-inline-edit" autoFocus defaultValue={c.text ?? ""}
          onPointerDown={(e) => e.stopPropagation()}
          onChange={(e) => editor.setText(c.id, e.target.value)}
          onBlur={() => setEditingId(null)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === "Escape") setEditingId(null);
            e.stopPropagation();
          }} />
      ) : (
        c.text && (
          <span className="node-text" style={{
            width: "100%", display: "block", overflow: "hidden",
            textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>{c.text}</span>
        )
      )}
      {c.bindings.length > 0 && (
        <span className="node-binding-dot" title={`${c.bindings.length} binding(s)`} />
      )}
      {editor.childrenOf(c.id).map((k) => (
        <CanvasNode key={k.id} component={k} liveBox={liveBox} editingId={editingId}
          setEditingId={setEditingId} onStartMove={onStartMove} onStartResize={onStartResize} />
      ))}
      {selected && !dragging && HANDLES.map((h) => (
        <span key={h} className={`handle handle-${h}`} onPointerDown={(e) => onStartResize(e, c, h)} />
      ))}
    </div>
  );
}
