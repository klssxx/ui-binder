"""SQLite access + versioned migrations.

Short-lived connections per operation (local DB, low latency), WAL mode for
concurrent reads while the API writes.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from backend import config

_MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS images (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'reference',
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL,
            format TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ui_documents (
            workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
            json TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS snapshots (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            label TEXT NOT NULL,
            json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            path TEXT NOT NULL,
            read_only INTEGER NOT NULL DEFAULT 1,
            frameworks TEXT NOT NULL DEFAULT '[]',
            languages TEXT NOT NULL DEFAULT '[]',
            entrypoints TEXT NOT NULL DEFAULT '[]',
            manifests TEXT NOT NULL DEFAULT '[]',
            summary TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS project_files (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            rel_path TEXT NOT NULL,
            language TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'source',
            analysis TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS capabilities (
            capability_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            qualified_name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            inputs TEXT NOT NULL DEFAULT '[]',
            outputs TEXT NOT NULL DEFAULT '[]',
            side_effects TEXT NOT NULL DEFAULT '[]',
            origin_file TEXT NOT NULL DEFAULT '',
            origin_line INTEGER NOT NULL DEFAULT 0,
            framework TEXT NOT NULL DEFAULT 'unknown',
            http_method TEXT NOT NULL DEFAULT '',
            http_path TEXT NOT NULL DEFAULT '',
            dependencies TEXT NOT NULL DEFAULT '[]',
            legacy INTEGER NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0.5
        );
        CREATE TABLE IF NOT EXISTS bindings (
            binding_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            component_id TEXT NOT NULL,
            event TEXT NOT NULL,
            target_capability TEXT NOT NULL,
            input_mapping TEXT NOT NULL DEFAULT '[]',
            output_mapping TEXT NOT NULL DEFAULT '[]',
            loading_mapping TEXT NOT NULL DEFAULT '',
            error_mapping TEXT NOT NULL DEFAULT '',
            transformations TEXT NOT NULL DEFAULT '[]',
            confidence REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'SUGGESTED',
            rationale TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS verification_runs (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            report TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS visual_diffs (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            reference_image TEXT NOT NULL DEFAULT '',
            rendered_image TEXT NOT NULL DEFAULT '',
            metrics TEXT NOT NULL,
            fidelity REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS trace_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            ts TEXT NOT NULL,
            event TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL DEFAULT '',
            ts TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            context TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_capabilities_ws ON capabilities(workspace_id);
        CREATE INDEX IF NOT EXISTS idx_bindings_ws ON bindings(workspace_id);
        CREATE INDEX IF NOT EXISTS idx_files_project ON project_files(project_id);
        CREATE INDEX IF NOT EXISTS idx_logs_ws ON logs(workspace_id);
        """,
    ),
]

_init_lock = threading.Lock()
_initialized = False


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    conn = sqlite3.connect(config.db_path(), timeout=30)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply pending migrations in order. Returns number applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    count = 0
    for version, sql in _MIGRATIONS:
        if version in applied:
            continue
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, utcnow()),
        )
        count += 1
    return count


def init_db() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        with connect() as conn:
            apply_migrations(conn)
        _initialized = True
