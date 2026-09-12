/** Editor state: current workspace, UI document, selection, undo/redo history.
 *  Plain React context + useReducer — no external state library. */
import { createContext, useCallback, useContext, useMemo, useReducer, useRef } from "react";
import type { BBox, UIComponent, UIDocument, Workspace } from "../types";

const HISTORY_LIMIT = 60;

interface EditorState {
  workspace: Workspace | null;
  doc: UIDocument | null;
  selectedId: string | null;
  past: UIDocument[];
  future: UIDocument[];
  dirty: boolean;
  lastSavedVersion: number;
}

type Action =
  | { type: "workspace"; workspace: Workspace | null }
  | { type: "document"; doc: UIDocument | null; resetHistory?: boolean; version?: number }
  | { type: "select"; id: string | null }
  | { type: "mutate"; next: (components: UIComponent[], screen: UIDocument["screen"]) =>
      [UIComponent[], UIDocument["screen"]] }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "saved"; version: number }
  | { type: "screen"; screen: UIDocument["screen"] }
  | { type: "metadata"; metadata: Record<string, unknown> };

function reducer(state: EditorState, action: Action): EditorState {
  switch (action.type) {
    case "workspace":
      return { ...state, workspace: action.workspace };
    case "document": {
      const version = action.version ?? state.lastSavedVersion;
      return {
        ...state,
        doc: action.doc,
        past: action.resetHistory ? [] : state.past,
        future: action.resetHistory ? [] : state.future,
        dirty: false,
        lastSavedVersion: version,
        selectedId: null,
      };
    }
    case "select":
      return { ...state, selectedId: action.id };
    case "mutate": {
      if (!state.doc) return state;
      const [components, screen] = action.next(state.doc.components, state.doc.screen);
      const nextDoc: UIDocument = { ...state.doc, components, screen };
      return {
        ...state,
        doc: nextDoc,
        past: [...state.past, state.doc].slice(-HISTORY_LIMIT),
        future: [],
        dirty: true,
      };
    }
    case "undo": {
      if (!state.past.length) return state;
      const previous = state.past[state.past.length - 1];
      return {
        ...state,
        doc: previous,
        past: state.past.slice(0, -1),
        future: [state.doc as UIDocument, ...state.future].slice(0, HISTORY_LIMIT),
        dirty: true,
      };
    }
    case "redo": {
      if (!state.future.length) return state;
      const [next, ...rest] = state.future;
      return {
        ...state,
        doc: next,
        past: [...state.past, state.doc as UIDocument].slice(-HISTORY_LIMIT),
        future: rest,
        dirty: true,
      };
    }
    case "saved":
      return { ...state, dirty: false, lastSavedVersion: action.version };
    case "screen":
      if (!state.doc) return state;
      return {
        ...state,
        doc: { ...state.doc, screen: action.screen },
        past: [...state.past, state.doc].slice(-HISTORY_LIMIT),
        future: [], dirty: true,
      };
    case "metadata":
      if (!state.doc) return state;
      return {
        ...state,
        doc: { ...state.doc, metadata: { ...state.doc.metadata, ...action.metadata } },
        dirty: true,
      };
    default:
      return state;
  }
}

export interface EditorApi {
  state: EditorState;
  setWorkspace(ws: Workspace | null): void;
  loadDocument(doc: UIDocument | null, version?: number): void;
  select(id: string | null): void;
  mutate(next: (components: UIComponent[], screen: UIDocument["screen"]) =>
    [UIComponent[], UIDocument["screen"]]): void;
  updateComponent(id: string, patch: Partial<UIComponent>): void;
  updateBBox(id: string, bbox: Partial<BBox>): void;
  setText(id: string, text: string): void;
  setStyle(id: string, key: string, value: unknown): void;
  addComponent(type: UIComponent["type"], parent: string | null, bbox: BBox): string;
  deleteComponent(id: string): void;
  duplicateComponent(id: string): void;
  reparent(id: string, parentId: string): void;
  undo(): void;
  redo(): void;
  markSaved(version: number): void;
  setScreen(width: number, height: number, preset: string | null): void;
  patchMetadata(partial: Record<string, unknown>): void;
  selected(): UIComponent | null;
  byId(id: string): UIComponent | undefined;
  childrenOf(parentId: string): UIComponent[];
  nextId(): string;
}

const EditorContext = createContext<EditorApi | null>(null);

