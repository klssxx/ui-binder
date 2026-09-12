"""Sample application backend — the reproducible E2E target for UI Binder.

Deliberately small but real: input → button → API → result, plus extra
service functions that remain UNBOUND so the orphan detector has something
honest to report.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Sample Idea Generator")

_STORE = Path(__file__).parent / "results.json"


class GenerateRequest(BaseModel):
    prompt: str
    mode: str = "basic"


class GenerateResponse(BaseModel):
    result: str
    score: float


def generate_idea(prompt: str, mode: str = "basic") -> str:
    """Build a deterministic idea string from the prompt."""
    base = prompt.strip() or "empty prompt"
    if mode == "advanced":
        return f"ADVANCED IDEA :: {base} :: leverage synergies"
    return f"IDEA :: {base}"


def evaluate_idea(text: str) -> float:
    """Score an idea deterministically (length-based)."""
    return round(min(1.0, len(text) / 120.0), 2)


def save_result(result: str) -> None:
    """Persist the latest result to disk (side effect: fs)."""
    _STORE.write_text(json.dumps({"result": result}), encoding="utf-8")


def load_history() -> list[str]:
    """Return previously saved results."""
    if not _STORE.exists():
        return []
    return [json.loads(_STORE.read_text(encoding="utf-8")).get("result", "")]


def export_report() -> str:
    """Export a markdown report (unrouted in v0.1 — orphan by design)."""
    return "# Report\n\n(no data)"


def restore_session() -> dict:
    """Restore a previous session (unrouted in v0.1 — orphan by design)."""
    return {"restored": False}


@app.post("/api/generate", response_model=GenerateResponse)
def api_generate(request: GenerateRequest) -> GenerateResponse:
    """Generate an idea from a prompt."""
    idea = generate_idea(request.prompt, request.mode)
    score = evaluate_idea(idea)
    save_result(idea)
    return GenerateResponse(result=idea, score=score)


@app.get("/api/health")
def api_health() -> dict:
    return {"status": "ok"}
