"""Tests for vision provider contract and validation."""
from __future__ import annotations

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["UIBINDER_VISION_BASE_URL"] = ""
os.environ["UIBINDER_VISION_MODEL"] = ""
os.environ["UIBINDER_VISION_API_KEY"] = ""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_vision_provider_registry():
    """Provider registry should list available providers."""
    from backend.vision.provider import list_providers
    providers = list_providers()
    assert "heuristic" in providers


def test_vision_provider_get_local():
    """Getting heuristic provider should work."""
    from backend.vision.provider import get_provider
    p = get_provider("heuristic")
    assert p.name == "heuristic"


def test_vision_provider_get_unknown_falls_back():
    """Unknown provider should fall back to heuristic."""
    from backend.vision.provider import get_provider
    p = get_provider("nonexistent_xyz")
    assert p.name == "heuristic"


def test_vision_provider_remote_requires_config():
    """Remote provider should raise if not configured."""
    from backend.vision.remote import OpenAICompatibleVisionProvider
    with pytest.raises(RuntimeError):
        OpenAICompatibleVisionProvider(
            base_url="", model="", api_key=""
        )


def test_vision_provider_remote_with_config():
    """Remote provider should init with config."""
    from backend.vision.remote import OpenAICompatibleVisionProvider
    p = OpenAICompatibleVisionProvider(
        base_url="https://api.example.com/v1",
        model="test-model",
        api_key="test-key-123"
    )
    assert p.base_url == "https://api.example.com/v1"
    assert p.model == "test-model"


def test_vision_result_contract():
    """VisionResult should serialize properly."""
    from backend.vision.contract import VisionResult, VisionUsage, VisionProvenance, DetectedComponent
    
    dc = DetectedComponent(
        type="button",
        bbox={"x": 10, "y": 20, "width": 100, "height": 40},
        text="Click me",
        confidence=0.95,
        role="primary",
        styles={"background": "#4f8cff", "color": "#ffffff"},
    )
    
    usage = VisionUsage(
        provider="remote", model="test", latency_ms=150.0,
        input_tokens=100, output_tokens=50, estimated_cost_usd=0.001,
        success=True, image_hash="abc123",
    )
    
    prov = VisionProvenance(
        provider="remote", model="test", mode="REMOTE",
        privacy="external", confidence_avg=0.9,
    )
    
    result = VisionResult(components=[dc], usage=usage, provenance=prov)
    assert len(result.components) == 1
    assert result.components[0].type == "button"
    assert result.usage.input_tokens == 100


def test_auto_vision_provider_fallback():
    """AutoVisionProvider should use local when confidence is high."""
    from backend.vision.auto import AutoVisionProvider
    from backend.vision.provider import get_provider
    from PIL import Image
    
    provider = AutoVisionProvider(threshold=0.6)
    # Create a test image
    img = Image.new("RGB", (100, 100), color="red")
    
    doc, notes = provider.analyze(img)
    assert "fallback_used" in notes


def test_budget_tracker():
    """Budget tracker should track spending."""
    from backend.vision.budget import VisionBudget, get_budget
    from backend.vision.contract import VisionUsage
    
    budget = VisionBudget(max_cost_usd=1.0)
    usage = VisionUsage(provider="test", model="x", estimated_cost_usd=0.5)
    
    assert budget.record(usage) is True
    assert budget.spent == 0.5
    assert budget.calls == 1
    
    usage2 = VisionUsage(provider="test", model="x", estimated_cost_usd=0.6)
    assert budget.would_exceed(0.6) is True
    assert budget.would_exceed(0.1) is False


def test_budget_limit_enforced():
    """Budget should reject when limit exceeded."""
    from backend.vision.budget import VisionBudget
    from backend.vision.contract import VisionUsage
    
    budget = VisionBudget(max_cost_usd=0.1)
    usage = VisionUsage(provider="test", model="x", estimated_cost_usd=0.2)
    
    assert budget.record(usage) is False  # Exceeds budget


def test_detected_component_to_dict_backward_compat():
    """DetectedComponent.to_dict() should omit None/0.5 defaults."""
    from backend.vision.contract import DetectedComponent
    
    dc = DetectedComponent(type="button", bbox={"x": 0, "y": 0, "width": 10, "height": 10})
    d = dc.to_dict()
    assert "type" in d
    assert "bbox" in d
    assert "text" not in d  # None omitted
    assert "confidence" not in d  # 0.5 default omitted
    
    dc2 = DetectedComponent(
        type="button", bbox={"x": 0, "y": 0, "width": 10, "height": 10},
        text="Hi", confidence=0.9, role="primary"
    )
    d2 = dc2.to_dict()
    assert d2["text"] == "Hi"
    assert d2["confidence"] == 0.9
    assert d2["role"] == "primary"


def test_vision_provider_auto_provider():
    """Auto provider should be retrievable."""
    from backend.vision.provider import get_provider
    p = get_provider("auto")
    assert p.name == "auto"


def test_vision_provider_mistral_alias():
    """Mistral provider should use OpenAI-compatible interface."""
    from backend.vision.remote import OpenAICompatibleVisionProvider
    # Mistral uses same interface, just different config
    p = OpenAICompatibleVisionProvider(
        base_url="https://api.mistral.ai/v1",
        model="pixtral-latest",
        api_key="test-mistral-key"
    )
    assert p.base_url == "https://api.mistral.ai/v1"
    assert p.model == "pixtral-latest"
