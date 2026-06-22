"""Stage 2 — per-field translation. One component -> one machine subquery.

Closed-vocab fields are grounded against the taxonomy CSV (with hierarchy
expansion); open fields produce REGEX/MATCH directly; enums and booleans map to
fixed values. A pluggable normalizer runs first to absorb misspellings.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Protocol

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
from oppp.registry import Registry
from oppp.services.base import ServiceConfig, get_service
from oppp.taxonomy.index import get_index


class Translator(Protocol):
    def translate(
        self, component: Component, service: ServiceConfig, normalizer: Normalizer | None
    ) -> MachineSubquery | None: ...


translator_registry: Registry[Translator] = Registry("translator")


def get_translator(name: str = "tool", **kwargs) -> Translator:
    return translator_registry.create(name, **kwargs)


# Open fields searched as free-text substrings rather than exact values.
_REGEX_OPEN_FIELDS = {"studyGroup", "ages"}

# Minimal synonym expansion for free-text study-group conditions (extensible).
_STUDYGROUP_SYNONYMS: dict[str, list[str]] = {
    "hepatic impairment": [
        "cirrhosis",
        "liver disease",
        "hepatic insufficiency",
        "hepatic impairment",
        "liver impairment",
        "Child-Pugh B",
        "Child-Pugh C",
        "liver failure",
        "hepatic failure",
        "liver insufficiency",
        "hepatic disease",
    ],
    "renal impairment": [
        "renal impairment",
        "renal insufficiency",
        "kidney disease",
        "renal failure",
        "chronic kidney disease",
        "CKD",
    ],
}


def translate_one(
    component: Component,
    service: str = "safety",
    normalizer: str = "noop",
    *,
    llm_select: bool = False,
) -> MachineSubquery | None:
    """Convenience wrapper resolving service + normalizer by name.

    Defaults to deterministic (no LLM selection) so isolated translation in tests
    and the `field` CLI is hermetic; pass llm_select=True to exercise the selector.
    """
    return translate_component(
        component, get_service(service), get_normalizer(normalizer), llm_select=llm_select
    )


def translate_component(
    component: Component,
    service: ServiceConfig,
    normalizer: Normalizer | None = None,
    *,
    llm_select: bool = True,
) -> MachineSubquery | None:
    """Translate a single FILTER component. Returns None for QUESTION components.

    `llm_select` toggles the optional LLM term selector for closed-vocab fields;
    set it False for a fully offline/deterministic translation (tests, eval).
    """
    if component.type is ComponentType.QUESTION:
        return None
    normalizer = normalizer or get_normalizer("noop")
    spec = service.spec(component.field)
    frag = component.nl_fragment.strip()

    if spec is None:
        return MachineSubquery(
            field=component.field,
            operator=Operator.MATCH,
            value=frag,
            boolean_group=component.boolean_group,
            notes="no field spec; raw value",
        )

    if spec.bucket == "closed" and spec.taxonomy:
        return _translate_closed(component, spec, service, normalizer, llm_select=llm_select)
    if spec.bucket == "boolean":
        return _translate_boolean(component, spec)
    if spec.bucket == "enum":
        return _translate_enum(component, spec)
    return _translate_open(component, spec)


class ToolTranslator:
    """Translator: ground each field via its taxonomy tool / grounding rules.

    A thin object wrapper around :func:`translate_component` so Stage 2 is pluggable
    and isolatable like the other stages. With ``llm_select=True`` (the production
    'tool' backend) closed-vocab fields also run the LLM term selector to refine
    the candidate vocabulary; ``llm_select=False`` (the offline 'deterministic'
    double) uses pure taxonomy grounding so the suite/eval need no LLM.
    """

    def __init__(self, llm_select: bool = True) -> None:
        self.llm_select = llm_select

    def translate(self, component, service, normalizer=None):
        return translate_component(component, service, normalizer, llm_select=self.llm_select)


translator_registry.add("tool", lambda **kw: ToolTranslator(**{"llm_select": True, **kw}))
translator_registry.add("deterministic", lambda **kw: ToolTranslator(**{"llm_select": False, **kw}))


# ---------------------------------------------------------------------------
# Optional LLM term selector — refines the taxonomy candidate pool.
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _get_term_selector():
    """Lazily build the structured-output LLM used to pick final vocabulary terms.

    Routes through the central :mod:`oppp.llm` factory so temperature (0) and the
    LangChain/Portkey wiring live in one place — the same client the 'llm'
    decomposer and aggregator use. Returns None when creds or the optional 'llm'
    deps are missing, so the deterministic core keeps working offline.
    """
    from oppp.llm import LLMUnavailable, structured

    try:
        return structured(TermSelection)
    except LLMUnavailable:
        return None


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


def _llm_map_to_vocab(
    fragment: str, field: str, index, *, limit: int = 8, accept_score: float = 90.0
) -> list[GroundingHit]:
    """Closed-vocab fallback when exact/fuzzy lookup finds nothing.

    The phrase is a synonym, scientific name, brand, or abbreviation the string
    matcher missed (e.g. ``'homo sapiens' -> 'Human'``, ``'Columvi' -> 'Glofitamab'``).
    Ask the LLM for the canonical vocabulary term(s) it refers to, then **re-ground
    each proposal through the taxonomy** so the emitted value is guaranteed to exist
    in the controlled vocabulary — we never emit the model's raw string (CONST-1).

    Returns the grounded hits (marked ``match="llm"`` for provenance). Returns ``[]``
    when no LLM is configured or nothing the model proposes grounds, so the caller
    flags the gap rather than inventing a value.
    """
    selector = _get_term_selector()
    if selector is None:
        return []
    prompt = (
        "You map a user's phrase to a controlled pharmacology vocabulary for the "
        f"field {field!r}. The phrase did NOT match the vocabulary by exact or fuzzy "
        "string match — it is most likely a synonym, scientific name, brand name, or "
        "abbreviation of a standard term.\n"
        f"User phrase: {fragment!r}\n"
        "Return the canonical preferred term(s) this phrase refers to (e.g. "
        "'homo sapiens' -> 'Human'; 'Columvi' -> 'Glofitamab'; 'per os' -> 'Oral'). "
        "Use standard term spellings. Return several only if the phrase genuinely "
        "refers to multiple terms; otherwise return the single best term."
    )
    try:
        result: TermSelection = selector.invoke(prompt)  # type: ignore[assignment]
    except Exception:  # pragma: no cover - network/credential failure -> fallback
        return []
    hits: list[GroundingHit] = []
    seen: set[str] = set()
    for proposal in result.selected:
        match = index.lookup(proposal, match="fuzzy", limit=1)
        if match and match[0].score >= accept_score and match[0].name.lower() not in seen:
            hit = match[0]
            hit.match = "llm"  # record that this term was reached via LLM mapping
            seen.add(hit.name.lower())
            hits.append(hit)
        if len(hits) >= limit:
            break
    return hits


# ---------------------------------------------------------------------------
def _translate_closed(component, spec, service, normalizer, *, llm_select=True) -> MachineSubquery:
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
         this falls back to the top-5 fuzzy hits. When exact+fuzzy find nothing, the
         LLM maps the phrase to canonical vocabulary term(s) (:func:`_llm_map_to_vocab`),
         re-grounded against the taxonomy so the value stays in-vocabulary.
    3. If nothing matches even then (or offline with no LLM), the term is flagged
       unmatched (confidence 0) rather than emitting an invented value (CONST-1).
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
        if not base and llm_select:
            # Synonym the string matcher missed -> map via LLM, then re-ground.
            base = _llm_map_to_vocab(frag, component.field, index, limit=1)
        canonical = base[0].name if base else term
        family = index.expand_family(canonical)
        if family:
            hits = family
            expanded_from = "family"
        else:
            hits = base
    else:
        # Resolution order: exact -> close (fuzzy) -> LLM. Exact/fuzzy build the
        # candidate pool and, when enabled, the LLM picks the final term(s) from it.
        # When exact+fuzzy find nothing, fall back to the LLM mapping the phrase to
        # canonical vocabulary term(s) (e.g. 'homo sapiens' -> 'Human'), re-grounded
        # so the value is always drawn from the vocabulary. Offline (llm_select=False)
        # this yields no hits and the gap is flagged below rather than invented.
        candidates = index.lookup(term, match="fuzzy", limit=8)
        if candidates:
            chosen = (
                _llm_select(frag, component.field, [h.name for h in candidates])
                if llm_select
                else None
            )
            if chosen:
                chosen_set = {c.lower() for c in chosen}
                hits = [h for h in candidates if h.name.lower() in chosen_set]
            else:
                hits = candidates[:5]
        elif llm_select:
            hits = _llm_map_to_vocab(frag, component.field, index)
        else:
            hits = []

    if hits:
        values = [h.name for h in hits]
        grounding = Grounding(
            matched=hits[:25],
            expanded_from=expanded_from,
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
        field=spec.emit_field,
        operator=Operator.MATCH,
        value=value,
        boolean_group=component.boolean_group,
        entity_name=spec.entity_name,
        collapse_to=collapse_to,
        grounding=grounding,
        notes=note,
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
        field=spec.emit_field,
        operator=Operator.MATCH,
        value=component.nl_fragment,
        notes="value not in enum allow-list",
    )


def _translate_open(component, spec) -> MachineSubquery:
    frag = component.nl_fragment.strip()
    if spec.name in _REGEX_OPEN_FIELDS:
        key = frag.lower()
        terms = _STUDYGROUP_SYNONYMS.get(key, [frag])
        pattern = ".*(" + "|".join(re.escape(t) for t in terms) + ").*"
        return MachineSubquery(
            field=spec.emit_field,
            operator=Operator.REGEX,
            pattern=pattern,
            boolean_group=component.boolean_group,
            entity_name=spec.entity_name,
        )
    return MachineSubquery(
        field=spec.emit_field,
        operator=Operator.MATCH,
        value=frag,
        boolean_group=component.boolean_group,
        entity_name=spec.entity_name,
    )
