"""Safe exporter — writes a standalone React/Vite/TS app from the UI AST.

SAFETY MODEL (directive §35-36):
  - export NEVER writes into the imported project
  - target must be empty or nonexistent (validated by security.paths)
  - a CHANGE PLAN (dry run) is always available before writing
Bound CONFIRMED bindings to route capabilities become real fetch calls;
everything else is exported as design-only markup with data-binding attributes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.export.base import Exporter, ExportPlan, register_exporter
from backend.security.paths import is_safe_export_target
from backend.schema.ui_schema import UIDocument

_FILES = [
    "package.json", "vite.config.ts", "tsconfig.json", "index.html",
    "src/main.tsx", "src/App.tsx", "src/styles.css", "src/api.ts", "src/bindings.json",
]


def build_export_plan(document: UIDocument, bindings: list[dict[str, Any]]) -> dict[str, Any]:
    """Legacy-compatible plan function (target = react-vite-ts)."""
    confirmed = [b for b in bindings if b.get("status") == "CONFIRMED"]
    return {
        "mode": "export-to-new-directory",
        "target": "react-vite-ts",
        "files_created": _FILES,
        "files_modified": [],
        "bindings_embedded": len(confirmed),
        "bindings_total": len(bindings),
        "components": len(document.components),
        "notes": [
            "Target directory must be empty; nothing in the imported project is touched.",
            "Only CONFIRMED bindings become live calls; others are marked data-binding.",
        ],
    }


def export_react_project(document: UIDocument, bindings: list[dict[str, Any]],
                         capabilities: list[dict[str, Any]], tokens: dict[str, Any] | None,
                         target: Path, source_project: Path | None = None,
                         image_resolver=None) -> dict[str, Any]:
    """Legacy-compatible export function (target = react-vite-ts)."""
    exporter = ReactViteTSExporter()
    return exporter.export(document, bindings, capabilities, tokens,
                           target, source_project, image_resolver)


class ReactViteTSExporter(Exporter):
    target_id = "react-vite-ts"
    label = "React / Vite / TypeScript"

    def plan(self, document, bindings, capabilities, tokens) -> ExportPlan:
        p = ExportPlan()
        p.target = self.target_id
        p.target_label = self.label
        p.files_created = list(_FILES)
        confirmed = [b for b in bindings if b.get("status") == "CONFIRMED"]
        p.bindings_total = len(bindings)
        p.bindings_realizable = len(confirmed)
        p.bindings_unresolved = len(bindings) - len(confirmed)
        p.components_total = len(document.components)
        p.components_native = len(document.components)
        p.components_fallback = 0
        return p

    def validate(self, document, bindings, capabilities, tokens) -> list[str]:
        warnings = []
        if not document.components:
            warnings.append("No components in UI document — export will be empty.")
        return warnings

    def export(self, document, bindings, capabilities, tokens, target,
               source_project=None, image_resolver=None) -> dict[str, Any]:
        import re as _re
        import shutil as _shutil
        ok, why = is_safe_export_target(target, source_project)
        if not ok:
            raise ValueError(why)
        target.mkdir(parents=True, exist_ok=True)
        (target / "src").mkdir(exist_ok=True)

        # PRESERVE INPUTS: do not mutate bindings or components
        bindings = _detach(bindings)
        caps_by_id = {c.get("capability_id"): c for c in capabilities}
        for b in bindings:
            b["_capability"] = caps_by_id.get(b.get("target_capability"), {})

        css_vars = _css_vars(tokens or {})

        (target / "package.json").write_text(_PKG_JSON, encoding="utf-8")
        (target / "vite.config.ts").write_text(_VITE_CONFIG, encoding="utf-8")
        (target / "tsconfig.json").write_text(_TSCONFIG, encoding="utf-8")
        (target / "index.html").write_text(_INDEX_HTML, encoding="utf-8")
        (target / "src/main.tsx").write_text(_MAIN_TSX, encoding="utf-8")
        (target / "src/styles.css").write_text(_styles_css(css_vars), encoding="utf-8")

        # Resolve assets first to get relative paths for codegen
        import shutil as _shutil
        asset_paths: dict[str, str] = {}
        assets_copied = 0
        if image_resolver is not None:
            pattern = _re.compile(r"/api/images/([A-Za-z0-9_]+)/file$")
            for comp in document.components:
                styles = comp.model_dump().get("styles") if hasattr(comp, "model_dump") else comp.styles
                src = styles.get("src") if isinstance(styles, dict) else None
                if not isinstance(src, str):
                    continue
                m = pattern.search(src)
                if not m:
                    continue
                image_id = m.group(1)
                record_path = image_resolver(image_id)
                if record_path is None or not Path(record_path).is_file():
                    continue
                (target / "assets").mkdir(exist_ok=True)
                filename = f"{image_id}{Path(record_path).suffix}"
                _shutil.copyfile(record_path, target / "assets" / filename)
                asset_paths[comp.id] = f"./assets/{filename}"
                assets_copied += 1

        api_code, app_code = _generate_code(document, bindings, asset_paths)
        (target / "src/api.ts").write_text(api_code, encoding="utf-8")
        (target / "src/App.tsx").write_text(app_code, encoding="utf-8")
        (target / "src/bindings.json").write_text(
            json.dumps(bindings, ensure_ascii=False, indent=2), encoding="utf-8")

        plan = self.plan(document, bindings, capabilities, tokens)
        d = plan.to_dict()
        d["target_path"] = str(target)
        d["assets_copied"] = assets_copied
        # Legacy compatibility for existing API clients/tests
        confirmed_count = sum(1 for b in bindings if b.get("status") == "CONFIRMED")
        d["bindings_embedded"] = confirmed_count
        d["files_modified"] = []
        d["mode"] = "export-to-new-directory"
        return d


def _detach(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shallow copy each binding dict so export doesn't mutate input."""
    return [{**b} for b in bindings]


