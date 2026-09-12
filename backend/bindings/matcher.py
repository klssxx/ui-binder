"""Smart Binder — deterministic, auditable binding suggestions.

Scoring signals (weights documented in docs/BINDING_MODEL.md):
  +0.55  normalized exact match between component text/name and capability name
  +0.20  verb-lexicon match (generate/evaluar/save/export/search/...)
  +0.10  token overlap (Jaccard over normalized tokens)
  +0.08  parameter-name match against component name tokens
  +0.07  component-type prior (button→route/function/handler)
Score is clipped to [0, 0.98]; only user confirmation makes it a FACT.
"""
from __future__ import annotations

import re
from typing import Any

from backend.schema.binding import BindingSuggestion

_VERB_LEXICON: dict[str, list[str]] = {
    "generate": ["generate", "generar", "create", "crear", "build", "make", "new"],
    "evaluate": ["evaluate", "evaluar", "assess", "score", "puntuar", "rate", "review"],
    "save": ["save", "guardar", "store", "persist", "almacenar"],
    "load": ["load", "cargar", "fetch", "get", "obtener", "read", "leer", "history", "historial"],
    "export": ["export", "exportar", "download", "descargar", "report", "informe"],
    "search": ["search", "buscar", "find", "encontrar", "query"],
    "run": ["run", "ejecutar", "execute", "start", "iniciar", "launch"],
    "compare": ["compare", "comparar", "diff", "versus"],
    "restore": ["restore", "restaurar", "recover", "recuperar", "session", "sesión"],
    "open": ["open", "abrir", "import", "importar"],
    "delete": ["delete", "eliminar", "remove", "borrar"],
    "cancel": ["cancel", "cancelar", "close", "cerrar"],
    "analyze": ["analyze", "analizar", "inspect", "inspeccionar"],
    "verify": ["verify", "verificar", "check", "comprobar", "validate", "validar"],
}

_TYPE_PRIOR: dict[str, set[str]] = {
    "button": {"route", "function", "handler", "method"},
    "input": {"function", "method"},
    "textarea": {"function", "method"},
    "select": {"function", "method"},
    "chart": {"service", "route"},
    "table": {"service", "route"},
}

_STOPWORDS = {"the", "a", "an", "el", "la", "los", "las", "de", "del", "un", "una",
              "button", "boton", "botón", "input", "field", "campo", "panel", "text", "texto"}


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9áéíóúñü\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> set[str]:
    words = _normalize(text).replace("_", " ").split()
    return {w for w in words if w and w not in _STOPWORDS}


def _camel_split(text: str) -> set[str]:
    return _tokens(re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text))


def component_terms(component: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    terms |= _tokens(component.get("text") or "")
    terms |= _camel_split(component.get("name") or "")
    return {t for t in terms if len(t) > 1}


def capability_terms(capability: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    terms |= _camel_split(capability.get("name") or "")
    terms |= _tokens(capability.get("description") or "")
    terms |= _tokens(capability.get("http_path") or "/")
    terms |= {p.get("name", "") for p in capability.get("inputs", [])}
    return {t for t in terms if len(t) > 1}


def _verb_matches(terms: set[str]) -> set[str]:
    hits: set[str] = set()
    for verb, synonyms in _VERB_LEXICON.items():
        for term in terms:
            if term in synonyms or any(syn.startswith(term) and len(term) >= 4 for syn in synonyms):
                hits.add(verb)
                break
    return hits


def _stem_like(a: str, b: str) -> bool:
    """Prefix-stem equivalence: 'generar' ≈ 'generate' (shared 5-char prefix)."""
    if a == b:
        return True
    return len(a) >= 5 and len(b) >= 5 and a[:5] == b[:5]


def score_component_capability(component: dict[str, Any], capability: dict[str, Any],
                               existing_bound: set[str] | None = None) -> tuple[float, list[str]]:
    """Deterministic score in [0, 0.98] + rationale lines."""
    rationale: list[str] = []
    score = 0.0

    comp_terms = component_terms(component)
    cap_terms = capability_terms(capability)
    cap_name_norm = _normalize(capability.get("name") or "").replace(" ", "")
    cap_base = (capability.get("name") or "").split(".")[-1].lower()

    # 1) exact normalized match
    for term in comp_terms:
        if term == cap_base or term == cap_name_norm:
            score += 0.55
            rationale.append(f"exact name match: '{term}' ≈ '{capability.get('name')}'")
            break

    # 2) verb lexicon (ES/EN)
    comp_verbs = _verb_matches(comp_terms)
    cap_verbs = _verb_matches(cap_terms)
    shared_verbs = comp_verbs & cap_verbs
    if shared_verbs:
        score += min(0.24, 0.14 * len(shared_verbs))
        rationale.append(f"verb match: {sorted(shared_verbs)}")

    # 3) stem-equivalent token overlap (Jaccard with prefix-5 stems)
    stem_pairs = [(t, c) for t in comp_terms for c in cap_terms if _stem_like(t, c)]
    if comp_terms and cap_terms and stem_pairs:
        matched_comp = {t for t, _ in stem_pairs}
        matched_cap = {c for _, c in stem_pairs}
        j = (len(matched_comp) + len(matched_cap)) / (len(comp_terms) + len(cap_terms))
        score += 0.12 * min(1.0, j * 4)
        if matched_comp & matched_cap:
            score += 0.25
            rationale.append(f"token match: {sorted(matched_comp & matched_cap)[:5]}")
        else:
            score += 0.12
            rationale.append(f"stem-matched tokens: "
                             f"{[f'{t}≈{c}' for t, c in stem_pairs[:3]]}")
        if len(matched_comp) > 1:
            score += 0.05

    # 4) parameter match
    param_names = {p.get("name", "").lower() for p in capability.get("inputs", [])}
    if param_names & {t for t in comp_terms if len(t) >= 3}:
        score += 0.08
        rationale.append("parameter name matches component term")

    # 5) component type prior
    ctype = component.get("type", "")
    if ctype in _TYPE_PRIOR and capability.get("kind") in _TYPE_PRIOR[ctype]:
        score += 0.08
        rationale.append(f"type prior: {ctype} → {capability.get('kind')}")

    # 6) route path tail similarity with stem tolerance
    http_path = (capability.get("http_path") or "").lower().strip()
    if http_path and http_path != "/":
        path_tail = http_path.rsplit("/", 1)[-1]
        tail_hit = any(_stem_like(t, path_tail) for t in comp_terms) if path_tail else False
        if tail_hit:
            score += 0.18
            rationale.append(f"route path tail matches: /{path_tail}")

    if capability.get("legacy"):
        score *= 0.5
        rationale.append("capability marked LEGACY — score halved")

    return min(score, 0.98), rationale


def suggest_bindings(component: dict[str, Any], capabilities: list[dict[str, Any]],
                     limit: int = 5) -> list[BindingSuggestion]:
    suggestions: list[BindingSuggestion] = []
    for cap in capabilities:
        if cap.get("kind") in ("class",):
            continue
        score, rationale = score_component_capability(component, cap)
        if score < 0.15:
            continue
        suggestions.append(BindingSuggestion(
            capability_id=cap["capability_id"],
            score=round(score, 3),
            rationale=rationale or ["weak signal"],
            inputs=cap.get("inputs", []),
            outputs=cap.get("outputs", []),
            side_effects=cap.get("side_effects", []),
        ))
    suggestions.sort(key=lambda s: (-s.score, s.capability_id))
    return suggestions[:limit]
