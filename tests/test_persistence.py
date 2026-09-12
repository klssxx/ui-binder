"""Persistence tests: CRUD, snapshots, versioning, delete cascade."""
from __future__ import annotations

from backend.persistence.db import init_db
from backend.persistence.store import WorkspaceStore


def test_workspace_lifecycle(data_dir):
    init_db()
    store = WorkspaceStore()
    ws = store.create_workspace("alpha")
    assert store.get_workspace(ws["id"])["name"] == "alpha"
    store.rename_workspace(ws["id"], "beta", notes="n")
    assert store.get_workspace(ws["id"])["name"] == "beta"
    assert len(store.list_workspaces()) == 1
    assert store.delete_workspace(ws["id"]) is True
    assert store.get_workspace(ws["id"]) is None


def test_ui_document_versioning_and_snapshots(data_dir):
    init_db()
    store = WorkspaceStore()
    ws = store.create_workspace("v")
    store.save_ui_document(ws["id"], {"ui": {"components": [1]}})
    row = store.get_ui_document(ws["id"])
    assert row["version"] == 1
    store.save_ui_document(ws["id"], {"ui": {"components": [1, 2]}})
    assert store.get_ui_document(ws["id"])["version"] == 2

    snap = store.create_snapshot(ws["id"], "before")
    store.save_ui_document(ws["id"], {"ui": {"components": [1, 2, 3]}})
    restored = store.restore_snapshot(ws["id"], snap["id"])
    assert len(restored["json"]["ui"]["components"]) == 2
    assert store.restore_snapshot(ws["id"], "missing") is None


def test_binding_crud_roundtrip(data_dir):
    init_db()
    store = WorkspaceStore()
    ws = store.create_workspace("b")
    b = store.create_binding(ws["id"], {
        "component_id": "component_0002", "event": "onClick",
        "target_capability": "cap_route_1", "status": "CONFIRMED",
        "input_mapping": [{"source": "component_0003.value", "target": "prompt"}],
        "confidence": 0.9,
    })
    listed = store.list_bindings(ws["id"])
    assert listed[0]["binding_id"] == b["binding_id"]
    assert listed[0]["input_mapping"][0]["target"] == "prompt"

    updated = store.update_binding(ws["id"], b["binding_id"], {"status": "BROKEN"})
    assert updated["status"] == "BROKEN"
    assert store.delete_binding(ws["id"], b["binding_id"]) is True
    assert store.list_bindings(ws["id"]) == []


def test_migrations_idempotent(data_dir):
    init_db()
    init_db()  # second call must be a no-op
    from backend.persistence.db import connect
    with connect() as conn:
        versions = [r["version"] for r in conn.execute("SELECT version FROM schema_migrations")]
    assert versions == [1]
