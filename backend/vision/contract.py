"""Rich vision contract — backward-compatible visual detection result.

Extends the basic type/bbox/text/confidence model with:
- role, parent_hint, group_hint
- styles (background, color, border, radius, font_*, opacity, alignment)
- state hints (enabled, selected, checked)
- visual semantics

All new fields are OPTIONAL for backward compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DetectedComponent:
    """A single UI element detected by a vision provider."""
    type: str
    bbox: dict[str, float]  # {x, y, width, height}
    text: Optional[str] = None
    confidence: float = 0.5
    
    # Rich visual contract (optional, backward-compatible)
    role: Optional[str] = None
    parent_hint: Optional[str] = None
    group_hint: Optional[str] = None
    styles: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    visual_semantic: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        d = {
            "type": self.type,
            "bbox": self.bbox,
        }
        if self.text is not None:
            d["text"] = self.text
        if self.confidence != 0.5:
            d["confidence"] = self.confidence
        if self.role:
            d["role"] = self.role
        if self.parent_hint:
            d["parent_hint"] = self.parent_hint
        if self.group_hint:
            d["group_hint"] = self.group_hint
        if self.styles:
            d["styles"] = self.styles
        if self.state:
            d["state"] = self.state
        if self.visual_semantic:
            d["visual_semantic"] = self.visual_semantic
        return d


@dataclass
class VisionUsage:
    """Cost/usage tracking for a single vision call."""
    provider: str
    model: str
    latency_ms: float = 0.0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: float = 0.0
    success: bool = True
    fallback: bool = False
    image_hash: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class VisionProvenance:
    """Traceability for a vision analysis."""
    provider: str
    model: str
    mode: str  # LOCAL, REMOTE, AUTO
    privacy: str
    cost: float = 0.0
    confidence_avg: float = 0.0
    fallback_used: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class VisionResult:
    """Complete result from a vision provider."""
    components: list[DetectedComponent]
    usage: VisionUsage
    provenance: VisionProvenance
    raw_response: Optional[dict[str, Any]] = None