# ---------------------------------------------------------------- codegen

def _escape(text: str | None) -> str:
    return json.dumps(text or "", ensure_ascii=False)


def _style_of(comp: dict[str, Any]) -> str:
    b = comp["bbox"]
    s = comp.get("styles") or {}
    parts = [
        f"position: 'absolute'",
        f"left: {b['x']:g}px", f"top: {b['y']:g}px",
        f"width: {b['width']:g}px", f"height: {b['height']:g}px",
    ]
    if s.get("background"):
        parts.append(f"background: '{s['background']}'")
    if s.get("color"):
        parts.append(f"color: '{s['color']}'")
    if s.get("fontSize"):
        parts.append(f"fontSize: '{s['fontSize']}'")
    for key in ("fontFamily", "fontWeight", "fontStyle", "textAlign", "shadow"):
        if s.get(key):
            parts.append(f"{key if key != 'shadow' else 'textShadow'}: '{s[key]}'")
    if s.get("opacity") is not None:
        parts.append(f"opacity: {s['opacity']}")
    if s.get("radius"):
        parts.append(f"borderRadius: '{s['radius']}px'")
    if s.get("padding"):
        parts.append(f"padding: '{s['padding']}'")
    box = s.get("boxSizing", "border-box")
    parts.append(f"boxSizing: '{box}'")
    return ", ".join(parts)


_ELEMENT = {
    "container": "div", "panel": "div", "card": "div", "modal": "div",
    "text": "p", "heading": "h2", "button": "button",
    "input": "input", "textarea": "textarea", "select": "select",
    "checkbox": "input", "radio": "input", "image": "img", "icon": "span",
    "table": "div", "chart": "div", "tabs": "div", "sidebar": "aside",
    "navbar": "nav", "divider": "hr", "custom": "div",
}

_VOID = {"img", "hr", "input"}


