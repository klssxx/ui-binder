"""UI AST — canonical, versioned intermediate representation (ui-schema v1).

Everything persistent flows through these models; nothing depends on
unversioned internal classes. See docs/UI_SCHEMA.md.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

UI_SCHEMA_VERSION = 1

COMPONENT_TYPES: tuple[str, ...] = (
    "screen", "container", "panel", "card", "text", "heading", "button",
    "input", "textarea", "select", "checkbox", "radio", "image", "icon",
    "table", "chart", "tabs", "sidebar", "navbar", "modal", "divider", "custom",
)
ComponentType = Literal[
    "screen", "container", "panel", "card", "text", "heading", "button",
    "input", "textarea", "select", "checkbox", "radio", "image", "icon",
    "table", "chart", "tabs", "sidebar", "navbar", "modal", "divider", "custom",
]

SCREEN_ID = "screen"


class BBox(BaseModel):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)

    def area(self) -> float:
        return self.width * self.height


class Component(BaseModel):
    id: str
    type: ComponentType = "container"
    name: str = ""
    parent_id: Optional[str] = None
    children: list[str] = Field(default_factory=list)
    bbox: BBox
    text: Optional[str] = None
    styles: dict[str, Any] = Field(default_factory=dict)
    states: dict[str, Any] = Field(default_factory=dict)
    events: dict[str, Any] = Field(default_factory=dict)
    bindings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", mode="before")
    @classmethod
    def _default_name(cls, v: Any) -> Any:
        return v if v else ""

    def area(self) -> float:
        return self.bbox.width * self.bbox.height

    def contains(self, other: "Component") -> bool:
        a, b = self.bbox, other.bbox
        return (
            a.x <= b.x and a.y <= b.y
            and a.x + a.width >= b.x + b.width
            and a.y + a.height >= b.y + b.height
        )


class Screen(BaseModel):
    id: str = SCREEN_ID
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    background: Optional[str] = None
    preset: Optional[str] = None  # responsive preset used for the canvas


class Stroke(BaseModel):
    """Trazo de la capa de dibujo (F5). Vive en el documento versionado."""
    id: str
    tool: Literal["pencil", "rect", "ellipse", "line", "arrow"] = "pencil"
    color: str = "#4f8cff"
    width: float = 4
    opacity: float = 1.0
    points: list[dict[str, float]] = Field(default_factory=list)  # pencil: N; formas: 2


class UIDocument(BaseModel):
    ui_schema_version: int = UI_SCHEMA_VERSION
    screen: Screen
    components: list[Component] = Field(default_factory=list)
    strokes: list[Stroke] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def by_id(self) -> dict[str, Component]:
        return {c.id: c for c in self.components}

    def children_of(self, parent_id: Optional[str]) -> list[Component]:
        return [c for c in self.components if c.parent_id == parent_id]

    def validate_structure(self) -> list[str]:
        """Structural invariants. Returns list of human-readable problems."""
        problems: list[str] = []
        ids = [c.id for c in self.components]
        if len(ids) != len(set(ids)):
            problems.append("Duplicate component ids.")
        id_set = set(ids)
        for c in self.components:
            if c.id == SCREEN_ID:
                problems.append(f"Component uses reserved id '{SCREEN_ID}'.")
            if c.parent_id is not None and c.parent_id not in id_set and c.parent_id != SCREEN_ID:
                problems.append(f"{c.id}: unknown parent '{c.parent_id}'.")
            if c.parent_id == c.id:
                problems.append(f"{c.id}: parent of itself.")
            for child in c.children:
                if child not in id_set:
                    problems.append(f"{c.id}: unknown child '{child}'.")
        for c in self.components:
            if c.parent_id is not None:
                parent = self.by_id().get(c.parent_id)
                if parent is not None and c.id not in parent.children:
                    problems.append(f"{c.id}: not listed in parent's children (order lost).")
        return problems


def empty_document(width: float = 1280, height: float = 800, preset: str | None = None) -> UIDocument:
    return UIDocument(screen=Screen(width=width, height=height, preset=preset))
