"""Design tokens extracted from the reference screenshot + AST."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ColorToken(BaseModel):
    name: str
    hex: str
    usage: str = "unknown"
    confidence: float = 0.5


class FontToken(BaseModel):
    family: str = "system-ui"
    size_px: float
    weight: int = 400
    role: str = "body"  # body | heading | caption
    confidence: float = 0.5


class RadiusToken(BaseModel):
    name: str
    px: float
    confidence: float = 0.3


class SpacingToken(BaseModel):
    name: str
    px: float
    confidence: float = 0.4


class DesignTokens(BaseModel):
    colors: list[ColorToken] = Field(default_factory=list)
    fonts: list[FontToken] = Field(default_factory=list)
    radii: list[RadiusToken] = Field(default_factory=list)
    spacing: list[SpacingToken] = Field(default_factory=list)
    grid: dict[str, Any] = Field(default_factory=dict)
    breakpoints: dict[str, int] = Field(
        default_factory=lambda: {"mobile": 640, "tablet": 1024, "desktop": 1440}
    )
    raw: dict[str, Any] = Field(default_factory=dict)

    def to_css_variables(self) -> dict[str, str]:
        """Flatten tokens to CSS custom properties for the exporter."""
        out: dict[str, str] = {}
        for c in self.colors:
            key = "--color-" + c.name.replace(" ", "-").lower()
            out[key] = c.hex
        for f in self.fonts:
            suffix = "" if f.role == "body" else "-" + f.role
            out[f"--font-size{suffix}"] = f"{f.size_px:.0f}px"
        for r in self.radii:
            out["--radius-" + r.name] = f"{r.px:.0f}px"
        for s in self.spacing:
            out["--space-" + s.name] = f"{s.px:.0f}px"
        return out