def _stroke_svg(stroke: dict[str, Any]) -> str:
    """Stroke -> SVG element."""
    pts = stroke.get("points", [])
    if not pts:
        return ""
    common = (f'stroke="{stroke.get("color", "#4f8cff")}" '
              f'stroke-width="{stroke.get("width", 4)}" '
              f'fill="none" opacity="{stroke.get("opacity", 1)}" '
              f'stroke-linecap="round" stroke-linejoin="round"')
    tool = stroke.get("tool", "pencil")
    if tool == "pencil":
        d = "M " + " L ".join(f'{p["x"]:g} {p["y"]:g}' for p in pts)
        return f'<path d="{d}" {common} />'
    a, b = pts[0], pts[-1]
    x, y = min(a["x"], b["x"]), min(a["y"], b["y"])
    w, h = abs(b["x"] - a["x"]), abs(b["y"] - a["y"])
    if tool == "rect":
        return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" {common} />'
    if tool == "ellipse":
        return (f'<ellipse cx="{x + w / 2:g}" cy="{y + h / 2:g}" rx="{w / 2:g}" '
                f'ry="{h / 2:g}" {common} />')
    if tool == "arrow":
        import math
        ang = math.atan2(b["y"] - a["y"], b["x"] - a["x"])
        size = max(10.0, float(stroke.get("width", 4)) * 3)
        lx, ly = b["x"] - size * math.cos(ang - 0.5), b["y"] - size * math.sin(ang - 0.5)
        rx, ry = b["x"] - size * math.cos(ang + 0.5), b["y"] - size * math.sin(ang + 0.5)
        return (f'<line x1="{a["x"]:g}" y1="{a["y"]:g}" x2="{b["x"]:g}" y2="{b["y"]:g}" {common} />'
                f'<path d="M {b["x"]:g} {b["y"]:g} L {lx:g} {ly:g} M {b["x"]:g} {b["y"]:g} '
                f'L {rx:g} {ry:g}" {common} />')
    return f'<line x1="{a["x"]:g}" y1="{a["y"]:g}" x2="{b["x"]:g}" y2="{b["y"]:g}" {common} />'


