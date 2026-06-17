"""Stage 2 — per-field translation. One component -> one machine subquery.

Closed-vocab fields are grounded against the taxonomy CSV (with hierarchy
expansion); open fields produce REGEX/MATCH directly; enums and booleans map to
fixed values. A pluggable normalizer runs first to absorb misspellings.
"""

from __future__ import annotations

import re
from functools import lru_cache

from oppp.models import (
    Component,
    ComponentType,
    Grounding,
    GroundingHit,
    MachineSubquery,
    Operator,
    TermSelection,
)
from oppp.normalize.base import Normalizer, get_normalizer
from oppp.services.base import ServiceConfig, get_service
from oppp.taxonomy.index import get_index

# Open fields searched as free-text substrings rather than exact values.
_REGEX_OPEN_FIELDS = {"studyGroup", "ages"}

# Minimal synonym expansion for free-text study-group conditions (extensible).
_STUDYGROUP_SYNONYMS: dict[str, list[str]] = {
    "hepatic impairment": [
        "cirrhosis", "liver disease", "hepatic insufficiency", "hepatic impairment",
        "liver impairment", "Child-Pugh B", "Child-Pugh C", "liver failure",
        "hepatic failure", "liver insufficiency", "hepatic disease",
    ],
    "renal impairment": [
        "renal impairment", "renal insufficiency", "kidney disease", "renal failure",
        "chronic kidney disease", "CKD",
    ],
}


def translate_one(
    component: Component, service: str = "safety", normalizer: str = "noop"
) -> MachineSubquery | None:
    """Convenience wrapper resolving service + normalizer by name."""
    return translate_component(component, get_service(service), get_normalizer(normalizer))


def translate_component(
    component: Component, service: ServiceConfig, normalizer: Normalizer | None = None
) -> MachineSubquery | None:
    """Translate a single FILTER component. Returns None for QUESTION components."""
    if component.type is ComponentType.QUESTION:
        return None
    normalizer = normalizer or get_normalizer("noop")
    spec = service.spec(component.field)
    frag = component.nl_fragment.strip()

    if spec is None:
        return MachineSubquery(
            field=component.field, operator=Operator.MATCH, value=frag,
            boolean_group=component.boolean_group, notes="no field spec; raw value",
        )

    if spec.bucket == "closed" and spec.taxonomy:
        return _translate_closed(component, spec, service, normalizer)
    if spec.bucket == "boolean":
        return _translate_boolean(component, spec)
    if spec.bucket == "enum":
        return _translate_enum(component, spec)
    return _translate_open(component, spec)


# ---------------------------------------------------------------------------
# Optional LLM term selector — refines the taxonomy candidate pool.
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _get_term_selector():
    """Lazily build the structured-output LLM used to pick final vocabulary terms.

    Mirrors the LangChain/Portkey wiring of the 'llm' decomposer backend. Returns
    None when creds or the optional 'llm' deps are missing, so the deterministic
    core keeps working offline.
    """
    from oppp.config import get_settings, load_dotenv_if_present

    load_dotenv_if_present()
    s = get_settings()
    if not (s.portkey_api_key and s.portkey_endpoint):
        return None
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:  # pragma: no cover - optional extra
        return None
    llm = ChatOpenAI(
        api_key=s.portkey_api_key,
        base_url=s.portkey_endpoint,
        model=f"{s.portkey_provider}/{s.tool_model}",
        temperature=0,
    )
    return llm.with_structured_output(TermSelection)


def _llm_select(fragment: str, field: str, candidates: list[str]) -> list[str] | None:
    """Ask the LLM to choose the final term(s) from the taxonomy candidate pool.

    Given the user's phrase and the exact/fuzzy candidates, returns the subset the
    model judges to match the intent (filtered to valid candidate spellings).
    Returns None when no LLM is configured or the call fails / returns nothing, so
    the caller falls back to the deterministic selection.
    """
    selector = _get_term_selector()
    if selector is None or not candidates:
        return None
    options = "\n".join(f"- {c}" for c in candidates)
    prompt = (
        "You ground a user's phrase to a controlled pharmacology vocabulary.\n"
        f"Field: {field}\n"
        f"User phrase: {fragment!r}\n"
        "Candidate vocabulary terms (choose only from these):\n"
        f"{options}\n\n"
        "Return the term(s) that best match the user's intent. Return several only "
        "if the phrase genuinely refers to multiple terms; otherwise return the single "
        "best. Use the exact candidate spellings."
    )
    try:
        result: TermSelection = selector.invoke(prompt)  # type: ignore[assignment]
    except Exception:  # pragma: no cover - network/credential failure -> fallback
        return None
    allowed = {c.lower() for c in candidates}
    chosen = [c for c in result.selected if c.lower() in allowed]
    return chosen or None


