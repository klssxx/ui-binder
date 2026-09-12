"""API contract tests: happy paths + honest error paths."""
from __future__ import annotations

import io


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"]["state"] == "ok"
    assert "heuristic" in body["vision_provider"]["available"]


def test_workspace_crud_and_404(client):
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    assert client.get(f"/api/workspaces/{ws['id']}").status_code == 200
    assert client.get("/api/workspaces/ws_missing").status_code == 404
    assert client.patch(f"/api/workspaces/{ws['id']}", json={"name": "t2"}).json()["name"] == "t2"
    assert client.delete(f"/api/workspaces/{ws['id']}").status_code == 204
    assert client.delete(f"/api/workspaces/{ws['id']}").status_code == 404


def test_ui_requires_analysis_first(client):
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    assert client.get(f"/api/workspaces/{ws['id']}/ui").status_code == 409
    assert client.post(f"/api/workspaces/{ws['id']}/analyze-ui", json={}).status_code == 409


def test_upload_rejects_invalid_image(client):
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    r = client.post(f"/api/workspaces/{ws['id']}/images",
                    files={"file": ("x.png", io.BytesIO(b"not an image"), "image/png")})
    assert r.status_code == 422


def test_import_project_validates_path(client, sample_app_dir):
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    assert client.post(f"/api/workspaces/{ws['id']}/import-project",
                       json={"path": "Z:/does/not/exist"}).status_code == 422
    assert client.post(f"/api/workspaces/{ws['id']}/import-project",
                       json={"path": "C:\\Windows"}).status_code == 422
    r = client.post(f"/api/workspaces/{ws['id']}/import-project",
                    json={"path": str(sample_app_dir)})
    assert r.status_code == 200
    body = r.json()
    assert body["read_only"] is True
    assert "fastapi" in body["frameworks"]
    assert client.post(f"/api/workspaces/{ws['id']}/analyze-project").status_code == 200


def test_analyze_project_without_import_409(client):
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    assert client.post(f"/api/workspaces/{ws['id']}/analyze-project").status_code == 409


def test_binding_validation(client, sample_app_dir):
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    r = client.post(f"/api/workspaces/{ws['id']}/bindings", json={
        "component_id": "component_0001", "target_capability": "ghost"})
    assert r.status_code == 422

    client.post(f"/api/workspaces/{ws['id']}/import-project", json={"path": str(sample_app_dir)})
    assert client.post(f"/api/workspaces/{ws['id']}/analyze-project").status_code == 200
    caps = client.get(f"/api/workspaces/{ws['id']}/capabilities").json()["capabilities"]
    assert caps
    r = client.post(f"/api/workspaces/{ws['id']}/bindings", json={
        "component_id": "component_9999",
        "target_capability": caps[0]["capability_id"]})
    # no UI document in this workspace → component check impossible → 409 is honest
    assert r.status_code == 409


def test_duplicate_binding_rejected_409(client, sample_app_dir, golden_png):
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    with open(golden_png, "rb") as fh:
        client.post(f"/api/workspaces/{ws['id']}/images",
                    files={"file": ("reference.png", fh, "image/png")})
    client.post(f"/api/workspaces/{ws['id']}/analyze-ui", json={})
    doc = client.get(f"/api/workspaces/{ws['id']}/ui").json()["ui"]
    button = next(c for c in doc["components"] if c["type"] == "button")

    client.post(f"/api/workspaces/{ws['id']}/import-project", json={"path": str(sample_app_dir)})
    client.post(f"/api/workspaces/{ws['id']}/analyze-project")
    caps = client.get(f"/api/workspaces/{ws['id']}/capabilities").json()["capabilities"]
    route = next(c for c in caps if c["kind"] == "route")

    payload = {"component_id": button["id"], "target_capability": route["capability_id"],
               "status": "CONFIRMED"}
    assert client.post(f"/api/workspaces/{ws['id']}/bindings", json=payload).status_code == 201
    r = client.post(f"/api/workspaces/{ws['id']}/bindings", json=payload)
    assert r.status_code == 409