export function EditorProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    workspace: null,
    doc: null,
    selectedId: null,
    past: [],
    future: [],
    dirty: false,
    lastSavedVersion: 0,
  });
  const idCounter = useRef(0);

  const mutate = useCallback((next: Parameters<Action extends never ? never : EditorApi["mutate"]>[0]) => {
    dispatch({ type: "mutate", next });
  }, []);

  const apiImpl = useMemo<EditorApi>(() => {
    const find = (components: UIComponent[], id: string) => components.find((c) => c.id === id);
    return {
      state,
      setWorkspace: (ws) => dispatch({ type: "workspace", workspace: ws }),
      loadDocument: (doc, version) =>
        dispatch({ type: "document", doc, version, resetHistory: true }),
      select: (id) => dispatch({ type: "select", id }),
      mutate,
      updateComponent: (id, patch) =>
        mutate((components, screen) => [
          components.map((c) => (c.id === id ? { ...c, ...patch } : c)),
          screen,
        ]),
      updateBBox: (id, bbox) =>
        mutate((components, screen) => [
          components.map((c) =>
            c.id === id ? { ...c, bbox: { ...c.bbox, ...bbox } } : c),
          screen,
        ]),
      setText: (id, text) =>
        mutate((components, screen) => [
          components.map((c) => (c.id === id ? { ...c, text } : c)),
          screen,
        ]),
      setStyle: (id, key, value) =>
        mutate((components, screen) => [
          components.map((c) => {
            if (c.id !== id) return c;
            const styles = { ...c.styles };
            if (value === null || value === undefined || value === "") delete styles[key];
            else styles[key] = value;
            return { ...c, styles };
          }),
          screen,
        ]),
      addComponent: (type, parent, bbox) => {
        idCounter.current += 1;
        const id = `component_new_${Date.now().toString(36)}_${idCounter.current}`;
        mutate((components, screen) => {
          const comp: UIComponent = {
            id, type, name: `${type}-${idCounter.current}`, parent_id: parent ?? "screen",
            children: [], bbox, text: type === "text" || type === "heading" || type === "button"
              ? "Nuevo texto" : null,
            styles: {}, states: {}, events: {}, bindings: [],
            metadata: { confidence: 1.0, source: "manual" },
          };
          const next = components.map((c) =>
            c.id === (parent ?? "screen") ? { ...c, children: [...c.children, id] } : c);
          return [[...next, comp], screen];
        });
        return id;
      },
      deleteComponent: (id) => {
        const doomed = new Set<string>([id]);
        let grew = true;
        while (grew) {
          grew = false;
          for (const c of state.doc?.components ?? []) {
            if (c.parent_id && doomed.has(c.parent_id) && !doomed.has(c.id)) {
              doomed.add(c.id);
              grew = true;
            }
          }
        }
        mutate((components, screen) => [
          components
            .filter((c) => !doomed.has(c.id))
            .map((c) => ({
              ...c,
              parent_id: doomed.has(c.parent_id ?? "") ? "screen" : c.parent_id,
              children: c.children.filter((ch) => !doomed.has(ch)),
            })),
          screen,
        ]);
        if (state.selectedId && doomed.has(state.selectedId)) dispatch({ type: "select", id: null });
      },
      duplicateComponent: (id) => {
        const src = find(state.doc?.components ?? [], id);
        if (!src) return;
        idCounter.current += 1;
        const nid = `component_new_${Date.now().toString(36)}_${idCounter.current}`;
        mutate((components, screen) => {
          const copy: UIComponent = {
            ...src, id: nid, name: `${src.name}-copy`,
            bbox: { ...src.bbox, x: src.bbox.x + 16, y: src.bbox.y + 16 },
            children: [], bindings: [], metadata: { ...src.metadata, source: "manual" },
          };
          const updated = components.map((c) =>
            c.id === src.parent_id ? { ...c, children: [...c.children, nid] } : c);
          return [[...updated, copy], screen];
        });
      },
      reparent: (id, parentId) =>
        mutate((components, screen) => [
          components.map((c) => {
            if (c.id === id) return { ...c, parent_id: parentId };
            if (c.id === parentId) return { ...c, children: [...new Set([...c.children, id])] };
            return { ...c, children: c.children.filter((ch) => ch !== id) };
          }),
          screen,
        ]),
      undo: () => dispatch({ type: "undo" }),
      redo: () => dispatch({ type: "redo" }),
      markSaved: (version) => dispatch({ type: "saved", version }),
      setScreen: (width, height, preset) =>
        dispatch({ type: "screen", screen: { ...((state.doc?.screen ?? {
          id: "screen", width: 1280, height: 800, background: null, preset: null,
        } as UIDocument["screen"])), width, height, preset } }),
      patchMetadata: (partial) => dispatch({ type: "metadata", metadata: partial }),
      selected: () =>
        (state.doc?.components ?? []).find((c) => c.id === state.selectedId) ?? null,
      byId: (id) => find(state.doc?.components ?? [], id),
      childrenOf: (parentId) =>
        (state.doc?.components ?? []).filter((c) => c.parent_id === parentId),
      nextId: () => {
        idCounter.current += 1;
        return `component_new_${Date.now().toString(36)}_${idCounter.current}`;
      },
    };
  }, [state, mutate]);

  return <EditorContext.Provider value={apiImpl}>{children}</EditorContext.Provider>;
}

export function useEditor(): EditorApi {
  const ctx = useContext(EditorContext);
  if (!ctx) throw new Error("useEditor must be used within EditorProvider");
  return ctx;
}
