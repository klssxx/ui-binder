"""WorkspaceStore — typed CRUD over SQLite for every persisted entity."""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from backend.persistence.db import connect, utcnow

def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


J = json.dumps


class CorruptDocumentError(ValueError):
    """Persisted UI document JSON is unreadable — needs snapshot restore or re-analysis."""


def _loads(raw: Optional[str], default: Any) -> Any:
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


class WorkspaceStore:
    """All persistence goes through here; callers stay SQL-free."""

    # ---------- workspaces ----------

    def create_workspace(self, name: str, notes: str = "") -> dict[str, Any]:
        ws = {
            "id": _uid("ws"),
            "name": name.strip() or "Untitled",
            "status": "active",
            "notes": notes,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        with connect() as conn:
            conn.execute(
                "INSERT INTO workspaces (id, name, status, notes, created_at, updated_at) "
                "VALUES (:id, :name, :status, :notes, :created_at, :updated_at)",
                ws,
            )
        return ws

    def list_workspaces(self) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute("SELECT * FROM workspaces ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_workspace(self, ws_id: str) -> Optional[dict[str, Any]]:
        with connect() as conn:
            row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
        return dict(row) if row else None

    def workspace_exists(self, ws_id: str) -> bool:
        return self.get_workspace(ws_id) is not None

    def rename_workspace(self, ws_id: str, name: str, notes: Optional[str] = None) -> Optional[dict[str, Any]]:
        with connect() as conn:
            if notes is not None:
                conn.execute(
                    "UPDATE workspaces SET name = ?, notes = ?, updated_at = ? WHERE id = ?",
                    (name, notes, utcnow(), ws_id),
                )
            else:
                conn.execute(
                    "UPDATE workspaces SET name = ?, updated_at = ? WHERE id = ?",
                    (name, utcnow(), ws_id),
                )
            row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
        return dict(row) if row else None

    def delete_workspace(self, ws_id: str) -> bool:
        with connect() as conn:
            cur = conn.execute("DELETE FROM workspaces WHERE id = ?", (ws_id,))
        return cur.rowcount > 0

    # ---------- images ----------

    def add_image(self, ws_id: str, *, role: str, filename: str, path: str,
                  width: int, height: int, size_bytes: int, fmt: str, sha256: str) -> dict[str, Any]:
        img = {
            "id": _uid("img"),
            "workspace_id": ws_id,
            "role": role,
            "filename": filename,
            "path": path,
            "width": width,
            "height": height,
            "size_bytes": size_bytes,
            "format": fmt,
            "sha256": sha256,
            "created_at": utcnow(),
        }
        with connect() as conn:
            conn.execute(
                "INSERT INTO images (id, workspace_id, role, filename, path, width, height, "
                "size_bytes, format, sha256, created_at) VALUES (:id, :workspace_id, :role, "
                ":filename, :path, :width, :height, :size_bytes, :format, :sha256, :created_at)",
                img,
            )
        return img

    def get_image(self, image_id: str) -> Optional[dict[str, Any]]:
        with connect() as conn:
            row = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
        return dict(row) if row else None

    def get_reference_image(self, ws_id: str) -> Optional[dict[str, Any]]:
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM images WHERE workspace_id = ? AND role = 'reference' "
                "ORDER BY created_at DESC LIMIT 1",
                (ws_id,),
            ).fetchone()
        return dict(row) if row else None

    # ---------- UI document (AST) ----------

    def get_ui_document(self, ws_id: str) -> Optional[dict[str, Any]]:
        with connect() as conn:
            row = conn.execute(
                "SELECT json, version, updated_at FROM ui_documents WHERE workspace_id = ?",
                (ws_id,),
            ).fetchone()
        if not row:
            return None
        raw = row["json"]
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise CorruptDocumentError(
                    f"Persisted UI document is corrupt (version {row['version']}, "
                    f"updated {row['updated_at']}): {exc.msg} at pos {exc.pos}. "
                    "Restore a snapshot or re-run Analyze UI."
                ) from exc
            if not isinstance(parsed, dict):
                raise CorruptDocumentError(
                    f"Persisted UI document is not an object (version {row['version']}).")
            return {"json": parsed, "version": row["version"], "updated_at": row["updated_at"]}
        return {"json": _loads(raw, {}), "version": row["version"], "updated_at": row["updated_at"]}

    def save_ui_document(self, ws_id: str, doc: dict[str, Any]) -> None:
        now = utcnow()
        with connect() as conn:
            existing = conn.execute(
                "SELECT version FROM ui_documents WHERE workspace_id = ?", (ws_id,)
            ).fetchone()
            version = (existing["version"] + 1) if existing else 1
            conn.execute(
                "INSERT INTO ui_documents (workspace_id, json, version, updated_at) VALUES (?,?,?,?) "
                "ON CONFLICT(workspace_id) DO UPDATE SET json = excluded.json, "
                "version = excluded.version, updated_at = excluded.updated_at",
                (ws_id, json.dumps(doc, ensure_ascii=False), version, now),
            )
            conn.execute("UPDATE workspaces SET updated_at = ? WHERE id = ?", (now, ws_id))

    # ---------- snapshots ----------

    def create_snapshot(self, ws_id: str, label: str) -> dict[str, Any]:
        current = self.get_ui_document(ws_id) or {"json": {}}
        snap = {
            "id": _uid("snap"),
            "workspace_id": ws_id,
            "label": label or f"snapshot {utcnow()}",
            "json": current["json"],
            "created_at": utcnow(),
        }
        with connect() as conn:
            conn.execute(
                "INSERT INTO snapshots (id, workspace_id, label, json, created_at) "
                "VALUES (:id, :workspace_id, :label, :json, :created_at)",
                {**snap, "json": json.dumps(snap["json"], ensure_ascii=False)},
            )
        return snap

    def list_snapshots(self, ws_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT id, workspace_id, label, created_at FROM snapshots "
                "WHERE workspace_id = ? ORDER BY created_at DESC",
                (ws_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def restore_snapshot(self, ws_id: str, snapshot_id: str) -> Optional[dict[str, Any]]:
        with connect() as conn:
            row = conn.execute(
                "SELECT json FROM snapshots WHERE id = ? AND workspace_id = ?",
                (snapshot_id, ws_id),
            ).fetchone()
        if not row:
            return None
        raw = row["json"]
        try:
            parsed = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
        except json.JSONDecodeError as exc:
            raise CorruptDocumentError(
                f"Snapshot '{snapshot_id}' is corrupt: {exc.msg} at pos {exc.pos}.") from exc
        self.save_ui_document(ws_id, parsed)
        return self.get_ui_document(ws_id)

    # ---------- projects ----------

    def upsert_project(self, ws_id: str, path: str, frameworks: list[str], languages: list[str],
                       entrypoints: list[str], manifests: list[dict], summary: dict) -> dict[str, Any]:
        now = utcnow()
        with connect() as conn:
            row = conn.execute(
                "SELECT id FROM projects WHERE workspace_id = ?", (ws_id,)
            ).fetchone()
            if row:
                pid = row["id"]
                conn.execute(
                    "UPDATE projects SET path=?, frameworks=?, languages=?, entrypoints=?, "
                    "manifests=?, summary=?, updated_at=? WHERE id=?",
                    (path, J(frameworks), J(languages), J(entrypoints),
                     json.dumps(manifests), json.dumps(summary), now, pid),
                )
            else:
                pid = _uid("proj")
                conn.execute(
                    "INSERT INTO projects (id, workspace_id, path, read_only, frameworks, languages, "
                    "entrypoints, manifests, summary, created_at, updated_at) "
                    "VALUES (?,?,?,1,?,?,?,?,?,?,?)",
                    (pid, ws_id, path, J(frameworks), J(languages), J(entrypoints),
                     json.dumps(manifests), json.dumps(summary), now, now),
                )
            conn.execute("DELETE FROM project_files WHERE project_id = ?", (pid,))
        return {"id": pid, "workspace_id": ws_id, "path": path, "read_only": True}

    def get_project(self, ws_id: str) -> Optional[dict[str, Any]]:
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE workspace_id = ? ORDER BY updated_at DESC LIMIT 1",
                (ws_id,),
            ).fetchone()
        if not row:
            return None
        proj = dict(row)
        proj["frameworks"] = _loads(proj["frameworks"], [])
        proj["languages"] = _loads(proj["languages"], [])
        proj["entrypoints"] = _loads(proj["entrypoints"], [])
        proj["manifests"] = _loads(proj["manifests"], [])
        proj["summary"] = _loads(proj["summary"], {})
        proj["read_only"] = bool(proj["read_only"])
        return proj

    def set_project_files(self, project_id: str, files: list[dict[str, Any]]) -> None:
        with connect() as conn:
            for f in files:
                conn.execute(
                    "INSERT INTO project_files (id, project_id, rel_path, language, role, analysis) "
                    "VALUES (?,?,?,?,?,?)",
                    (_uid("file"), project_id, f["rel_path"], f.get("language", "unknown"),
                     f.get("role", "source"), json.dumps(f.get("analysis", {}))),
                )

    def list_project_files(self, project_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT rel_path, language, role, analysis FROM project_files "
                "WHERE project_id = ? ORDER BY rel_path",
                (project_id,),
            ).fetchall()
        out = []
        for r in rows:
            out.append({
                "rel_path": r["rel_path"], "language": r["language"],
                "role": r["role"], "analysis": _loads(r["analysis"], {}),
            })
        return out

    # ---------- capabilities ----------

    def replace_capabilities(self, ws_id: str, caps: list[dict[str, Any]]) -> int:
        with connect() as conn:
            conn.execute("DELETE FROM capabilities WHERE workspace_id = ?", (ws_id,))
            for c in caps:
                conn.execute(
                    "INSERT INTO capabilities (capability_id, workspace_id, kind, name, qualified_name, "
                    "description, inputs, outputs, side_effects, origin_file, origin_line, framework, "
                    "http_method, http_path, dependencies, legacy, confidence) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (c["capability_id"], ws_id, c["kind"], c["name"], c["qualified_name"],
                     c.get("description", ""), J(c.get("inputs", [])), J(c.get("outputs", [])),
                     J(c.get("side_effects", [])), c.get("origin_file", ""),
                     int(c.get("origin_line", 0)), c.get("framework", "unknown"),
                     c.get("http_method", ""), c.get("http_path", ""),
                     J(c.get("dependencies", [])), int(c.get("legacy", False)),
                     float(c.get("confidence", 0.5))),
                )
        return len(caps)

    def list_capabilities(self, ws_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM capabilities WHERE workspace_id = ? ORDER BY kind, qualified_name",
                (ws_id,),
            ).fetchall()
        out = []
        for r in rows:
            c = dict(r)
            c["inputs"] = _loads(c["inputs"], [])
            c["outputs"] = _loads(c["outputs"], [])
            c["side_effects"] = _loads(c["side_effects"], [])
            c["dependencies"] = _loads(c["dependencies"], [])
            c["legacy"] = bool(c["legacy"])
            out.append(c)
        return out

    def set_capability_legacy(self, ws_id: str, capability_id: str, legacy: bool) -> bool:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE capabilities SET legacy = ? WHERE capability_id = ? AND workspace_id = ?",
                (int(legacy), capability_id, ws_id),
            )
        return cur.rowcount > 0

    # ---------- bindings ----------

    def create_binding(self, ws_id: str, data: dict[str, Any]) -> dict[str, Any]:
        now = utcnow()
        b = {
            "binding_id": data.get("binding_id") or _uid("bind"),
            "workspace_id": ws_id,
            "component_id": data["component_id"],
            "event": data.get("event", "onClick"),
            "target_capability": data["target_capability"],
            "input_mapping": data.get("input_mapping", []),
            "output_mapping": data.get("output_mapping", []),
            "loading_mapping": data.get("loading_mapping", ""),
            "error_mapping": data.get("error_mapping", ""),
            "transformations": data.get("transformations", []),
            "confidence": float(data.get("confidence", 0.0)),
            "status": data.get("status", "SUGGESTED"),
            "rationale": data.get("rationale", []),
            "created_at": now,
            "updated_at": now,
        }
        with connect() as conn:
            conn.execute(
                "INSERT INTO bindings (binding_id, workspace_id, component_id, event, target_capability, "
                "input_mapping, output_mapping, loading_mapping, error_mapping, transformations, "
                "confidence, status, rationale, created_at, updated_at) "
                "VALUES (:binding_id, :workspace_id, :component_id, :event, :target_capability, "
                ":input_mapping, :output_mapping, :loading_mapping, :error_mapping, :transformations, "
                ":confidence, :status, :rationale, :created_at, :updated_at)",
                {**b,
                 "input_mapping": J(b["input_mapping"]),
                 "output_mapping": J(b["output_mapping"]),
                 "transformations": J(b["transformations"]),
                 "rationale": J(b["rationale"])},
            )
        return self.get_binding(ws_id, b["binding_id"])  # type: ignore[return-value]

    def update_binding(self, ws_id: str, binding_id: str, changes: dict[str, Any]) -> Optional[dict[str, Any]]:
        json_fields = {"input_mapping", "output_mapping", "transformations", "rationale"}
        straight = {"component_id", "event", "target_capability", "loading_mapping",
                    "error_mapping", "confidence", "status"}
        sets, vals = [], []
        for k, v in changes.items():
            if k in json_fields:
                sets.append(f"{k} = ?")
                vals.append(J(v))
            elif k in straight:
                sets.append(f"{k} = ?")
                vals.append(v)
        if not sets:
            return self.get_binding(ws_id, binding_id)
        sets.append("updated_at = ?")
        vals.append(utcnow())
        vals.extend([binding_id, ws_id])
        with connect() as conn:
            cur = conn.execute(
                f"UPDATE bindings SET {', '.join(sets)} WHERE binding_id = ? AND workspace_id = ?", vals
            )
            if cur.rowcount == 0:
                return None
        return self.get_binding(ws_id, binding_id)

    def delete_binding(self, ws_id: str, binding_id: str) -> bool:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM bindings WHERE binding_id = ? AND workspace_id = ?", (binding_id, ws_id)
            )
        return cur.rowcount > 0

    def get_binding(self, ws_id: str, binding_id: str) -> Optional[dict[str, Any]]:
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM bindings WHERE binding_id = ? AND workspace_id = ?",
                (binding_id, ws_id),
            ).fetchone()
        return _expand_binding(row) if row else None

    def list_bindings(self, ws_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM bindings WHERE workspace_id = ? ORDER BY created_at", (ws_id,)
            ).fetchall()
        return [_expand_binding(r) for r in rows]

    # ---------- verification / diffs / trace / logs ----------

    def save_verification_run(self, ws_id: str, report: dict[str, Any]) -> dict[str, Any]:
        run = {"id": _uid("ver"), "workspace_id": ws_id, "report": report, "created_at": utcnow()}
        with connect() as conn:
            conn.execute(
                "INSERT INTO verification_runs (id, workspace_id, report, created_at) VALUES (?,?,?,?)",
                (run["id"], ws_id, json.dumps(report, ensure_ascii=False), run["created_at"]),
            )
        return run

    def latest_verification(self, ws_id: str) -> Optional[dict[str, Any]]:
        with connect() as conn:
            row = conn.execute(
                "SELECT report, created_at FROM verification_runs WHERE workspace_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (ws_id,),
            ).fetchone()
        return {"report": _loads(row["report"], {}), "created_at": row["created_at"]} if row else None

    def save_visual_diff(self, ws_id: str, reference: str, rendered: str,
                         metrics: dict[str, Any], fidelity: float) -> dict[str, Any]:
        d = {
            "id": _uid("diff"), "workspace_id": ws_id, "reference_image": reference,
            "rendered_image": rendered, "metrics": metrics, "fidelity": fidelity,
            "created_at": utcnow(),
        }
        with connect() as conn:
            conn.execute(
                "INSERT INTO visual_diffs (id, workspace_id, reference_image, rendered_image, metrics, "
                "fidelity, created_at) VALUES (?,?,?,?,?,?,?)",
                (d["id"], ws_id, reference, rendered,
                 json.dumps(metrics, ensure_ascii=False), fidelity, d["created_at"]),
            )
        return d

    def list_visual_diffs(self, ws_id: str) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT * FROM visual_diffs WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 20",
                (ws_id,),
            ).fetchall()
        return [{**dict(r), "metrics": _loads(r["metrics"], {})} for r in rows]

    def add_trace_event(self, ws_id: str, event: dict[str, Any]) -> None:
        with connect() as conn:
            conn.execute(
                "INSERT INTO trace_events (workspace_id, ts, event) VALUES (?,?,?)",
                (ws_id, utcnow(), json.dumps(event, ensure_ascii=False)),
            )

    def list_trace_events(self, ws_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT ts, event FROM trace_events WHERE workspace_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (ws_id, limit),
            ).fetchall()
        return [{"ts": r["ts"], **_loads(r["event"], {})} for r in reversed(rows)]

    def list_logs(self, ws_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with connect() as conn:
            rows = conn.execute(
                "SELECT ts, level, message, context FROM logs WHERE workspace_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (ws_id, limit),
            ).fetchall()
        return [{"ts": r["ts"], "level": r["level"], "message": r["message"],
                 "context": _loads(r["context"], {})} for r in reversed(rows)]


def _expand_binding(row: sqlite3.Row) -> dict[str, Any]:
    b = dict(row)
    for field in ("input_mapping", "output_mapping", "transformations", "rationale"):
        b[field] = _loads(b[field], [])
    return b
