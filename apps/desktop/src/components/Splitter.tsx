import { useCallback, useEffect, useRef, useState } from "react";

/** Divider arrastrable para redimensionar paneles (F0). */
export function Splitter({ direction, onDelta }: {
  direction: "x" | "y"; onDelta: (deltaPx: number) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const last = useRef(0);

  const onDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    last.current = direction === "x" ? e.clientX : e.clientY;
    setDragging(true);
  }, [direction]);

  useEffect(() => {
    if (!dragging) return;
    const move = (e: PointerEvent) => {
      const pos = direction === "x" ? e.clientX : e.clientY;
      onDelta(pos - last.current);
      last.current = pos;
    };
    const up = () => setDragging(false);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [dragging, direction, onDelta]);

  return (
    <div
      className={`splitter splitter-${direction} ${dragging ? "splitter-active" : ""}`}
      onPointerDown={onDown}
    />
  );
}
