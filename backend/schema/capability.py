"""Capability model — what an imported project can DO, independent of files."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

CapabilityKind = Literal[
    "function", "method", "class", "route", "component", "hook",
    "handler", "store", "service",
]


class Param(BaseModel):
    name: str
    type: str = "unknown"
    required: bool = True
    description: str = ""


class Capability(BaseModel):
    capability_id: str
    kind: CapabilityKind
    name: str
    qualified_name: str
    description: str = ""
    inputs: list[Param] = Field(default_factory=list)
    outputs: list[Param] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    origin_file: str = ""
    origin_line: int = 0
    framework: str = "unknown"
    http_method: str = ""
    http_path: str = ""
    dependencies: list[str] = Field(default_factory=list)  # capability_ids
    legacy: bool = False
    confidence: float = 0.5
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityEdge(BaseModel):
    source: str  # capability_id
    target: str  # capability_id
    relation: str  # calls | handles | fetches | renders | returns_to


class CapabilityGraph(BaseModel):
    nodes: list[Capability] = Field(default_factory=list)
    edges: list[CapabilityEdge] = Field(default_factory=list)


def confidence_band(value: float, source: str = "") -> str:
    """FACT is reserved for user-asserted facts (manual edits/confirmations)."""
    if source == "manual":
        return "FACT"
    if value >= 0.85:
        return "HIGH CONFIDENCE"
    if value >= 0.5:
        return "MEDIUM CONFIDENCE"
    if value > 0.0:
        return "LOW CONFIDENCE"
    return "UNKNOWN"