def test_search_groups(client, sample_app_dir, golden_png):
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    with open(golden_png, "rb") as fh:
        client.post(f"/api/workspaces/{ws['id']}/images",
                    files={"file": ("reference.png", fh, "image/png")})
    client.post(f"/api/workspaces/{ws['id']}/analyze-ui", json={})
    client.post(f"/api/workspaces/{ws['id']}/import-project", json={"path": str(sample_app_dir)})
    client.post(f"/api/workspaces/{ws['id']}/analyze-project")
    r = client.get(f"/api/workspaces/{ws['id']}/search?q=generate").json()
    assert r["capabilities"], "capabilities must match 'generate'"
    assert r["routes"], "POST /api/generate must appear as route"
    assert r["files"], "App.tsx must appear in files"


def test_trace_and_logs_roundtrip(client):
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    client.post(f"/api/workspaces/{ws['id']}/trace/events",
                json={"event": "preview-click", "component": "component_0002"})
    events = client.get(f"/api/workspaces/{ws['id']}/trace/events").json()["events"]
    assert events and events[-1]["event"] == "preview-click"
    logs = client.get(f"/api/workspaces/{ws['id']}/logs").json()["logs"]
    assert any(l["message"] == "workspace created" for l in logs)


def test_logs_redact_secrets(data_dir, client):
    from backend.logging_setup import log
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    log(ws["id"], "INFO", "testing redaction", api_key="sk-12345678abcdefgh", password="hunter2")
    logs = client.get(f"/api/workspaces/{ws['id']}/logs").json()["logs"]
    entry = next(l for l in logs if "redaction" in l["message"])
    assert entry["context"]["api_key"] == "[REDACTED]"
    assert entry["context"]["password"] == "[REDACTED]"


def test_export_requires_empty_target(client, sample_app_dir, golden_png, tmp_path):
    ws = client.post("/api/workspaces", json={"name": "t"}).json()
    with open(golden_png, "rb") as fh:
        client.post(f"/api/workspaces/{ws['id']}/images",
                    files={"file": ("reference.png", fh, "image/png")})
    client.post(f"/api/workspaces/{ws['id']}/analyze-ui", json={})
    occupied = tmp_path / "occ"
    occupied.mkdir()
    (occupied / "x").write_text("x", encoding="utf-8")
    r = client.post(f"/api/workspaces/{ws['id']}/export", json={"target_dir": str(occupied)})
    assert r.status_code == 422
    plan = client.get(f"/api/workspaces/{ws['id']}/export-plan").json()
    assert plan["files_created"]


def test_spec_suggest_by_description(client, sample_app_dir):
    ws = client.post("/api/workspaces", json={"name": "spec"}).json()
    client.post(f"/api/workspaces/{ws['id']}/import-project", json={"path": str(sample_app_dir)})
    client.post(f"/api/workspaces/{ws['id']}/analyze-project")
    r = client.post(f"/api/workspaces/{ws['id']}/spec/suggest", json={
        "name": "Generar idea", "description": "genera una idea a partir del prompt",
        "type": "button"})
    assert r.status_code == 200
    sugs = r.json()["suggestions"]
    assert sugs, "la descripción en castellano debe encontrar la ruta /api/generate"
    routes = client.get(f"/api/workspaces/{ws['id']}/capabilities").json()["capabilities"]
    generate_routes = {c["capability_id"] for c in routes
                       if c["http_path"] == "/api/generate"}
    assert any(s["capability_id"] in generate_routes for s in sugs[:3]), \
        "la ruta de generación debe estar entre las mejores sugerencias"
    # sin proyecto analizado → 409 honesto
    ws2 = client.post("/api/workspaces", json={"name": "spec2"}).json()
    assert client.post(f"/api/workspaces/{ws2['id']}/spec/suggest",
                       json={"name": "x"}).status_code == 409


def test_fonts_endpoint(client):
    r = client.get("/api/fonts")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 10
    families = {f["family"] for f in body["fonts"]}
    assert "system-ui" in families
    # la segunda llamada usa la caché del proceso
    r2 = client.get("/api/fonts")
    assert r2.json()["cached"] is True