# ---------------------------------------------------------------------------
def _translate_closed(component, spec, service, normalizer) -> MachineSubquery:
    """Resolve a closed-vocabulary field's value by grounding free text against a taxonomy.

    Takes one decomposed ``component`` (raw NL fragment + target field) and turns it
    into a single ``MachineSubquery`` whose value is drawn from the field's controlled
    vocabulary CSV (e.g. drugs, effects, species, route). The fragment is:

    1. Normalized (optional typo correction) before lookup.
    2. Grounded against the taxonomy index, with one of three expansion behaviours:
       - class term -> expand to all child terms;
       - ``rollup_to_siblings`` field (e.g. effects) -> resolve canonical label, then
         roll up to its MedDRA family/sibling set;
       - otherwise -> exact/fuzzy lookup builds a candidate pool, and the optional
         LLM selector (:func:`_llm_select`) picks the final term(s) from it; offline
         this falls back to the top-5 fuzzy hits.
    3. If nothing matches, the normalized term is passed through unmatched (confidence 0).
    4. For drug-style fields (``fuzzy_wildcard``), a single leaf term gets a trailing
       ``*`` wildcard to broaden the match.

    ``documentYear`` is delegated to :func:`_translate_year` (numeric RANGE/MATCH).

    The result carries a ``Grounding`` record (matched hits, expansion source,
    confidence) and, for family rollups, a ``collapse_to`` canonical term so Stage 3
    can shrink the query if it exceeds the API constraint budget. Emits a ``MATCH``
    operator on ``spec.emit_field``, preserving the component's boolean group and
    entity routing.
    """
    index = get_index(spec.taxonomy)
    frag = component.nl_fragment.strip()

    # documentYear: numeric thresholds -> RANGE / MATCH.
    if spec.taxonomy == "document_year":
        return _translate_year(component, spec)

    norm = normalizer.normalize(frag, field=component.field, bucket="closed")
    term = norm.normalized

    expanded_from = None
    canonical = term
    if index.is_class(term):
        hits = index.expand_children(term)
        expanded_from = "class"
    elif spec.rollup_to_siblings:
        # Resolve to the canonical label, then roll up to its MedDRA family.
        base = index.lookup(term, match="fuzzy", limit=1)
        canonical = base[0].name if base else term
        family = index.expand_family(canonical)
        if family:
            hits = family
            expanded_from = "family"
        else:
            hits = base
    else:
        # Exact + fuzzy candidate pool, then let the LLM pick the final term(s)
        # from those candidates. Falls back to the deterministic top hits offline.
        candidates = index.lookup(term, match="fuzzy", limit=8)
        chosen = _llm_select(frag, component.field, [h.name for h in candidates])
        if chosen:
            chosen_set = {c.lower() for c in chosen}
            hits = [h for h in candidates if h.name.lower() in chosen_set]
        else:
            hits = candidates[:5]

    if hits:
        values = [h.name for h in hits]
        grounding = Grounding(
            matched=hits[:25], expanded_from=expanded_from,
            confidence=min(1.0, (hits[0].score / 100.0)),
        )
    else:
        values = [term]
        grounding = Grounding(
            matched=[GroundingHit(name=term, match="unmatched", score=0.0)],
            confidence=0.0,
        )

    # Drug-style fuzzy broadening: trailing wildcard on a single leaf term.
    if spec.fuzzy_wildcard and expanded_from is None and len(values) == 1:
        values = [f"{values[0]}*"]

    value = values if len(values) != 1 else values[0]
    note = norm.note if norm.changed else None
    # For a MedDRA family rollup, remember the canonical term so Stage 3 can
    # collapse back to it if the expanded query would exceed the API budget.
    collapse_to = canonical if expanded_from == "family" else None
    return MachineSubquery(
        field=spec.emit_field, operator=Operator.MATCH, value=value,
        boolean_group=component.boolean_group, entity_name=spec.entity_name,
        collapse_to=collapse_to, grounding=grounding, notes=note,
    )


def _translate_year(component, spec) -> MachineSubquery:
    frag = component.nl_fragment.lower()
    m = re.search(r"(\d{4})", frag)
    year = int(m.group(1)) if m else None
    if year is None:
        return MachineSubquery(field=spec.emit_field, operator=Operator.MATCH, value=frag)
    if any(w in frag for w in ("after", "since", "from", ">")):
        return MachineSubquery(field=spec.emit_field, operator=Operator.RANGE, value={"min": year})
    if any(w in frag for w in ("before", "until", "<")):
        return MachineSubquery(field=spec.emit_field, operator=Operator.RANGE, value={"max": year})
    return MachineSubquery(field=spec.emit_field, operator=Operator.MATCH, value=year)


def _translate_boolean(component, spec) -> MachineSubquery:
    val = str(component.nl_fragment).strip().lower() in ("true", "yes", "1", "preclinical")
    return MachineSubquery(field=spec.emit_field, operator=Operator.MATCH, value=val)


def _translate_enum(component, spec) -> MachineSubquery:
    frag = component.nl_fragment.strip().lower()
    for allowed in spec.enum_values:
        if allowed.lower() == frag:
            return MachineSubquery(field=spec.emit_field, operator=Operator.MATCH, value=allowed)
    return MachineSubquery(
        field=spec.emit_field, operator=Operator.MATCH, value=component.nl_fragment,
        notes="value not in enum allow-list",
    )


def _translate_open(component, spec) -> MachineSubquery:
    frag = component.nl_fragment.strip()
    if spec.name in _REGEX_OPEN_FIELDS:
        key = frag.lower()
        terms = _STUDYGROUP_SYNONYMS.get(key, [frag])
        pattern = ".*(" + "|".join(re.escape(t) for t in terms) + ").*"
        return MachineSubquery(
            field=spec.emit_field, operator=Operator.REGEX, pattern=pattern,
            boolean_group=component.boolean_group, entity_name=spec.entity_name,
        )
    return MachineSubquery(
        field=spec.emit_field, operator=Operator.MATCH, value=frag,
        boolean_group=component.boolean_group, entity_name=spec.entity_name,
    )
