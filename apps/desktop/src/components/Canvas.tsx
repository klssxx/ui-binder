/** Visual canvas: renders the UI AST as absolutely-positioned nodes with
 *  select / move / resize / inline text editing. Drag delta lives in state;
 *  the AST is mutated once on pointer-up so undo history stays clean. */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useEditor } from "../state/editorStore";
import type { BBox, UIComponent } from "../types";

const TEXT_TYPES = new Set(["text", "heading", "button", "input", "textarea", "select"]);
const HANDLES = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];

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

export function Canvas() {
  const editor = useEditor();
  const { doc } = editor.state;
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  useLayoutEffect(() => {
    const el = viewportRef.current;
    if (!el || !doc) return;
    const fit = Math.min(1, (el.clientWidth - 64) / doc.screen.width,
      (el.clientHeight - 64) / doc.screen.height);
    setZoom(Math.max(0.15, Math.round(fit * 100) / 100));
  }, [doc]);

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

  if (!doc) {
    return (
      <div className="canvas-empty">
        <div>
          <h2>Sin documento UI</h2>
          <p>Importa un screenshot y ejecuta <strong>ANALYZE UI</strong>, o añade
            componentes desde el árbol con el botón <strong>+</strong>.</p>
        </div>
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
    <div
      className="canvas-scroll"
      ref={viewportRef}
      onPointerDown={() => { editor.select(null); setEditingId(null); }}
    >
      <div className="canvas-zoom">{Math.round(zoom * 100)}%</div>
      <div
        className="canvas-stage"
        style={{
          width: doc.screen.width,
          height: doc.screen.height,
          background: doc.screen.background ?? "#101216",
          transform: `scale(${zoom})`,
          transformOrigin: "top left",
        }}
      >
        {editor.childrenOf("screen").map((c) => (
          <CanvasNode
            key={c.id}
            component={c}
            liveBox={liveBox}
            editingId={editingId}
            setEditingId={setEditingId}
            onStartMove={(e, c2) => {
              e.stopPropagation();
              editor.select(c2.id);
              setDrag({ mode: "move", id: c2.id, startX: e.clientX, startY: e.clientY, dx: 0, dy: 0 });
            }}
            onStartResize={(e, c2, handle) => {
              e.stopPropagation();
              setDrag({ mode: "resize", id: c2.id, handle, startX: e.clientX, startY: e.clientY,
                dx: 0, dy: 0, origin: { ...c2.bbox } });
            }}
          />
        ))}
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
    borderRadius: c.styles.radius ? Number(c.styles.radius) : undefined,
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
      {editing ? (
        <input
          className="node-inline-edit"
          autoFocus
          defaultValue={c.text ?? ""}
          onPointerDown={(e) => e.stopPropagation()}
          onChange={(e) => editor.setText(c.id, e.target.value)}
          onBlur={() => setEditingId(null)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === "Escape") setEditingId(null);
            e.stopPropagation();
          }}
        />
      ) : (
        c.text && <span className="node-text">{c.text}</span>
      )}
      {c.bindings.length > 0 && (
        <span className="node-binding-dot" title={`${c.bindings.length} binding(s)`} />
      )}
      {editor.childrenOf(c.id).map((k) => (
        <CanvasNode key={k.id} component={k} liveBox={liveBox} editingId={editingId}
          setEditingId={setEditingId} onStartMove={onStartMove} onStartResize={onStartResize} />
      ))}
      {selected && !dragging && HANDLES.map((h) => (
        <span key={h} className={`handle handle-${h}`}
          onPointerDown={(e) => onStartResize(e, c, h)} />
      ))}
    </div>
  );
}
