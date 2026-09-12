"""Remote vision provider: JSON contract via stubbed transport + config guard."""
from __future__ import annotations

import json
from typing import Any

from PIL import Image

from backend.vision.remote import OpenAICompatibleVisionProvider


class _StubResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _StubClient:
    calls: list[dict] = []

    def __init__(self, *a: Any, **kw: Any):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a: Any):
        return False

    def post(self, url: str, json: dict = None, data: dict = None, headers: dict = None):  # noqa: A002
        import json as jsonlib
        _StubClient.calls.append({"url": url, "json": json, "headers": headers})
        content = jsonlib.dumps({
            "components": [
                {"type": "button", "bbox": {"x": 10, "y": 20, "width": 100, "height": 40},
                 "text": "Generar", "confidence": 0.9},
                {"type": "heading", "bbox": {"x": 10, "y": 5, "width": 300, "height": 32},
                 "text": "Panel", "confidence": 0.8},
                {"type": "nonsense", "bbox": {"x": 0, "y": 0, "width": 10, "height": 10},
                 "confidence": 0.5},
            ]
        })
        return _StubResponse({"choices": [{"message": {"content": f"```json\n{content}\n```"}}]})


def test_unconfigured_provider_raises(monkeypatch):
    monkeypatch.delenv("UIBINDER_VISION_BASE_URL", raising=False)
    monkeypatch.delenv("UIBINDER_VISION_API_KEY", raising=False)
    monkeypatch.delenv("UIBINDER_VISION_MODEL", raising=False)
    try:
        OpenAICompatibleVisionProvider()
        raise AssertionError("should require configuration")
    except RuntimeError as e:
        assert "not configured" in str(e)


def test_remote_provider_parses_and_classifies(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "Client", _StubClient)
    provider = OpenAICompatibleVisionProvider(
        base_url="https://example.internal/v1", model="stub-vision", api_key="sk-test")
    img = Image.new("RGB", (600, 400), "#101216")
    doc, notes = provider.analyze(img)

    assert notes["provider"] == "remote"
    assert notes["privacy"].startswith("image was sent")
    types = {c.type for c in doc.components}
    assert "button" in types and "heading" in types
    assert "custom" in types  # unknown type is reclasified as custom, never dropped
    assert doc.screen.width == 600
    # containment hierarchy: heading inside screen, button under screen or heading
    assert doc.validate_structure() == []
    # key never appears in the request log payload (only in headers)
    assert _StubClient.calls[0]["json"]["model"] == "stub-vision"
    assert "sk-test" not in json.dumps(_StubClient.calls[0]["json"])


def test_remote_provider_never_stores_key(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "Client", _StubClient)
    provider = OpenAICompatibleVisionProvider(
        base_url="https://example.internal/v1", model="m", api_key="sk-secret")
    dumped = provider.__dict__
    assert dumped["_api_key"] == "sk-secret"  # memory only, never persisted
    img = Image.new("RGB", (60, 40), "#000")
    _, notes = provider.analyze(img)
    assert "sk-secret" not in json.dumps(notes)
