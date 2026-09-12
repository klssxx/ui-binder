"""Smart Binder tests (directive §47): exact, semantic, multiple, none, broken,
changed signature, missing input, unused output."""
from __future__ import annotations

from backend.bindings.matcher import suggest_bindings
from backend.bindings.verifier import verify_bindings


def component(**over):
    base = {"id": "component_0002", "type": "button", "name": "generate-button",
            "text": "Generar", "bbox": {"x": 0, "y": 0, "width": 120, "height": 40}}
    base.update(over)
    return base


def capability(**over):
    base = {
        "capability_id": "cap_1", "kind": "route", "name": "api_generate",
        "qualified_name": "backend/app.py::api_generate", "description": "Generate an idea",
        "inputs": [{"name": "prompt", "type": "str", "required": True, "description": ""}],
        "outputs": [{"name": "return", "type": "GenerateResponse", "required": True, "description": ""}],
        "side_effects": ["fs"], "origin_file": "backend/app.py", "origin_line": 60,
        "framework": "fastapi", "http_method": "POST", "http_path": "/api/generate",
        "dependencies": [], "legacy": False, "confidence": 0.95,
    }
    base.update(over)
    return base


def test_exact_name_match_scores_high():
    caps = [capability(name="generar", http_path="/api/generar")]
    s = suggest_bindings(component(text="Generar"), caps)
    assert s and s[0].score >= 0.5
    assert any("exact name match" in r for r in s[0].rationale)


def test_semantic_verb_match():
    caps = [capability(name="api_generate", http_path="/api/generate")]
    s = suggest_bindings(component(text="Generar idea"), caps)
    assert s, "verb lexicon must bridge ES button text → EN route"
    assert s[0].capability_id == "cap_1"


def test_route_path_tail_match():
    s = suggest_bindings(component(text="Generar"), [capability()])
    assert s
    assert any("route path tail" in r for r in s[0].rationale)


def test_multiple_candidates_ordered():
    caps = [
        capability(capability_id="cap_mid", name="generate_idea", kind="function",
                   http_path="", framework="python",
                   description="Generate an idea from a prompt"),
        capability(capability_id="cap_high", name="api_generate", http_path="/api/generate"),
    ]
    s = suggest_bindings(component(text="Generar"), caps)
    assert len(s) >= 2, "both candidates must clear the threshold"
    assert s[0].capability_id == "cap_high"
    assert s[0].score > s[-1].score


def test_no_candidate_below_threshold():
    caps = [capability(capability_id="cap_x", name="restore_session_snapshot",
                       http_path="/api/session/restore",
                       description="Restore a saved session")]
    s = suggest_bindings(component(name="cancel-button", text="Cancelar"), caps)
    assert all(x.score < 0.5 for x in s) or s == []


def test_determinism():
    caps = [capability(), capability(capability_id="cap_2", name="export_report",
                                     http_path="/api/export")]
    c = component(text="Generar")
    a = suggest_bindings(c, caps)
    b = suggest_bindings(c, caps)
    assert [(x.capability_id, x.score) for x in a] == [(x.capability_id, x.score) for x in b]


# ---------- verifier (§47: broken/changed signature/missing input/unused output) ----------

def binding(**over):
    base = {"binding_id": "bind_1", "component_id": "component_0002", "event": "onClick",
            "target_capability": "cap_1", "status": "CONFIRMED",
            "input_mapping": [{"source": "component_0003.value", "target": "prompt"}],
            "output_mapping": [{"source": "return", "target": "component_0009"}]}
    base.update(over)
    return base


def components():
    return [
        {"id": "component_0002", "type": "button"},
        {"id": "component_0003", "type": "input"},
        {"id": "component_0009", "type": "panel"},
    ]


def test_verifier_ok():
    res = verify_bindings([binding()], [capability()], components())
    assert res[0]["status"] == "CONFIRMED" and res[0]["problems"] == []


def test_verifier_broken_target():
    res = verify_bindings([binding()], [], components())
    assert res[0]["status"] == "BROKEN"
    assert any("no longer exists" in p for p in res[0]["problems"])


def test_verifier_changed_signature_missing_required_input():
    cap = capability(inputs=[{"name": "prompt", "required": True},
                             {"name": "mode", "required": True}])
    res = verify_bindings([binding()], [cap], components())
    assert res[0]["status"] == "BROKEN"
    assert any("not mapped" in p for p in res[0]["problems"])


def test_verifier_unknown_mapped_input():
    cap = capability(inputs=[])
    res = verify_bindings([binding()], [cap], components())
    assert any("not in signature" in p for p in res[0]["problems"])


def test_verifier_missing_component():
    res = verify_bindings([binding(component_id="ghost")], [capability()], components())
    assert any("not in current UI AST" in p for p in res[0]["problems"])


def test_unused_output_is_not_a_problem():
    b = binding(output_mapping=[])
    res = verify_bindings([b], [capability()], components())
    assert res[0]["problems"] == []
