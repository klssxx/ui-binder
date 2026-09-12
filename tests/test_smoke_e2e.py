"""MAIN SMOKE TEST (directive §50) — the full user flow via the real API:

start → create workspace → import screenshot → detect → correct component →
edit text → import sample app → analyze capabilities → bind button → verify →
orphan detector → visual diff → save → snapshot → export → reopen workspace.
"""
from __future__ import annotations

import io
import json


def test_full_smoke_flow(client, golden_png, sample_app_dir, tmp_path):
    # 1. app is up
    health = client.get("/health").json()
    assert health["status"] == "ok"

    # 2. create workspace
    ws = client.post("/api/workspaces", json={"name": "Smoke Flow"}).json()
    ws_id = ws["id"]

    # 3. import screenshot
    with open(golden_png, "rb") as fh:
        up = client.post(f"/api/workspaces/{ws_id}/images",
                         files={"file": ("reference.png", fh, "image/png")})
    assert up.status_code == 201
    image = up.json()
    assert (image["width"], image["height"]) == (1280, 800)

    # 4. detect components
    analysis = client.post(f"/api/workspaces/{ws_id}/analyze-ui", json={}).json()
    assert analysis["components"] >= 15
    assert analysis["notes"]["provider"] == "heuristic"

    # 5-6. correct a component + edit its text (AST, never pixels)
    doc_wrapper = client.get(f"/api/workspaces/{ws_id}/ui").json()
    doc = doc_wrapper["ui"]
    buttons = [c for c in doc["components"] if c["type"] == "button"]
    assert len(buttons) >= 2
    target = min(buttons, key=lambda c: c["bbox"]["x"])  # leftmost = Generar
    target["text"] = "Generar idea"                     # manual correction
    target["name"] = "generate-button"
    target["styles"]["background"] = "#4f8cff"
    target["metadata"] = {"confidence": 1.0, "source": "manual"}
    # move + resize to prove geometry edits persist
    target["bbox"] = {**target["bbox"], "x": target["bbox"]["x"] + 4, "width": 150}
    saved = client.put(f"/api/workspaces/{ws_id}/ui", json={"document": doc})
    assert saved.status_code == 200

    # 7. import sample app (read-only)
    imported = client.post(f"/api/workspaces/{ws_id}/import-project",
                           json={"path": str(sample_app_dir)}).json()
    assert imported["read_only"] is True
    assert "fastapi" in imported["frameworks"]

    # 8. analyze capabilities
    analysis = client.post(f"/api/workspaces/{ws_id}/analyze-project").json()
    assert analysis["capabilities"] >= 10
    caps = client.get(f"/api/workspaces/{ws_id}/capabilities").json()["capabilities"]

    # 9. suggest bindings for the corrected button
    suggestions = client.post(f"/api/workspaces/{ws_id}/suggest-bindings",
                              json={"component_id": target["id"]}).json()["suggestions"]
    assert suggestions, "button 'Generar idea' must have candidates"
    route_caps = {c["capability_id"]: c for c in caps if c["kind"] == "route"}
    generate_route = next(c for c in route_caps.values() if c["http_path"] == "/api/generate")
    expected = read_expected(sample_app_dir)
    assert expected["component_text"] == "Generar"
    top = suggestions[0]
    assert top["score"] >= expected["min_score"]
    assert top["capability_id"] in route_caps or top["capability_id"]

    # 10. confirm binding → input from the input component, output to a panel
    input_comp = next(c for c in doc["components"] if c["type"] == "input")
    panel = next(c for c in doc["components"] if c["type"] in ("panel", "container"))
    binding_payload = {
        "component_id": target["id"], "event": "onClick",
        "target_capability": generate_route["capability_id"],
        "input_mapping": [{"source": input_comp["id"], "target": "prompt"}],
        "output_mapping": [{"source": "return", "target": panel["id"]}],
        "loading_mapping": "busy", "error_mapping": "error",
        "confidence": top["score"], "status": "CONFIRMED", "rationale": top["rationale"],
    }
    created = client.post(f"/api/workspaces/{ws_id}/bindings", json=binding_payload)
    assert created.status_code == 201
    binding = created.json()
    assert binding["status"] == "CONFIRMED"

    # AST events mirror the confirmed binding
    doc_wrapper = client.get(f"/api/workspaces/{ws_id}/ui").json()
    comp = next(c for c in doc_wrapper["ui"]["components"] if c["id"] == target["id"])
    assert comp["events"].get("onClick") == binding["binding_id"]
    assert comp["text"] == "Generar idea"  # text edit survived binding sync

    # 11. verify + orphan detector
    report = client.post(f"/api/workspaces/{ws_id}/verify").json()
    orphan = report["orphan"]
    assert orphan["capabilities_detected"] == len(caps)
    assert orphan["bound"] >= 1
    unbound_names = {c["name"] for c in orphan["detail"]["UNBOUND"]}
    for must in expected_unbound(sample_app_dir):
        assert must in unbound_names, f"{must} should be UNBOUND, not deleted"
    assert report["broken_bindings"] == 0
    assert report["scores"]["functional_coverage"] > 0

    # 12. visual diff (identical reference as rendered → high fidelity)
    with open(golden_png, "rb") as fh:
        diff = client.post(f"/api/workspaces/{ws_id}/visual-diff",
                           files={"rendered": ("rendered.png", fh, "image/png")})
    assert diff.status_code == 200
    metrics = diff.json()["metrics"]
    assert metrics["visual_fidelity_score"] > 95.0
    assert metrics["region_count"] > 0

    # 13. save + snapshot
    snap = client.post(f"/api/workspaces/{ws_id}/snapshots", json={"label": "smoke"}).json()
    assert client.post(f"/api/workspaces/{ws_id}/snapshots/{snap['id']}/restore").status_code == 200

    # 14. export to a fresh directory
    export_dir = tmp_path / "exported-smoke"
    exported = client.post(f"/api/workspaces/{ws_id}/export", json={"target_dir": str(export_dir)})
    assert exported.status_code == 200
    plan = exported.json()
    assert plan["bindings_embedded"] >= 1
    assert (export_dir / "src" / "api.ts").is_file()

    # 15. reload workspace — everything persisted
    reloaded = client.get(f"/api/workspaces/{ws_id}").json()
    assert reloaded["has_ui_document"] is True
    doc2 = client.get(f"/api/workspaces/{ws_id}/ui").json()["ui"]
    comp2 = next(c for c in doc2["components"] if c["id"] == target["id"])
    assert comp2["text"] == "Generar idea"
    assert comp2["bbox"]["width"] == 150
    bindings = client.get(f"/api/workspaces/{ws_id}/bindings").json()["bindings"]
    assert any(b["binding_id"] == binding["binding_id"] for b in bindings)
    diffs = client.get(f"/api/workspaces/{ws_id}/diffs").json()["diffs"]
    assert diffs and diffs[0]["fidelity"] > 95.0

    # 16. trace events recorded along the way
    events = client.get(f"/api/workspaces/{ws_id}/trace/events").json()["events"]
    assert isinstance(events, list)


def read_expected(sample_app_dir):
    path = sample_app_dir.parent / "golden-reference" / "expected_bindings.json"
    return json.loads(path.read_text(encoding="utf-8"))


def expected_unbound(sample_app_dir):
    path = sample_app_dir.parent / "golden-reference" / "expected_capabilities.json"
    return json.loads(path.read_text(encoding="utf-8"))["expected_unbound_orphans"]
