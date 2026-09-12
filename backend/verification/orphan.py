"""Orphan detector — DELETE NOTHING: capabilities are never silently discarded.

Classification per capability:
  BOUND    — has ≥1 CONFIRMED binding
  UNBOUND  — no binding at all
  BROKEN   — only BROKEN bindings remain
  UNKNOWN  — detection confidence below 0.4 (treat as unverified, not absent)
  LEGACY   — explicitly marked by the user (requires explicit action)
"""
from __future__ import annotations

from typing import Any


def orphan_report(capabilities: list[dict[str, Any]], bindings: list[dict[str, Any]]) -> dict[str, Any]:
    bindings_by_cap: dict[str, list[dict[str, Any]]] = {}
    for b in bindings:
        bindings_by_cap.setdefault(b["target_capability"], []).append(b)

    classified: dict[str, list[dict[str, Any]]] = {"BOUND": [], "UNBOUND": [], "BROKEN": [],
                                                   "UNKNOWN": [], "LEGACY": []}
    for cap in capabilities:
        if cap.get("legacy"):
            classified["LEGACY"].append(_slim(cap))
            continue
        cap_bindings = bindings_by_cap.get(cap["capability_id"], [])
        if not cap_bindings:
            if float(cap.get("confidence", 0.5)) < 0.4:
                classified["UNKNOWN"].append(_slim(cap))
            else:
                classified["UNBOUND"].append(_slim(cap))
            continue
        statuses = {b.get("status") for b in cap_bindings}
        if "CONFIRMED" in statuses:
            classified["BOUND"].append(_slim(cap))
        elif statuses == {"BROKEN"}:
            classified["BROKEN"].append(_slim(cap))
        else:
            classified["UNBOUND"].append(_slim(cap))

    total = len(capabilities)
    return {
        "capabilities_detected": total,
        "bound": len(classified["BOUND"]),
        "unbound": len(classified["UNBOUND"]),
        "broken": len(classified["BROKEN"]),
        "unknown": len(classified["UNKNOWN"]),
        "legacy": len(classified["LEGACY"]),
        "detail": classified,
        "policy": "Ninguna capacidad se elimina nunca automáticamente. Marcar como LEGADO o "
                  "eliminar exige una acción explícita del usuario.",
    }


def functional_coverage(capabilities: list[dict[str, Any]], bindings: list[dict[str, Any]]) -> float:
    report = orphan_report(capabilities, bindings)
    total = report["capabilities_detected"]
    if total == 0:
        return 100.0
    covered = report["bound"]
    return round(100.0 * covered / total, 1)


def _slim(cap: dict[str, Any]) -> dict[str, Any]:
    return {
        "capability_id": cap["capability_id"],
        "kind": cap.get("kind"),
        "name": cap.get("name"),
        "qualified_name": cap.get("qualified_name"),
        "origin_file": cap.get("origin_file"),
        "confidence": cap.get("confidence"),
    }
