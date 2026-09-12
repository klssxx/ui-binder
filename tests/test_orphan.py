"""Orphan detector tests (directive §48): BOUND / UNBOUND / BROKEN / UNKNOWN / LEGACY."""
from __future__ import annotations

from backend.verification.orphan import functional_coverage, orphan_report


def cap(cid, conf=0.9, **over):
    base = {"capability_id": cid, "kind": "function", "name": cid,
            "qualified_name": f"x::{cid}", "confidence": conf,
            "origin_file": "a.py", "legacy": False}
    base.update(over)
    return base


def bind(target, status="CONFIRMED"):
    return {"binding_id": f"b-{target}-{status}", "component_id": "c1",
            "event": "onClick", "target_capability": target, "status": status}


def test_unbound_when_no_binding():
    r = orphan_report([cap("generate")], [])
    assert r["unbound"] == 1 and r["bound"] == 0


def test_bound_when_confirmed():
    r = orphan_report([cap("generate")], [bind("generate")])
    assert r["bound"] == 1
    assert r["detail"]["BOUND"][0]["capability_id"] == "generate"


def test_broken_when_only_broken_bindings():
    r = orphan_report([cap("generate")], [bind("generate", "BROKEN")])
    assert r["broken"] == 1


def test_unknown_when_low_confidence():
    r = orphan_report([cap("mystery", conf=0.2)], [])
    assert r["unknown"] == 1


def test_legacy_never_deleted():
    r = orphan_report([cap("old", legacy=True)], [])
    assert r["legacy"] == 1
    assert r["detail"]["LEGACY"][0]["name"] == "old"


def test_functional_coverage():
    caps = [cap(f"c{i}") for i in range(10)]
    bindings = [bind(f"c{i}") for i in range(7)]
    assert functional_coverage(caps, bindings) == 70.0
    assert functional_coverage([], []) == 100.0


def test_policy_statement_present():
    r = orphan_report([], [])
    assert "policy" in r
    assert "acción explícita del usuario" in r["policy"]
