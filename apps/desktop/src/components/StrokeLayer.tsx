/** Capa de dibujo (F5): render SVG de los trazos del documento. */
import type { Stroke } from "../types";

export function strokeSvg(stroke: Stroke): JSX.Element {
  const common = {
    stroke: stroke.color,
    strokeWidth: stroke.width,
    fill: "none" as const,
    opacity: stroke.opacity,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  const key = stroke.id;
  if (stroke.tool === "pencil") {
    const d = "M " + stroke.points.map((p) => `${p.x} ${p.y}`).join(" L ");
    return <path key={key} d={d} {...common} />;
  }
  const a = stroke.points[0];
  const b = stroke.points[stroke.points.length - 1];
  if (!a || !b) return <g key={key} />;
  const x = Math.min(a.x, b.x), y = Math.min(a.y, b.y);
  const w = Math.abs(b.x - a.x), h = Math.abs(b.y - a.y);
  if (stroke.tool === "rect") {
    return <rect key={key} x={x} y={y} width={w} height={h} {...common} />;
  }
  if (stroke.tool === "ellipse") {
    return <ellipse key={key} cx={x + w / 2} cy={y + h / 2} rx={w / 2} ry={h / 2} {...common} />;
  }
  if (stroke.tool === "arrow") {
    const ang = Math.atan2(b.y - a.y, b.x - a.x);
    const size = Math.max(10, stroke.width * 3);
    const lx = b.x - size * Math.cos(ang - 0.5), ly = b.y - size * Math.sin(ang - 0.5);
    const rx = b.x - size * Math.cos(ang + 0.5), ry = b.y - size * Math.sin(ang + 0.5);
    return (
      <g key={key}>
        <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} {...common} />
        <path d={`M ${b.x} ${b.y} L ${lx} ${ly} M ${b.x} ${b.y} L ${rx} ${ry}`} {...common} />
      </g>
    );
  }
  return <line key={key} x1={a.x} y1={a.y} x2={b.x} y2={b.y} {...common} />;
}

export function StrokeLayer({ strokes, width, height }: {
  strokes: Stroke[]; width: number; height: number;
}) {
  if (!strokes.length) return null;
  return (
    <svg className="strokes-layer" width={width} height={height}>
      {strokes.map((s) => strokeSvg(s))}
    </svg>
  );
}
