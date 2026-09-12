"""Python source analysis via ``ast`` — no execution, read-only, safe.

Extracts functions, classes/methods, FastAPI routes, imports and internal calls.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

_FASTAPI_DECORATORS = {"get", "post", "put", "patch", "delete", "head", "options", "websocket"}
_SIDE_EFFECT_CALLS = {
    "open": "fs", "write": "fs", "write_text": "fs", "save": "fs", "remove": "fs",
    "requests": "network", "httpx": "network", "fetch": "network",
    "connect": "db", "execute": "db", "commit": "db", "insert": "db",
}


@dataclass
class PyFunction:
    name: str
    qualified: str
    line: int
    params: list[dict[str, Any]] = field(default_factory=list)
    returns: str = "unknown"
    docstring: str = ""
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)
    is_method: bool = False


@dataclass
class PyRoute:
    method: str
    path: str
    handler: str
    line: int
    params: list[dict[str, Any]] = field(default_factory=list)
    returns: str = "unknown"


@dataclass
class PyClass:
    name: str
    line: int
    bases: list[str] = field(default_factory=list)
    methods: list[PyFunction] = field(default_factory=list)
    docstring: str = ""


@dataclass
class PyModule:
    rel_path: str
    imports: list[str] = field(default_factory=list)
    functions: list[PyFunction] = field(default_factory=list)
    classes: list[PyClass] = field(default_factory=list)
    routes: list[PyRoute] = field(default_factory=list)
    models: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def _annotation_str(node: ast.expr | None) -> str:
    if node is None:
        return "unknown"
    try:
        return ast.unparse(node)
    except Exception:
        return "unknown"


def _params(args: ast.arguments) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    defaults: list[ast.expr | None] = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(args.args, defaults):
        if arg.arg in {"self", "cls"}:
            continue
        out.append({
            "name": arg.arg,
            "type": _annotation_str(arg.annotation),
            "required": default is None,
            "description": "",
        })
    return out


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _decorator_info(dec: ast.expr) -> tuple[str, str] | None:
    """Return (http_method, path) if the decorator looks like app.get('/x')."""
    target = dec
    if isinstance(target, ast.Call):
        func = target.func
        if isinstance(func, ast.Attribute) and func.attr in _FASTAPI_DECORATORS:
            path = ""
            if target.args and isinstance(target.args[0], ast.Constant):
                path = str(target.args[0].value)
            return func.attr.upper(), path
    return None


def analyze_python_source(source: str, rel_path: str = "<memory>") -> PyModule:
    tree = ast.parse(source)
    module = PyModule(rel_path=rel_path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module.imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module.imports.append(node.module)

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.class_stack: list[PyClass] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            bases = [_annotation_str(b) for b in node.bases]
            py_class = PyClass(
                name=node.name, line=node.lineno, bases=bases,
                docstring=ast.get_docstring(node) or "",
            )
            module.classes.append(py_class)
            self.class_stack.append(py_class)
            self.generic_visit(node)
            self.class_stack.pop()

        def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            qualified = node.name
            is_method = bool(self.class_stack)
            if self.class_stack:
                qualified = f"{self.class_stack[-1].name}.{node.name}"
            calls: list[str] = []
            side_effects: set[str] = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    name = _call_name(sub)
                    if name:
                        calls.append(name)
                        effect = _SIDE_EFFECT_CALLS.get(name)
                        if effect:
                            side_effects.add(effect)
            fn = PyFunction(
                name=node.name, qualified=qualified, line=node.lineno,
                params=_params(node.args), returns=_annotation_str(node.returns),
                docstring=ast.get_docstring(node) or "", is_async=isinstance(node, ast.AsyncFunctionDef),
                decorators=[_annotation_str(d) for d in node.decorator_list],
                calls=calls, side_effects=sorted(side_effects), is_method=is_method,
            )
            route = None
            for dec in node.decorator_list:
                info = _decorator_info(dec)
                if info:
                    route = PyRoute(method=info[0], path=info[1], handler=node.name,
                                    line=node.lineno, params=fn.params, returns=fn.returns)
                    break
            if route is not None:
                module.routes.append(route)
            if is_method and self.class_stack:
                self.class_stack[-1].methods.append(fn)
            else:
                module.functions.append(fn)

        visit_FunctionDef = _function
        visit_AsyncFunctionDef = _function

    Visitor().visit(tree)

    # Pydantic-ish request/response models: classes deriving from BaseModel (or similar)
    for cls in module.classes:
        if any("BaseModel" in b for b in cls.bases):
            module.models[cls.name] = _extract_model_fields(tree, cls.name)
    return module


def _find_class_source(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise KeyError(name)


def _extract_model_fields(tree: ast.Module, class_name: str) -> list[dict[str, Any]]:
    cls = _find_class_source(tree, class_name)
    fields: list[dict[str, Any]] = []
    for stmt in cls.body:
        targets: list[ast.expr] = []
        annotation = None
        if isinstance(stmt, ast.AnnAssign):
            targets, annotation = [stmt.target], stmt.annotation
        elif isinstance(stmt, ast.Assign):
            targets = stmt.targets
        for t in targets:
            if isinstance(t, ast.Name):
                fields.append({
                    "name": t.id,
                    "type": _annotation_str(annotation) if annotation is not None else "unknown",
                    "required": not (isinstance(stmt, ast.AnnAssign) and stmt.value is not None),
                    "description": "",
                })
    return fields


def analyze_python_file(path, rel_path: str | None = None) -> PyModule:
    from pathlib import Path

    p = Path(path)
    source = p.read_text(encoding="utf-8", errors="replace")
    return analyze_python_source(source, rel_path or p.name)
