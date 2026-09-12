"""Binding verifier — validates bindings against the CURRENT capability set + AST."""
from __future__ import annotations

from typing import Any

_OK_EVENTS = {"onClick", "onChange", "onSubmit", "onInput", "onFocus", "onBlur", "onSelect",
              "onHover", "onLoad", "onError", "onToggle"}


def verify_bindings(bindings: list[dict[str, Any]], capabilities: list[dict[str, Any]],
                    components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return binding patches: status + problems. Caller applies the status."""
    caps_by_id = {c["capability_id"]: c for c in capabilities}
    comp_ids = {c["id"] for c in components}
    results: list[dict[str, Any]] = []
    for b in bindings:
        problems: list[str] = []
        cap = caps_by_id.get(b["target_capability"])
        if cap is None:
            problems.append(f"target capability '{b['target_capability']}' no longer exists")
        if b["component_id"] not in comp_ids:
            problems.append(f"component '{b['component_id']}' not in current UI AST")
        if b["event"] not in _OK_EVENTS:
            problems.append(f"unsupported event '{b['event']}'")
        if cap is not None:
            input_names = {p.get("name") for p in cap.get("inputs", [])}
            required = {p.get("name") for p in cap.get("inputs", []) if p.get("required")}
            mapped = {m.get("target") for m in b.get("input_mapping", [])}
            missing = required - mapped
            if missing:
                problems.append(f"required inputs not mapped: {sorted(missing)}")
            unknown = mapped - input_names
            if unknown:
                problems.append(f"mapped inputs not in signature: {sorted(unknown)}")
        if problems:
            results.append({"binding_id": b["binding_id"], "status": "BROKEN",
                            "problems": problems})
        else:
            results.append({"binding_id": b["binding_id"], "status": b.get("status"),
                            "problems": []})
    return results