def _generate_code(document: UIDocument, bindings: list[dict[str, Any]],
                   asset_paths: dict[str, str] | None = None) -> tuple[str, str]:
    strokes_svg = [_stroke_svg(s.model_dump() if hasattr(s, "model_dump") else s)
                   for s in getattr(document, "strokes", [])]
    comps = {c.id: c.model_dump() for c in document.components}
    children = {"screen": [cid for cid, c in comps.items() if c["parent_id"] in (None, "screen")]}
    for cid, c in comps.items():
        for child in c["children"]:
            children.setdefault(cid, []).append(child)

    confirmed = [b for b in bindings
                 if b.get("status") == "CONFIRMED" and b["target_capability"]]

    # state keys from output mappings: component_id -> state var
    state_vars: dict[str, str] = {}
    for b in confirmed:
        for om in b.get("output_mapping", []):
            target_comp = (om.get("target") or "").split(".")[0]
            if target_comp in comps and target_comp not in state_vars:
                state_vars[target_comp] = _safe_ident(f"{comps[target_comp].get('name') or target_comp}_value")

    handlers: dict[str, str] = {}  # component_id -> handler name
    api_fns: dict[str, dict[str, Any]] = {}
    for b in confirmed:
        cap_meta = b.get("_capability") or {}
        method = (cap_meta.get("http_method") or "POST").upper()
        path = cap_meta.get("http_path") or ""
        if not path:
            continue
        fname = _safe_ident(f"call_{b['component_id']}_{method.lower()}")
        api_fns[fname] = {"method": method, "path": path,
                          "inputs": [m.get("target") for m in b.get("input_mapping", [])]}
        handler = _safe_ident(f"handle_{b['component_id']}")
        handlers[b["component_id"]] = handler

    api_lines = [
        "// Generated by UI Binder — binding runtime for CONFIRMED bindings.",
        'const API_BASE = (import.meta.env?.VITE_API_BASE as string | undefined) ?? "http://127.0.0.1:8765";',
        "",
    ]
    for fname, spec in api_fns.items():
        method = spec["method"]
        if method == "GET":
            # GET: no body, query params in URL
            api_lines += [
                f"export async function {fname}(params: Record<string, string> = {{}}) {{",
                f'  const qs = new URLSearchParams(params).toString();',
                f'  const url = API_BASE + {json.dumps(spec["path"])} + (qs ? "?" + qs : "");',
                f'  const res = await fetch(url, {{',
                f'    method: "GET",',
                '    headers: { "Content-Type": "application/json" },',
                "  });",
                f"  if (!res.ok) throw new Error(`GET {spec['path']} failed: ${{res.status}}`);",
                "  if (res.status === 204) return undefined;",
                "  return res.json();",
                "}",
                "",
            ]
        else:
            api_lines += [
                f"export async function {fname}(body: Record<string, unknown>) {{",
                f'  const res = await fetch(API_BASE + {json.dumps(spec["path"])}, {{',
                f'    method: "{method}",',
                '    headers: { "Content-Type": "application/json" },',
                "    body: JSON.stringify(body),",
                "  }});",
                f"  if (!res.ok) throw new Error(`{method} {spec['path']} failed: ${{res.status}}`);",
                "  if (res.status === 204) return undefined;",
                "  return res.json();",
                "}",
                "",
            ]
    if not api_fns:
        api_lines.append("export {};")
    api_code = "\n".join(api_lines)

    # ---- App.tsx
    lines: list[str] = [
        "// Generated by UI Binder — DO NOT edit manually if you plan to re-export.",
        'import { useState } from "react";',
        'import "./styles.css";',
    ]
    if api_fns:
        lines.append('import { ' + ", ".join(sorted(api_fns)) + ' } from "./api";')
    lines += ["", "export default function App() {"]
    for var in sorted(set(state_vars.values())):
        lines.append(f'  const [{var}, set{var.capitalize()}] = useState("");')
    lines.append('  const [busy, setBusy] = useState(false);')
    lines.append('  const [error, setError] = useState("");')
    lines.append("")

    for comp_id, handler in handlers.items():
        fname = next((f for f in api_fns if f.startswith(f"call_{comp_id}_")), None)
        if fname is None:
            continue
        sources: dict[str, str] = {}
        for b in confirmed:
            if b["component_id"] != comp_id:
                continue
            for m in b.get("input_mapping", []):
                src_comp = (m.get("source") or "").split(".")[0]
                param = m.get("target") or ""
                if src_comp and param:
                    sources[param] = src_comp
        body_parts = [
            f'    {param}: (document.getElementById("{src}") as HTMLInputElement | null)?.value ?? "",'
            for param, src in sorted(sources.items())
        ]
        lines += [
            f"  const {handler} = async () => {{",
            '    setError(""); setBusy(true);',
            "    try {",
            f"      const res = await {fname}({{",
            *body_parts,
            "      }});",
        ]
        outputs = [om for b in confirmed if b["component_id"] == comp_id for om in b.get("output_mapping", [])]
        for om in outputs:
            target_comp = (om.get("target") or "").split(".")[0]
            var = state_vars.get(target_comp)
            if var:
                lines.append(f"      set{var.capitalize()}(String(res[{_escape(om.get('source') or 'return')}] ?? res ?? \"\"));")
        lines += [
            "    } catch (e) {",
            '      setError(e instanceof Error ? e.message : String(e));',
            "    } finally {",
            "      setBusy(false);",
            "    }",
            "  };",
            "",
        ]

    lines.append("  return (")
    lines.append(f'    <div className="uib-screen" style={{{{ width: {document.screen.width:g}, height: {document.screen.height:g} }}}}>')
    if strokes_svg:
        lines.append(f'      <svg className="uib-strokes" width={document.screen.width:g} height={document.screen.height:g}>')
        lines += [f"        {el}" for el in strokes_svg]
        lines.append("      </svg>")
    lines += _render_children("screen", comps, children, handlers, state_vars, bindings, 3, asset_paths)
    lines.append("    </div>")
    lines.append("  );")
    lines.append("}")
    app_code = "\n".join(lines) + "\n"
    return api_code, app_code


