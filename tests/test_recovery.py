"""Corruption recovery (QA adversarial finding): corrupt persisted JSON must
surface an actionable 422 — never an empty 500 — and a valid PUT must heal it."""
from __future__ import annotations

import sqlite3

from backend.persistence.db import init_db, connect


def _corrupt_ui_document(data_dir) -> None:
    with connect() as conn:
        conn.execute("UPDATE ui_documents SET json = '{invalid'")


def test_corrupt_document_returns_actionable_422_and_put_heals(client, golden_png):
    ws = client.post("/api/workspaces", json={"name": "corrupt"}).json()
    with open(golden_png, "rb") as fh:
        client.post(f"/api/workspaces/{ws['id']}/images",
                    files={"file": ("reference.png", fh, "image/png")})
    assert client.post(f"/api/workspaces/{ws['id']}/analyze-ui", json={}).status_code == 200

    init_db()  # ensure db exists in this env
    _corrupt_ui_document(client)

    r = client.get(f"/api/workspaces/{ws['id']}/ui")
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["message"] and detail["cause"] and detail["action"]
    assert "snapshot" in detail["action"] and "PUT /ui" in detail["action"]

    # related endpoints degrade honestly, process stays alive
    assert client.get("/health").status_code == 200
    assert client.post(f"/api/workspaces/{ws['id']}/suggest-bindings",
                       json={"component_id": "x"}).status_code == 422
    assert client.post(f"/api/workspaces/{ws['id']}/verify").status_code == 422
    assert client.post(f"/api/workspaces/{ws['id']}/export",
                       json={"target_dir": "C:/nope"}).status_code in (422, 409)
    assert client.post(f"/api/workspaces/{ws['id']}/snapshots",
                       json={"label": "x"}).status_code == 422

    # a fresh valid PUT heals the workspace
    doc = {
        "ui_schema_version": 1,
        "screen": {"id": "screen", "width": 320, "height": 240},
        "components": [{
            "id": "component_0001", "type": "button", "name": "healed",
            "parent_id": "screen", "children": [],
            "bbox": {"x": 8, "y": 8, "width": 90, "height": 32},
            "text": "Curado", "styles": {}, "states": {}, "events": {},
            "bindings": [], "metadata": {},
        }],
    }
    r = client.put(f"/api/workspaces/{ws['id']}/ui", json={"document": doc})
    assert r.status_code == 200
    healed = client.get(f"/api/workspaces/{ws['id']}/ui").json()
    assert healed["ui"]["components"][0]["text"] == "Curado"
    assert client.post(f"/api/workspaces/{ws['id']}/verify").status_code == 200
