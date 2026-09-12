"""Binding model — the explicit contract between UI components and capabilities."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

BindingStatus = Literal["SUGGESTED", "CONFIRMED", "BROKEN", "UNKNOWN"]


class Mapping(BaseModel):
    """A single value flow: UI property <-> capability parameter/result."""
    source: str                      # e.g. "idea_input.value" or "generate_button"
    target: str                      # e.g. "prompt" or "result_panel.data"
    transform: Optional[str] = None  # named transform, e.g. "trim", "number"
    note: Optional[str] = None


class Binding(BaseModel):
    binding_id: str
    component_id: str
    event: str = "onClick"
    target_capability: str
    input_mapping: list[Mapping] = Field(default_factory=list)
    output_mapping: list[Mapping] = Field(default_factory=list)
    loading_mapping: str = ""        # UI state key set while running
    error_mapping: str = ""          # UI state key receiving errors
    transformations: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    status: BindingStatus = "SUGGESTED"
    rationale: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BindingSuggestion(BaseModel):
    """Matcher output for a component — deterministic, auditable scoring."""
    capability_id: str
    score: float
    rationale: list[str]
    inputs: list[dict[str, Any]] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