def _render_children(parent_id: str, comps: dict[str, Any], children: dict[str, Any],
                     handlers: dict[str, str], state_vars: dict[str, str],
                     bindings: list[dict[str, Any]], depth: int,
                     asset_paths: dict[str, str] | None = None) -> list[str]:
    out: list[str] = []
    pad = "  " * depth
    for cid in children.get(parent_id, []):
        comp = comps.get(cid)
        if comp is None:
            continue
        ctype = comp["type"]
        tag = _ELEMENT.get(ctype, "div")
        attrs: list[str] = []
        if ctype == "input":
            attrs.append('type="text"')
        if ctype == "image":
            src = (asset_paths or {}).get(cid) or (comp.get("styles") or {}).get("src") or "placeholder.png"
            attrs.append(f'src="{src}"')
            attrs.append('alt=""')
        attrs.append(f'id="{cid}"')
        attrs.append(f'data-uib-type="{ctype}"')
        attrs.append(f'style={{{{{ {_style_of(comp)} }}}}}')
        if cid in handlers:
            attrs.append(f'onClick={{{handlers[cid]}}}')
            attrs.append('disabled={busy}')
        else:
            bound = [b for b in bindings if b.get("component_id") == cid]
            if bound:
                attrs.append(f'data-binding="{bound[0]["binding_id"]}"')
        attr_str = (" " + " ".join(attrs)) if attrs else ""
        if tag in _VOID:
            out.append(f"{pad}<{tag}{attr_str} />")
            continue
        inner = ""
        if cid in state_vars:
            inner = f"{{{state_vars[cid]} || ''}}"
        elif comp.get("text"):
            inner = _escape(comp["text"])[1:-1]
        kids = _render_children(cid, comps, children, handlers, state_vars, bindings, depth + 1, asset_paths)
        if kids:
            out.append(f"{pad}<{tag}{attr_str}>")
            out += kids
            out.append(f"{pad}</{tag}>")
        else:
            out.append(f"{pad}<{tag}{attr_str}>{inner}</{tag}>")
    return out


def _safe_ident(text: str) -> str:
    keep = [c if (c.isalnum() or c == "_") else "_" for c in text]
    ident = "".join(keep).strip("_") or "x"
    if ident[0].isdigit():
        ident = "_" + ident
    return ident


def _css_vars(tokens: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in tokens.get("colors", []):
        out["--color-" + str(c.get("name", "x")).replace(" ", "-").lower()] = str(c.get("hex", "#000"))
    for f in tokens.get("fonts", []):
        suffix = "" if f.get("role") == "body" else "-" + str(f.get("role"))
        out[f"--font-size{suffix}"] = f"{f.get('size_px', 14)}px"
    return out


def _styles_css(vars_: dict[str, str]) -> str:
    lines = ["/* Generated by UI Binder */", ":root {"]
    for k, v in sorted(vars_.items()):
        lines.append(f"  {k}: {v};")
    lines += [
        "}",
        "* { margin: 0; box-sizing: border-box; }",
        "body { font-family: system-ui, sans-serif; background: #101216; }",
        ".uib-screen { position: relative; overflow: hidden; margin: 0 auto; background: var(--color-background, #101216); }",
        ".uib-strokes { position: absolute; left: 0; top: 0; pointer-events: none; }",
        "button { cursor: pointer; border: none; }",
        "button:disabled { opacity: 0.6; cursor: wait; }",
        "",
    ]
    return "\n".join(lines)


_PKG_JSON = """{
  "name": "uibinder-export",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.5.3",
    "vite": "^5.4.0"
  }
}
"""

_VITE_CONFIG = """import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});
"""

_TSCONFIG = """{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true
  },
  "include": ["src"]
}
"""

_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>UI Binder Export</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""

_MAIN_TSX = """import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
"""


# Register the exporter
register_exporter(ReactViteTSExporter)
