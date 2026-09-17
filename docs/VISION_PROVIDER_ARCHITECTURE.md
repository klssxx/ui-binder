# Vision Provider Architecture — UI Binder

## Overview

UI Binder supports multiple vision providers for UI reconstruction from screenshots:

- **LOCAL**: OpenCV + OCR heuristic (offline, default)
- **REMOTE**: OpenAI-compatible multimodal API (Mistral, OpenAI, etc.)
- **AUTO**: Local first, escalate to remote if confidence < threshold

## Provider Interface

All providers implement the `VisionProvider` ABC:

```python
class VisionProvider(ABC):
    name: str
    
    def analyze(self, image: Image.Image) -> tuple[UIDocument, dict]:
        """Basic analysis returning UI AST + notes."""
    
    def analyze_rich(self, image: Image.Image) -> VisionResult:
        """Rich analysis with full visual contract."""
```

## Rich Visual Contract

The extended result includes per-component:

| Field | Type | Description |
|-------|------|-------------|
| `type` | str | Component type (button, input, etc.) |
| `role` | str? | Semantic role (primary, danger, etc.) |
| `bbox` | dict | {x, y, width, height} |
| `text` | str? | Detected text content |
| `confidence` | float | 0.0-1.0 |
| `parent_hint` | str? | Suggested parent component |
| `group_hint` | str? | Grouping suggestion |
| `styles` | dict | CSS-like styles (background, color, etc.) |
| `state` | dict | UI state (enabled, checked, etc.) |
| `visual_semantic` | str? | Semantic type override |

## Configuration

Environment variables:

```
UIBINDER_VISION_PROVIDER=local|remote|mistral|auto
UIBINDER_VISION_BASE_URL=https://api.mistral.ai/v1
UIBINDER_VISION_MODEL=pixtral-latest
UIBINDER_VISION_API_KEY=<key>
UIBINDER_VISION_MAX_COST_USD=2.0
UIBINDER_VISION_TIMEOUT=60
```

## Budget Tracking

`VisionBudget` enforces cost limits:
- Per-call cost tracking
- Automatic rejection when limit exceeded
- Thread-safe accounting

## AUTO Mode Logic

1. Run local heuristic
2. Calculate average confidence
3. If confidence < threshold (default 0.6), try remote
4. Use whichever result is better
5. Track fallback usage in provenance

## Mistral Support

Mistral uses the same OpenAI-compatible interface. No separate implementation needed — just configure with Mistral's base URL and model name.
