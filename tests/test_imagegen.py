"""F6: estado de IA + fondos locales + export con assets de imagen."""
from __future__ import annotations

import numpy as np
from PIL import Image


def test_imagegen_status_unconfigured(client, monkeypatch):
    monkeypatch.delenv("UIBINDER_IMAGEGEN_BASE_URL", raising=False)
    monkeypatch.delenv("UIBINDER_IMAGEGEN_API_KEY", raising=False)
    r = client.get("/api/imagegen/status")
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False
    assert "no envía nada" in body["privacy"] or "no envían" in body["privacy"]


def test_hero_requires_configuration_409(client, monkeypatch):
    monkeypatch.delenv("UIBINDER_IMAGEGEN_BASE_URL", raising=False)
    monkeypatch.delenv("UIBINDER_IMAGEGEN_API_KEY", raising=False)
    ws = client.post("/api/workspaces", json={"name": "ia"}).json()
    r = client.post(f"/api/workspaces/{ws['id']}/imagegen/hero", json={"prompt": "héroe"})
    assert r.status_code == 409
    assert "no está configurada" in r.json()["detail"]


def test_hero_rejects_empty_prompt(client, monkeypatch):
    monkeypatch.setenv("UIBINDER_IMAGEGEN_BASE_URL", "https://x")
    monkeypatch.setenv("UIBINDER_IMAGEGEN_API_KEY", "k")
    monkeypatch.setenv("UIBINDER_IMAGEGEN_MODEL", "m")
    ws = client.post("/api/workspaces", json={"name": "ia2"}).json()
    r = client.post(f"/api/workspaces/{ws['id']}/imagegen/hero", json={"prompt": "  "})
    assert r.status_code == 422


def test_background_local_ops(client, golden_png):
    ws = client.post("/api/workspaces", json={"name": "bg"}).json()
    with open(golden_png, "rb") as fh:
        client.post(f"/api/workspaces/{ws['id']}/images",
                    files={"file": ("reference.png", fh, "image/png")})
    for op, params in [("blur", {"sigma": 10}), ("darken", {"factor": 0.4}),
                       ("color", {"hex": "#123456"}), ("gradient", {})]:
        r = client.post(f"/api/workspaces/{ws['id']}/background",
                        json={"op": op, "params": params})
        assert r.status_code == 200, f"{op}: {r.text[:200]}"
        rec = r.json()["image"]
        assert rec["role"] == "variant" and rec["format"] == "PNG"
        served = client.get(f"/api/images/{rec['id']}/file")
        assert served.status_code == 200

    # blur real: la imagen variante debe ser más suave que la original (menos varianza)
    orig = np.asarray(Image.open(golden_png).convert("L"), dtype=float)
    r = client.post(f"/api/workspaces/{ws['id']}/background",
                    json={"op": "blur", "params": {"sigma": 12}})
    import io
    blurred = np.asarray(Image.open(io.BytesIO(client.get(
        f"/api/images/{r.json()['image']['id']}/file").content)).convert("L"), dtype=float)
    assert blurred.std() < orig.std()

    # op desconocida → 422 claro
    assert client.post(f"/api/workspaces/{ws['id']}/background",
                       json={"op": "nonsense", "params": {}}).status_code == 422


def test_export_copies_image_assets(client, golden_png, tmp_path):
    ws = client.post("/api/workspaces", json={"name": "assets"}).json()
    with open(golden_png, "rb") as fh:
        up = client.post(f"/api/workspaces/{ws['id']}/images",
                         files={"file": ("hero.png", fh, "image/png")}).json()
    src_url = f"/api/images/{up['id']}/file"
    doc = {
        "ui_schema_version": 1,
        "screen": {"id": "screen", "width": 640, "height": 400},
        "components": [{
            "id": "component_img", "type": "image", "name": "hero", "parent_id": "screen",
            "children": [], "bbox": {"x": 0, "y": 0, "width": 640, "height": 200},
            "text": None, "styles": {"src": src_url}, "states": {}, "events": {},
            "bindings": [], "metadata": {},
        }],
    }
    assert client.put(f"/api/workspaces/{ws['id']}/ui", json={"document": doc}).status_code == 200
    target = tmp_path / "export-assets"
    r = client.post(f"/api/workspaces/{ws['id']}/export", json={"target_dir": str(target)})
    assert r.status_code == 200, r.text[:300]
    assert r.json().get("assets_copied") == 1
    app = (target / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "./assets/" in app
    files = list((target / "assets").glob("*.png"))
    assert len(files) == 1 and files[0].stat().st_size > 1000


def test_status_reports_user_env_path(client):
    r = client.get("/api/imagegen/status")
    assert r.status_code == 200
    body = r.json()
    assert "env_file" in body
    normalized = body["env_file"].replace("\\", "/")
    assert normalized.endswith("UIBinder/.env")


def test_user_env_file_loaded(tmp_path, monkeypatch):
    import importlib
    import backend.config as config_module
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    env = tmp_path / "UIBinder" / ".env"
    env.parent.mkdir(parents=True)
    env.write_text("UIBINDER_IMAGEGEN_BASE_URL=https://ejemplo/v1\n"
                   "UIBINDER_IMAGEGEN_MODEL=cogview-4\n"
                   "UIBINDER_IMAGEGEN_API_KEY=clave-test\n", encoding="utf-8")
    monkeypatch.delenv("UIBINDER_IMAGEGEN_BASE_URL", raising=False)
    monkeypatch.delenv("UIBINDER_IMAGEGEN_MODEL", raising=False)
    monkeypatch.delenv("UIBINDER_IMAGEGEN_API_KEY", raising=False)
    importlib.reload(config_module)
    assert config_module.IMAGEGEN_BASE_URL == "https://ejemplo/v1"
    assert config_module.IMAGEGEN_MODEL == "cogview-4"
    assert config_module.IMAGEGEN_API_KEY == "clave-test"
    # restaurar módulo para el resto de la suite
    monkeypatch.delenv("UIBINDER_IMAGEGEN_BASE_URL")
    monkeypatch.delenv("UIBINDER_IMAGEGEN_MODEL")
    monkeypatch.delenv("UIBINDER_IMAGEGEN_API_KEY")
    importlib.reload(config_module)
