#!/usr/bin/env node
/**
 * UI BINDER project-analyzer — real AST analysis for JS/TS/JSX/TSX.
 * Usage: node analyze.mjs <file...>  → JSON array on stdout.
 * Consumed by backend/analyzer/node_bridge.py. Read-only.
 */
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
let parser;
try {
  parser = require("@babel/parser");
} catch {
  console.error("project-analyzer: @babel/parser not installed (run npm install)");
  process.exit(3);
}
const traverse = require("@babel/traverse").default;

const files = process.argv.slice(2);
const results = [];

for (const file of files) {
  const fs = await import("node:fs");
  let source;
  try {
    source = fs.readFileSync(file, "utf8");
  } catch (e) {
    results.push({ file, error: `read failed: ${e.code || e.message}` });
    continue;
  }
  const isTS = /\.[cm]?tsx?$/.test(file);
  const out = {
    file,
    language: isTS ? (file.endsWith("x") ? "tsx" : "ts") : (file.endsWith(".jsx") ? "jsx" : "js"),
    imports: [],
    exports: [],
    functions: [],
    classes: [],
    reactComponents: [],
    customHooks: [],
    hooksUsed: [],
    eventHandlers: [],
    fetchCalls: [],
    routes: [],
  };
  let ast;
  const plugins = ["jsx", "decorators-legacy", "classProperties"];
  if (isTS) plugins.push(["typescript", { isTSX: file.endsWith("x") }]);
  try {
    ast = parser.parse(source, { sourceType: "unambiguous", errorRecovery: true, plugins });
  } catch (e) {
    out.error = `parse failed: ${e.message}`;
    results.push(out);
    continue;
  }

  const paramNames = (param) => {
    if (!param) return [];
    if (param.type === "ObjectPattern") {
      return param.properties.filter((p) => p.type === "ObjectProperty").map((p) =>
        p.key.name || p.key.value || "?"
      );
    }
    if (param.type === "Identifier") return [param.name];
    if (param.type === "AssignmentPattern") return paramNames(param.left);
    return [];
  };
  const docOf = (node) => {
    if (!node.leadingComments || !node.leadingComments.length) return "";
    const last = node.leadingComments[node.leadingComments.length - 1];
    if (last.type !== "CommentBlock") return "";
    return last.value.split("\n").map((l) => l.replace(/^\s*\*?\s?/, "")).filter(Boolean)[0] || "";
  };
  const returnsJSX = (node) => {
    if (!node || !node.body) return false;
    if (node.body.type === "JSXElement" || node.body.type === "JSXFragment") return true;
    if (node.body.type === "BlockStatement") {
      return node.body.body.some(
        (s) => s.type === "ReturnStatement" && s.argument &&
          (s.argument.type === "JSXElement" || s.argument.type === "JSXFragment" ||
            (s.argument.type === "CallExpression" && false))
      );
    }
    return false;
  };

  const componentNames = new Set();
  const handlerNames = new Set();

  traverse(ast, {
    FunctionDeclaration(path) {
      const node = path.node;
      const name = node.id ? node.id.name : "(anonymous)";
      out.functions.push({ name, line: node.loc.start.line, params: paramNames(node.params[0]), async: !!node.async, doc: docOf(node) });
      if (/^[A-Z]/.test(name) && returnsJSX(node)) {
        componentNames.add(name);
        out.reactComponents.push({ name, line: node.loc.start.line, props: paramNames(node.params[0]), doc: docOf(node) });
      }
      if (/^use[A-Z]/.test(name)) out.customHooks.push({ name, line: node.loc.start.line });
      if (/^(handle|on)[A-Z_]/.test(name)) handlerNames.add(name);
    },
    VariableDeclarator(path) {
      const node = path.node;
      if (!node.init) return;
      const init = node.init;
      const isFn = init.type === "ArrowFunctionExpression" || init.type === "FunctionExpression";
      if (node.id && node.id.type === "Identifier" && isFn) {
        const name = node.id.name;
        out.functions.push({ name, line: node.loc.start.line, params: paramNames(node.params[0]), async: !!init.async, doc: docOf(path.parent) || docOf(node) });
        if (/^[A-Z]/.test(name) && returnsJSX(init)) {
          componentNames.add(name);
          out.reactComponents.push({ name, line: node.loc.start.line, props: paramNames(init.params[0]), doc: docOf(path.parent) });
        }
        if (/^use[A-Z]/.test(name)) out.customHooks.push({ name, line: node.loc.start.line });
        if (/^(handle|on)[A-Z_]/.test(name)) handlerNames.add(name);
      }
    },
    ClassDeclaration(path) {
      const node = path.node;
      const name = node.id ? node.id.name : "(anonymous)";
      out.classes.push({ name, line: node.loc.start.line, methods: (node.body.body || []).filter((m) => m.type === "ClassMethod").map((m) => m.key.name || "?") });
      const extendsReact = node.superClass && ((node.superClass.object && node.superClass.object.name === "React") || node.superClass.name === "Component" || node.superClass.name === "PureComponent");
      if (extendsReact && /^[A-Z]/.test(name)) {
        componentNames.add(name);
        out.reactComponents.push({ name, line: node.loc.start.line, props: [], doc: docOf(node) });
      }
    },
    ExportNamedDeclaration(path) {
      const decl = path.node.declaration;
      if (decl) {
        if (decl.id) out.exports.push(decl.id.name);
        else if (decl.declarations) decl.declarations.forEach((d) => d.id && out.exports.push(d.id.name));
      } else if (path.node.specifiers) {
        path.node.specifiers.forEach((s) => out.exports.push(s.exported.name || s.exported.value));
      }
    },
    ExportDefaultDeclaration() { out.exports.push("default"); },
    ImportDeclaration(path) {
      out.imports.push(path.node.source.value);
    },
    CallExpression(path) {
      const callee = path.node.callee;
      const name = callee.name || (callee.property && callee.property.name) || "";
      if (/^use[A-Z]/.test(name) && !out.hooksUsed.includes(name)) out.hooksUsed.push(name);
      if (name === "fetch" || name === "axios" || (callee.object && callee.object.name === "axios")) {
        const arg0 = path.node.arguments[0];
        let url = "";
        if (arg0 && arg0.type === "StringLiteral") url = arg0.value;
        else if (arg0 && arg0.type === "TemplateLiteral" && arg0.quasis[0]) url = arg0.quasis[0].value.cooked + "…";
        let method = "GET";
        const opt = path.node.arguments[1];
        if (opt && opt.properties) {
          for (const p of opt.properties) {
            if (p.key && p.key.name === "method" && p.value && p.value.value) method = String(p.value.value).toUpperCase();
          }
        }
        out.fetchCalls.push({ url, method, line: path.node.loc.start.line });
      }
      if (name === "createSlice" || name === "createStore" || name === "defineStore") {
        out.classes.push({ name: `store:${name}`, line: path.node.loc.start.line, methods: [] });
      }
    },
    JSXAttribute(path) {
      const name = path.node.name && path.node.name.name;
      if (/^on[A-Z]/.test(name || "")) {
        let value = "";
        const v = path.node.value;
        if (v && v.expression && v.expression.name) value = v.expression.name;
        else if (v && v.body) value = "inline";
        out.eventHandlers.push({ prop: name, handler: value, line: path.node.loc.start.line });
        if (value && value !== "inline") handlerNames.add(value);
      }
    },
    JSXOpeningElement(path) {
      if (path.node.name && path.node.name.name === "Route") {
        const attrs = {};
        path.node.attributes.forEach((a) => {
          if (a.name && a.value && a.value.value !== undefined && a.value.type === "StringLiteral") {
            attrs[a.name.name] = a.value.value;
          }
        });
        if (attrs.path) out.routes.push({ path: attrs.path, line: path.node.loc.start.line });
      }
    },
  });

  out.eventHandlers = out.eventHandlers.map((h) => ({
    ...h,
    isDefined: h.handler !== "inline" ? handlerNames.has(h.handler) || componentNames.has(h.handler) : true,
  }));
  results.push(out);
}

process.stdout.write(JSON.stringify(results));
