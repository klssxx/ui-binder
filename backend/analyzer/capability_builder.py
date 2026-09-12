"""Capability builder — turns file analyses into the semantic CAPABILITY GRAPH.

Nodes: functions, methods, classes, routes, components, hooks, handlers.
Edges: calls / handles / fetches / renders across frontend AND backend.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.analyzer.python_analyzer import analyze_python_file
from backend.analyzer.node_bridge import analyze_js_files
from backend.schema.capability import Capability, CapabilityEdge, CapabilityGraph

_MAX_JS_BATCH = 60


def build_capabilities(scan: dict[str, Any]) -> CapabilityGraph:
    root = Path(scan["root"])
    graph = CapabilityGraph()
    py_modules = []
    js_results: list[dict[str, Any]] = []
    rel_by_abs: dict[str, str] = {}

    for f in scan["source_files"]:
        path = root / f["rel_path"]
        if f["language"] == "python":
            try:
                py_modules.append((f["rel_path"], analyze_python_file(path, f["rel_path"])))
            except (SyntaxError, OSError):
                continue
        elif f["language"] in ("javascript", "typescript"):
            rel_by_abs[str(path)] = f["rel_path"]

    # batch the Node bridge
    js_paths: list[Path] = [Path(p) for p in rel_by_abs]
    for i in range(0, len(js_paths), _MAX_JS_BATCH):
        js_results.extend(analyze_js_files(js_paths[i:i + _MAX_JS_BATCH]))

    _add_python(graph, py_modules)
    _add_js(graph, js_results, rel_by_abs)
    _wire_graph(graph)
    return graph


def _slug(text: str) -> str:
    keep = [c if (c.isalnum() or c == "_") else "_" for c in text.lower()]
    return "".join(keep).strip("_") or "x"


def _cap_id(kind: str, qualified: str) -> str:
    return f"cap_{_slug(kind)}_{_slug(qualified)}"


def _expand_params(params: list[dict], models: dict[str, list[dict]]) -> list[dict]:
    """Replace Pydantic-model-typed params with the model's fields.

    FastAPI handlers take `request: GenerateRequest`; the bindable surface is
    the model's fields (prompt, mode, ...), not the wrapper argument.
    """
    out: list[dict] = []
    for p in params:
        annotation = str(p.get("type", ""))
        replaced = False
        for model_name, fields in models.items():
            if model_name in annotation and fields:
                for f in fields:
                    out.append({
                        "name": f["name"], "type": f.get("type", "unknown"),
                        "required": bool(f.get("required", True)),
                        "description": f"(from {model_name})",
                    })
                replaced = True
                break
        if not replaced:
            out.append(p)
    return out


def _add_python(graph: CapabilityGraph, modules: list[tuple[str, Any]]) -> None:
    for rel_path, mod in modules:
        models = getattr(mod, "models", {})
        for fn in mod.functions:
            graph.nodes.append(Capability(
                capability_id=_cap_id("function", f"{rel_path}::{fn.qualified}"),
                kind="function" if not fn.is_method else "method",
                name=fn.name, qualified_name=f"{rel_path}::{fn.qualified}",
                description=fn.docstring.split("\n")[0][:200] if fn.docstring else "",
                inputs=_expand_params(fn.params, models),
                outputs=[{"name": "return", "type": fn.returns, "required": True, "description": ""}] if fn.returns != "unknown" else [],
                side_effects=fn.side_effects, origin_file=rel_path, origin_line=fn.line,
                framework="python", dependencies=fn.calls, confidence=0.9,
            ))
        for cls in mod.classes:
            graph.nodes.append(Capability(
                capability_id=_cap_id("class", f"{rel_path}::{cls.name}"),
                kind="class", name=cls.name, qualified_name=f"{rel_path}::{cls.name}",
                description=cls.docstring.split("\n")[0][:200] if cls.docstring else "",
                origin_file=rel_path, origin_line=cls.line, framework="python", confidence=0.85,
            ))
            for m in cls.methods:
                graph.nodes.append(Capability(
                    capability_id=_cap_id("method", f"{rel_path}::{cls.name}.{m.name}"),
                    kind="method", name=f"{cls.name}.{m.name}",
                    qualified_name=f"{rel_path}::{cls.name}.{m.name}",
                    description=m.docstring.split("\n")[0][:200] if m.docstring else "",
                    inputs=m.params, side_effects=m.side_effects,
                    origin_file=rel_path, origin_line=m.line, framework="python",
                    dependencies=m.calls, confidence=0.85,
                ))
        for route in mod.routes:
            graph.nodes.append(Capability(
                capability_id=_cap_id("route", f"{rel_path}::{route.method}{route.path}::{route.handler}"),
                kind="route", name=f"{route.method} {route.path}",
                qualified_name=f"{rel_path}::{route.handler}",
                description=f"FastAPI route {route.method} {route.path} handled by {route.handler}()",
                inputs=_expand_params(route.params, models), origin_file=rel_path,
                origin_line=route.line, framework="fastapi",
                http_method=route.method, http_path=route.path,
                dependencies=[route.handler], confidence=0.95,
            ))


def _add_js(graph: CapabilityGraph, results: list[dict[str, Any]],
            rel_by_abs: dict[str, str]) -> None:
    for res in results:
        rel = rel_by_abs.get(res.get("file", ""), Path(res.get("file", "?")).name)
        fallback = bool(res.get("fallback"))
        base_conf = 0.35 if fallback else 0.85
        for fn in res.get("functions", []):
            if fn.get("name", "").startswith("("):
                continue
            graph.nodes.append(Capability(
                capability_id=_cap_id("function", f"{rel}::{fn['name']}"),
                kind="function", name=fn["name"], qualified_name=f"{rel}::{fn['name']}",
                description=fn.get("doc", ""), origin_file=rel,
                origin_line=fn.get("line", 0), framework="js",
                inputs=[{"name": p, "type": "unknown", "required": True, "description": ""}
                        for p in fn.get("params", [])],
                confidence=base_conf, metadata={"fallback": fallback},
            ))
        for comp in res.get("reactComponents", []):
            graph.nodes.append(Capability(
                capability_id=_cap_id("component", f"{rel}::{comp['name']}"),
                kind="component", name=comp["name"], qualified_name=f"{rel}::{comp['name']}",
                description=comp.get("doc", ""), origin_file=rel,
                origin_line=comp.get("line", 0), framework="react",
                inputs=[{"name": p, "type": "unknown", "required": False, "description": "prop"}
                        for p in comp.get("props", [])],
                confidence=base_conf if not fallback else 0.35,
                metadata={"fallback": fallback},
            ))
        for hook in res.get("customHooks", []):
            graph.nodes.append(Capability(
                capability_id=_cap_id("hook", f"{rel}::{hook['name']}"),
                kind="hook", name=hook["name"], qualified_name=f"{rel}::{hook['name']}",
                origin_file=rel, origin_line=hook.get("line", 0), framework="react",
                confidence=base_conf, metadata={"fallback": fallback},
            ))
        for eh in res.get("eventHandlers", []):
            graph.nodes.append(Capability(
                capability_id=_cap_id("handler", f"{rel}::{eh.get('handler') or eh.get('prop')}:{eh.get('line', 0)}"),
                kind="handler", name=eh.get("handler") or str(eh.get("prop", "")),
                qualified_name=f"{rel}::{eh.get('handler') or eh.get('prop')}",
                origin_file=rel, origin_line=eh.get("line", 0), framework="react",
                description=f"event prop {eh.get('prop')}", confidence=0.6 if eh.get("isDefined") else 0.3,
                metadata={"prop": eh.get("prop"), "fallback": fallback},
            ))
        for fetch in res.get("fetchCalls", []):
            graph.nodes.append(Capability(
                capability_id=_cap_id("fetch", f"{rel}::{fetch.get('method', 'GET')} {fetch.get('url', '')}:{fetch.get('line', 0)}"),
                kind="service", name=f"fetch {fetch.get('url', '')}",
                qualified_name=f"{rel}::fetch::{fetch.get('url', '')}",
                origin_file=rel, origin_line=fetch.get("line", 0), framework="js",
                http_method=fetch.get("method", "GET"), http_path=fetch.get("url", ""),
                side_effects=["network"], confidence=0.8, metadata={"fallback": fallback},
            ))


def _wire_graph(graph: CapabilityGraph) -> None:
    by_name: dict[str, list[Capability]] = {}
    by_http: dict[tuple[str, str], Capability] = {}
    for cap in graph.nodes:
        by_name.setdefault(cap.name, []).append(cap)
        if cap.http_method and cap.http_path:
            by_http.setdefault((cap.http_method.upper(), _norm_path(cap.http_path)), cap)

    for cap in graph.nodes:
        for dep in cap.dependencies:
            for target in by_name.get(_base_name(dep), []):
                if target.capability_id != cap.capability_id:
                    graph.edges.append(CapabilityEdge(
                        source=cap.capability_id, target=target.capability_id, relation="calls"))
        if cap.kind == "service" and cap.http_path:
            key = (cap.http_method.upper(), _norm_path(cap.http_path))
            route = by_http.get(key)
            if route and route.capability_id != cap.capability_id:
                graph.edges.append(CapabilityEdge(
                    source=cap.capability_id, target=route.capability_id, relation="fetches"))
        if cap.kind == "route" and cap.dependencies:
            for dep in cap.dependencies:
                for target in by_name.get(_base_name(dep), []):
                    graph.edges.append(CapabilityEdge(
                        source=cap.capability_id, target=target.capability_id, relation="handles"))

    # component → handler edges
    handlers = [c for c in graph.nodes if c.kind == "handler"]
    for h in handlers:
        for comp in graph.nodes:
            if comp.kind == "component" and h.origin_file == comp.origin_file and h.name:
                graph.edges.append(CapabilityEdge(
                    source=comp.capability_id, target=h.capability_id, relation="renders"))


def _base_name(qualified: str) -> str:
    return qualified.split(".")[-1].split("(")[0].strip()


def _norm_path(path: str) -> str:
    p = (path or "").strip()
    if p.startswith(("http://", "https://")):
        from urllib.parse import urlparse
        p = urlparse(p).path or "/"
    return p if p.startswith("/") else "/" + p
