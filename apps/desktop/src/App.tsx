/** UI Binder — application shell: toolbar / tree / canvas / inspector / dock. */
import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import { BottomDock, type DockTab } from "./components/BottomDock";
import { Canvas } from "./components/Canvas";
import { CommandPalette, SearchOverlay } from "./components/CommandPalette";
import { Inspector } from "./components/Inspector";
import { PreviewPane } from "./components/PreviewPane";
import { PromptModal } from "./components/PromptModal";
import { StatusBar } from "./components/StatusBar";
import { Toolbar, type ToolbarActions } from "./components/Toolbar";
import { TreePanel } from "./components/TreePanel";
import { WorkspaceDialog } from "./components/WorkspaceDialog";
import { EditorProvider, useEditor } from "./state/editorStore";
import type { Binding, Health, Workspace } from "./types";

function Shell() {
  const editor = useEditor();
  const [health, setHealth] = useState<"ok" | "degraded" | "checking">("checking");
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<{ kind: "info" | "error"; text: string } | null>(null);
  const [dockTab, setDockTab] = useState<DockTab>("orphans");
  const [showPalette, setShowPalette] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [showWorkspaces, setShowWorkspaces] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [prompt, setPrompt] = useState<{
    title: string; placeholder?: string; initial?: string;
    validate?: (v: string) => string | null;
    onSubmit: (v: string) => void;
  } | null>(null);
  const [stats, setStats] = useState({
    capabilities: 0, bindings: 0, broken: 0, unbound: 0,
    fidelity: null as number | null, coverage: null as number | null,
  });

  const notify = useCallback((kind: "info" | "error", text: string) => {
    setToast({ kind, text });
    setTimeout(() => setToast(null), 6000);
  }, []);

  const wrap = useCallback(async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    try {
      await fn();
    } catch (e) {
      const err = e as { status?: number; message?: string; detail?: unknown };
      const detail = err.detail ?? "";
      notify("error", `${label} falló — ${err.message ?? String(e)} ${typeof detail === "string" ? detail : ""}`.slice(0, 400));
    } finally {
      setBusy(null);
    }
  }, [notify]);

  // ---- boot
  useEffect(() => {
    (async () => {
      try {
        const h = await api.health();
        setHealth(h.status === "ok" ? "ok" : "degraded");
      } catch {
        setHealth("degraded");
      }
      const list = await api.listWorkspaces();
      const last = localStorage.getItem("uibinder.workspace");
      const target = list.find((w) => w.id === last) ?? list[0];
      if (target) await openWorkspace(target);
    })().catch(() => notify("error", "Backend no disponible en http://127.0.0.1:8765 — ejecuta scripts/dev.py"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshStats = useCallback(async (wsId: string) => {
    try {
      const [caps, bindings] = await Promise.all([api.capabilities(wsId), api.bindings(wsId)]);
      const broken = bindings.filter((b: Binding) => b.status === "BROKEN").length;
      const boundCaps = new Set(bindings.filter((b) => b.status === "CONFIRMED").map((b) => b.target_capability));
      setStats({
        capabilities: caps.length, bindings: bindings.length, broken,
        unbound: caps.filter((c) => !c.legacy && !boundCaps.has(c.capability_id)).length,
        fidelity: stats.fidelity, coverage: caps.length
          ? Math.round((boundCaps.size / caps.length) * 1000) / 10 : null,
      });
    } catch { /* stats are best-effort */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openWorkspace = useCallback(async (ws: Workspace) => {
    editor.setWorkspace(ws);
    localStorage.setItem("uibinder.workspace", ws.id);
    try {
      const doc = await api.getUi(ws.id);
      editor.loadDocument(doc);
    } catch {
      editor.loadDocument(null);
    }
    await refreshStats(ws.id);
    setShowWorkspaces(false);
  }, [editor, refreshStats]);

  const requireWs = (): Workspace | null => {
    const ws = editor.state.workspace;
    if (!ws) { notify("error", "Abre o crea un workspace primero."); }
    return ws;
  };

  // ---- keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const ctrl = e.ctrlKey || e.metaKey;
      if (ctrl && e.key.toLowerCase() === "k") { e.preventDefault(); setShowPalette((v) => !v); }
      else if (ctrl && e.shiftKey && e.key.toLowerCase() === "f") { e.preventDefault(); setShowSearch(true); }
      else if (ctrl && e.key.toLowerCase() === "s") {
        e.preventDefault();
        const ws = editor.state.workspace;
        if (ws && editor.state.doc) {
          void wrap("Save", async () => {
            const r = await api.saveUi(ws.id, editor.state.doc!);
            editor.markSaved(r.version);
            notify("info", `Guardado (v${r.version}, ${r.components} componentes)`);
          });
        }
      }
      else if (ctrl && e.key.toLowerCase() === "z") { e.preventDefault(); editor.undo(); }
      else if (ctrl && (e.key.toLowerCase() === "y" || (e.shiftKey && e.key.toLowerCase() === "z"))) {
        e.preventDefault(); editor.redo();
      }
      else if ((e.key === "Delete" || e.key === "Backspace") && editor.state.selectedId
        && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        editor.deleteComponent(editor.state.selectedId);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editor, wrap, notify]);

  const actions: ToolbarActions = {
    newWorkspace: () => setShowWorkspaces(true),
    switchWorkspace: () => setShowWorkspaces(true),
    importScreenshot: (file) => {
      const ws = requireWs();
      if (!ws) return;
      void wrap("Import image", async () => {
        const img = await api.uploadImage(ws.id, file);
        notify("info", `Imagen importada: ${img.width}×${img.height} (${img.format})`);
      });
    },
    analyzeUi: () => {
      const ws = requireWs();
      if (!ws) return;
      void wrap("Analyze UI", async () => {
        const r = await api.analyzeUi(ws.id, "heuristic");
        const doc = await api.getUi(ws.id);
        editor.loadDocument(doc);
        notify("info", `${r.components} componentes detectados — corrige y edita en el inspector`);
      });
    },
    importProject: () => {
      const ws = requireWs();
      if (!ws) return;
      setShowPalette(false);
      setPrompt({
        title: "IMPORT PROJECT (READ-ONLY)",
        placeholder: "C:\\ruta\\absoluta\\del\\proyecto",
        validate: (v) => (v.trim() ? null : "Introduce una ruta."),
        onSubmit: (path) => {
          setPrompt(null);
          void wrap("Import project", async () => {
            const r = await api.importProject(ws.id, path.trim());
            notify("info", `Proyecto importado read-only: ${r.file_count} archivos, [${r.frameworks.join(", ")}]`);
          });
        },
      });
    },
    analyzeProject: () => {
      const ws = requireWs();
      if (!ws) return;
      void wrap("Analyze project", async () => {
        const r = await api.analyzeProject(ws.id);
        await refreshStats(ws.id);
        notify("info", `${r.capabilities} capabilities, ${r.edges} relaciones en el grafo`);
      });
    },
    verify: () => {
      const ws = requireWs();
      if (!ws) return;
      setDockTab("orphans");
      void wrap("Verify", async () => {
        const r = await api.verify(ws.id);
        await refreshStats(ws.id);
        setStats((s) => ({ ...s, coverage: r.scores.functional_coverage, fidelity: r.scores.visual_fidelity }));
      });
    },
    exportProject: () => {
      const ws = requireWs();
      if (!ws) return;
      setPrompt({
        title: "EXPORT PROJECT (directorio nuevo y vacío)",
        placeholder: "C:\\ruta\\nueva\\vacía",
        validate: (v) => (v.trim() ? null : "Introduce una ruta."),
        onSubmit: (target) => {
          setPrompt(null);
          void wrap("Export", async () => {
            const r = await api.exportProject(ws.id, target.trim());
            const files = (r as { files_created?: string[] }).files_created?.length ?? 0;
            notify("info", `Exportado a ${target.trim()} — ${files} archivos`);
          });
        },
      });
    },
    save: () => {
      const ws = editor.state.workspace;
      if (!ws || !editor.state.doc) { notify("error", "Nada que guardar."); return; }
      void wrap("Save", async () => {
        const r = await api.saveUi(ws.id, editor.state.doc!);
        editor.markSaved(r.version);
        notify("info", `Guardado v${r.version}`);
      });
    },
    snapshot: () => {
      const ws = requireWs();
      if (!ws) return;
      void wrap("Snapshot", async () => {
        await api.snapshot(ws.id, `snapshot ${new Date().toLocaleString()}`);
        notify("info", "Snapshot creado");
      });
    },
    togglePreview: () => setShowPreview((v) => !v),
    openPalette: () => setShowPalette(true),
    openSearch: () => setShowSearch(true),
  };

  useEffect(() => {
    const id = editor.state.workspace?.id;
    if (id) void refreshStats(id);
  }, [editor.state.workspace?.id, refreshStats]);

  return (
    <div className="app">
      <Toolbar actions={actions} busy={busy} health={health} />
      <div className="main">
        <TreePanel />
        <div className="center">
          {showPreview
            ? <PreviewPane onClose={() => setShowPreview(false)} />
            : <Canvas />}
        </div>
        <Inspector />
      </div>
      <BottomDock tab={dockTab} setTab={setDockTab} onFidelity={(v) => setStats((s) => ({ ...s, coverage: v }))} />
      <StatusBar {...stats} />
      {toast && <div className={`toast toast-${toast.kind}`}>{toast.text}</div>}
      {showPalette && <CommandPalette actions={actions} onClose={() => setShowPalette(false)} />}
      {showSearch && <SearchOverlay onClose={() => setShowSearch(false)}
        onSelectComponent={(id) => editor.select(id)} />}
      {showWorkspaces && <WorkspaceDialog onClose={() => setShowWorkspaces(false)} onOpened={openWorkspace} />}
      {prompt && <PromptModal title={prompt.title} placeholder={prompt.placeholder}
        initial={prompt.initial} validate={prompt.validate}
        onSubmit={prompt.onSubmit} onCancel={() => setPrompt(null)} />}
    </div>
  );
}

export default function App() {
  return (
    <EditorProvider>
      <Shell />
    </EditorProvider>
  );
}
