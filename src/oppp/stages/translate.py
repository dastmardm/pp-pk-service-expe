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
    EntityAnnotation,
    Grounding,
    GroundingHit,
    MachineSubquery,
    Operator,
    TermSelection,
)
from oppp.normalize.base import Normalizer, get_normalizer
from oppp.registry import Registry
from oppp.services.base import ServiceConfig, get_service
from oppp.taxonomy.index import get_index, singular_candidates


class Translator(Protocol):
    def translate(
        self,
        component: Component,
        service: ServiceConfig,
        normalizer: Normalizer | None,
        annotations: list[EntityAnnotation] | None = None,
    ) -> MachineSubquery | None: ...


translator_registry: Registry[Translator] = Registry("translator")


def get_translator(name: str = "tool", **kwargs) -> Translator:
    return translator_registry.create(name, **kwargs)


# Open fields searched as free-text substrings rather than exact values.
_REGEX_OPEN_FIELDS = {"studyGroup", "age"}

# Minimum fuzzy score for a *non-exact* match to be trusted enough to anchor a
# MedDRA family rollup. Legitimate anchors land exact/near-exact (>=98); spurious
# shared-word matches (e.g. result-qualifier phrases like 'positive Ames Test') sit
# in the mid-80s. Below this, we prefer the LLM map (which re-grounds) or leave the
# term unmatched rather than expanding an unrelated family.
_ROLLUP_ANCHOR_MIN_SCORE = 95.0

# Result/polarity qualifier words that name an *outcome*, not the assay/finding the
# effects vocabulary is keyed on. They are high-frequency tokens shared by hundreds
# of entries, so they hijack a whole-phrase fuzzy match ('positive Ames Test' ranks
# 'Amniotic membrane rupture test positive' top). Stripping them before grounding
# keys on the assay/finding name ('Ames Test' -> the Ames assay family). General —
# not tied to any one phrase.
_RESULT_QUALIFIERS = re.compile(
    r"\b(positive|negative|abnormal|normal|elevated|increased|decreased|raised|reduced|low|high)\b",
    re.IGNORECASE,
)


def _strip_result_qualifiers(text: str) -> str:
    """Drop leading/standalone result-polarity words; collapse leftover whitespace."""
    return re.sub(r"\s+", " ", _RESULT_QUALIFIERS.sub("", text)).strip()


# Relational connectives the decomposer copies into a free-text fragment from the
# query's glue ('...NOAEL related to maternal toxicity' -> fragment 'related to
# maternal toxicity'), but which are not part of the searchable comment/value. A
# free-text field matches on the substantive phrase, so strip a leading connective.
# General over open free-text fields — not tied to any one comment.
_LEADING_CONNECTIVE = re.compile(
    r"^(?:related to|associated with|due to|caused by|regarding|concerning|relating to|about|for|on|of|in)\s+",
    re.IGNORECASE,
)


def _strip_leading_connective(text: str) -> str:
    """Drop a single leading relational connective from a free-text fragment."""
    return _LEADING_CONNECTIVE.sub("", text.strip(), count=1).strip()


# Acceptance score for a *qualifier-stripped* fuzzy anchor. Lower than the general
# rollup gate: the strip already removed the noise tokens, so a strong stem match
# (an assay/finding name) reliably lands ~80-90 and is trustworthy here.
_ROLLUP_QUALIFIER_MIN_SCORE = 80.0

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


def translate_input_filter(
    component: Component,
    service: ServiceConfig,
    normalizer=None,
    annotations: list[EntityAnnotation] | None = None,
) -> MachineSubquery | None:
    """Stage 2A public entry point: translate a closed-set input filter component."""
    from oppp.normalize.base import get_normalizer as _get_norm

    return translate_component(
        component,
        service,
        normalizer or _get_norm("noop"),
        llm_select=True,
        annotations=annotations,
    )


def translate_runtime_filter(
    component: Component,
    service: ServiceConfig,
    runtime_values: list[str],
) -> MachineSubquery | None:
    """Stage 2B public entry point: translate a runtime closed-set component.

    `runtime_values` is the sorted unique non-empty value list from fetched
    datapoints (the RuntimeClosedSet). The component is grounded against this
    list rather than the full taxonomy CSV.
    """
    if component.type is ComponentType.QUESTION:
        return None
    frag = component.nl_fragment.strip().lower()
    matched = [v for v in runtime_values if v.lower() == frag]
    if not matched:
        matched = [v for v in runtime_values if frag in v.lower() or v.lower() in frag]
    value = matched[0] if len(matched) == 1 else (matched if matched else frag)
    return MachineSubquery(
        field=component.field,
        operator=Operator.MATCH,
        value=value,
        boolean_group=component.boolean_group,
        notes="runtime closed-set translation" if matched else "no runtime match; raw fragment",
    )


def translate_one(
    component: Component,
    service: str = "pk",
    normalizer: str = "noop",
    *,
    llm_select: bool = False,
    annotations: list[EntityAnnotation] | None = None,
) -> MachineSubquery | None:
    """Convenience wrapper resolving service + normalizer by name.

    Defaults to deterministic (no LLM selection) so isolated translation in tests
    and the `field` CLI is hermetic; pass llm_select=True to exercise the selector.
    """
    return translate_component(
        component,
        get_service(service),
        get_normalizer(normalizer),
        llm_select=llm_select,
        annotations=annotations,
    )


def translate_component(
    component: Component,
    service: ServiceConfig,
    normalizer: Normalizer | None = None,
    *,
    llm_select: bool = True,
    annotations: list[EntityAnnotation] | None = None,
) -> MachineSubquery | None:
    """Translate a single FILTER component. Returns None for QUESTION components.

    `llm_select` toggles the optional LLM term selector for closed-vocab fields;
    set it False for a fully offline/deterministic translation (tests, eval).
    `annotations` are the Stage-0 enhancer recognitions (e.g. TERMite preferred
    labels); when present, a closed-vocab field grounds its matching annotation
    label first (the highest-precision resolution path).
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
        return _translate_closed(
            component, spec, service, normalizer, llm_select=llm_select, annotations=annotations
        )
    if spec.bucket == "boolean":
        return _translate_boolean(component, spec)
    if spec.bucket == "enum":
        return _translate_enum(component, spec)
    return _translate_open(component, spec, service, annotations)


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

    def translate(self, component, service, normalizer=None, annotations=None):
        return translate_component(
            component,
            service,
            normalizer,
            llm_select=self.llm_select,
            annotations=annotations,
        )


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


def _reground_proposals(
    proposals: list[str],
    index,
    *,
    limit: int,
    accept_score: float,
    seen: set[str],
    hits: list[GroundingHit],
) -> bool:
    """Re-ground each LLM proposal against the CSV (exact first, then fuzzy).

    Appends accepted hits to ``hits`` (deduped via ``seen``). A named real entity (a
    member drug, a canonical synonym) must bind to its *own* row, so we try exact
    before fuzzy; fuzzy then absorbs spelling / word-order drift in the proposal. An
    ungroundable proposal (a hallucination) is silently skipped — the emitted value
    therefore stays a subset of the closed set (CONST-1). Returns True once ``limit``
    is reached so the caller can stop early.
    """
    for proposal in proposals:
        match = index.lookup(proposal, match="exact", limit=1)
        if not match:
            match = index.lookup(proposal, match="fuzzy", limit=1)
        if match and match[0].score >= accept_score and match[0].name.lower() not in seen:
            hit = match[0]
            hit.match = "llm"  # provenance: reached via LLM mapping
            seen.add(hit.name.lower())
            hits.append(hit)
        if len(hits) >= limit:
            return True
    return False


def _alias_block(aliases: list[str] | None) -> str:
    """Render the extra pool phrasings (e.g. TERMite synonyms) for an LLM prompt."""
    extra = [a for a in (aliases or []) if a]
    if not extra:
        return ""
    listed = ", ".join(repr(a) for a in extra)
    return f"Also known as (equivalent phrasings for the same concept): {listed}\n"


def _llm_map_synonym(
    fragment: str,
    field: str,
    index,
    *,
    limit: int,
    accept_score: float,
    attempts: int,
    aliases: list[str] | None = None,
) -> list[GroundingHit]:
    """Stage-A fallback: the LLM names canonical term(s); we re-ground them.

    The phrase is a synonym / scientific name / brand / abbreviation, or a class/group
    whose *members* are vocabulary rows even though the group name is not (``'homo
    sapiens' -> 'Human'``, ``'Columvi' -> 'Glofitamab'``, ``'ADC' -> the member
    drugs``). The model points at the real entities from its own pharmacology
    knowledge; each proposal is re-grounded against the CSV so the result is always a
    subset of the closed set. This is the original mapping design — cheap (no vocab
    rows in the prompt) and right for the synonym/abbreviation/class-member shapes.

    ``aliases`` are the other members of the search pool (e.g. the TERMite synonym
    labels) — shown to the model as equivalent phrasings so the whole pool, not just
    the bare fragment, drives the mapping.
    """
    selector = _get_term_selector()
    if selector is None:
        return []
    prompt = (
        "You map a user's phrase to a controlled pharmacology vocabulary for the "
        f"field {field!r}. The phrase did NOT match the vocabulary by exact or fuzzy "
        "string match.\n"
        f"User phrase: {fragment!r}\n"
        f"{_alias_block(aliases)}"
        "Two cases:\n"
        "1. The phrase is a synonym / scientific name / brand / abbreviation of ONE "
        "standard term -> return that canonical term (e.g. 'homo sapiens' -> 'Human'; "
        "'Columvi' -> 'Glofitamab'; 'per os' -> 'Oral'; 'IV administration' -> "
        "'intravenous').\n"
        "2. The phrase names a CLASS or GROUP whose members are listed individually in "
        "the vocabulary but the group itself is not (e.g. 'ADC' / 'antibody-drug "
        "conjugates' -> the specific ADC drugs like 'Brentuximab Vedotin', "
        "'Trastuzumab Deruxtecan', 'Gemtuzumab Ozogamicin', …) -> return the SPECIFIC "
        "member entries you are confident belong to the group.\n"
        "Return the standard preferred name(s) of the matching vocabulary entries. Use "
        "real, specific entity names — never the group/abbreviation itself."
    )
    hits: list[GroundingHit] = []
    seen: set[str] = set()
    for attempt in range(max(1, attempts)):
        try:
            result: TermSelection = selector.invoke(prompt)  # type: ignore[assignment]
        except Exception:  # pragma: no cover - network/credential failure -> fallback
            break
        if _reground_proposals(
            result.selected, index, limit=limit, accept_score=accept_score, seen=seen, hits=hits
        ):
            return hits
        # One confirming pass once we have something: guards a lucky first hit, and
        # lets a flaky empty first attempt recover on the next.
        if hits and attempt >= 1:
            break
    return hits


def _llm_search_closed_set(
    fragment: str,
    field: str,
    index,
    *,
    limit: int,
    accept_score: float,
    aliases: list[str] | None = None,
) -> list[GroundingHit]:
    """Stage-B fallback: show the LLM the closed-set rows and let it pick the matches.

    Used only when Stage A (synonym mapping from the model's own knowledge) grounds
    nothing — the phrase is not a synonym/class the model can name blind, but the right
    rows *do* exist in the vocabulary under a wording the string matcher can't reach
    ('Ames Test' -> the four 'Mutagenic: Bacterial reverse mutation assay (Ames test)'
    rows). We hand the model a focused **window of actual closed-set rows**
    (:meth:`TaxonomyIndex.candidate_window`) and ask it to pick the entries that match,
    by exact CSV spelling. Each pick is still re-grounded (so a paraphrase the model
    typed instead of copying still binds, and anything off-list is dropped) — the value
    stays a subset of the closed set. This is the user's "pass the rows to the LLM and
    let it find the match" path, realised as a candidate window for large vocabularies.

    ``aliases`` (the other pool phrasings, e.g. TERMite synonyms) both widen the
    candidate window — each alias contributes its own related rows — and are shown to
    the model as equivalent phrasings, so the whole pool drives the search.
    """
    selector = _get_term_selector()
    if selector is None:
        return []
    window: list[str] = []
    seen_win: set[str] = set()
    for phrase in (fragment, *(aliases or [])):
        if not phrase:
            continue
        for row in index.candidate_window(phrase):
            if row.lower() not in seen_win:
                seen_win.add(row.lower())
                window.append(row)
    if not window:
        return []
    options = "\n".join(f"- {c}" for c in window)
    prompt = (
        "You ground a user's phrase to a controlled pharmacology vocabulary for the "
        f"field {field!r}. Exact and fuzzy string match failed, so here are the actual "
        "vocabulary rows that look related — choose the ones that genuinely match the "
        "phrase's meaning.\n"
        f"User phrase: {fragment!r}\n"
        f"{_alias_block(aliases)}"
        "Vocabulary rows (choose only from these, using their exact spelling):\n"
        f"{options}\n\n"
        "Return every row that matches the user's phrase (there may be several — e.g. an "
        "assay with 'with S9' / 'without S9' variants — or just one). Return nothing if "
        "none genuinely match. Use the exact row spellings above."
    )
    hits: list[GroundingHit] = []
    seen: set[str] = set()
    try:
        result: TermSelection = selector.invoke(prompt)  # type: ignore[assignment]
    except Exception:  # pragma: no cover - network/credential failure -> fallback
        return []
    _reground_proposals(
        result.selected, index, limit=limit, accept_score=accept_score, seen=seen, hits=hits
    )
    return hits


def _llm_map_to_vocab(
    fragment: str,
    field: str,
    index,
    *,
    limit: int = 40,
    accept_score: float = 90.0,
    attempts: int = 3,
    aliases: list[str] | None = None,
) -> list[GroundingHit]:
    """Closed-vocab LLM fallback when exact/fuzzy lookup finds nothing.

    Two stages, in order (per the user's design):

    1. **Synonym map** (:func:`_llm_map_synonym`) — the model names the canonical
       term(s) or class members from its own knowledge; cheap, no vocab in the prompt.
       Right for synonyms/abbreviations/brands and class-member groups
       ('ADC' -> the member drugs, 'homo sapiens' -> 'Human').
    2. **Closed-set search** (:func:`_llm_search_closed_set`) — *only if* Stage 1
       grounds nothing: hand the model a window of the actual closed-set rows and let
       it pick the matches ('Ames Test' -> the four bacterial-reverse-mutation rows,
       which exist in-vocab under a wording neither fuzzy nor a blind synonym guess
       reaches).

    Both stages re-ground every proposal against the CSV, so the emitted value is
    **always a subset of the closed set** (CONST-1); ungroundable picks are dropped and
    an all-empty result drops the filter rather than inventing a value. ``limit`` caps
    the kept rows below the API's ~49-value-per-MATCH-list ceiling.

    ``aliases`` are the other members of the search pool (the TERMite synonym labels):
    when the whole pool failed exact/fuzzy grounding, both LLM stages see every pool
    phrasing, not just the bare fragment, so a synonym the model recognises can still
    resolve the term.
    """
    hits = _llm_map_synonym(
        fragment,
        field,
        index,
        limit=limit,
        accept_score=accept_score,
        attempts=attempts,
        aliases=aliases,
    )
    if hits:
        return hits
    return _llm_search_closed_set(
        fragment, field, index, limit=limit, accept_score=accept_score, aliases=aliases
    )


# ---------------------------------------------------------------------------
def _surfaces_overlap(ann, fragment: str) -> bool:
    """Textual correspondence: annotation surface/label overlaps the fragment."""
    frag = fragment.strip().lower()
    if not frag:
        return False
    frag_forms = {frag, *(x.lower() for x in singular_candidates(frag))}
    for s in (ann.surface, ann.label):
        s = (s or "").strip().lower()
        if not s:
            continue
        s_forms = {s, *(x.lower() for x in singular_candidates(s))}
        if frag_forms & s_forms:
            return True
        if any(sf and (sf in frag or frag in sf) for sf in s_forms):
            return True
    return False


def _annotation_corresponds(ann, fragment: str, index) -> bool:
    """Does this annotation describe *this* component's fragment (not just its field)?

    A query can carry several values of one field ('rats or mice', 'neutropenia or
    thrombocytopenia') -> several same-typed annotations and several same-field
    components. Binding by *type* alone would collapse every value onto the first
    annotation of that type ('Rat' and 'mice' both -> the lone 'Mouse' annotation).

    Two complementary signals make this robust to both abbreviations and multi-value
    fields:

    * **Textual overlap** — surface/label shares words with the fragment (handles the
      common case and qualifier-dropping: 'inhibitors of kinases' ~ surface 'kinases').
    * **No grounding conflict** — the annotation still binds when surfaces *differ*
      (e.g. fragment 'No Observed Adverse Effect Level' vs label 'NOAEL'), UNLESS the
      fragment *itself* strongly grounds (exact / high fuzzy) to a *different* vocab
      entry than the annotation's label. That conflict is exactly the multi-value
      case: 'Rat' grounds to 'Rat' (100) while the annotation label is 'Mouse', so the
      annotation is rejected and 'Rat' grounds itself. When the fragment has no strong
      self-grounding (the abbreviation/expansion case), there is nothing to displace,
      so the annotation's verified label wins.
    """
    if _surfaces_overlap(ann, fragment):
        return True
    # Surfaces differ: bind unless the fragment self-grounds to a *different* term.
    label = (ann.label or "").strip().lower()
    own = index.lookup(fragment, match="exact", limit=1)
    if not own:
        fuzzy = index.lookup(fragment, match="fuzzy", limit=1)
        own = fuzzy if (fuzzy and fuzzy[0].score >= _ROLLUP_ANCHOR_MIN_SCORE) else []
    # Reject only when the fragment has its own strong, *conflicting* self-grounding.
    return not (own and own[0].name.strip().lower() != label)


def _annotation_hits(component, spec, service, index, annotations) -> list[GroundingHit]:
    """Resolution-order step 1: ground the Stage-0 enhancer's preferred label + synonyms.

    If an enhancer (e.g. TERMite) recognized one or more entities whose type maps to
    this component's field, its preferred label is usually already a controlled-vocab
    term ('No Observed Adverse Effect Level' -> 'NOAEL'). TERMite also returns the
    entity's full equivalent-term set (``publicSynonyms``: brand/scientific/abbrev/
    spelling variants) inside the *same* annotation, so we take the **entire set** into
    account, not just the label: ``[label, *synonyms]`` is one search pool, each member
    *verified* against the field's CSV (exact, incl. singular forms), and every verified
    hit is unioned. A synonym that *is* a vocab term still lands even when the preferred
    label is not. This is the highest-precision path, ahead of fuzzy/LLM on the raw
    fragment; the preferred label ranks first so it leads the value list.

    Each annotation must *correspond to this component's fragment*, not merely share
    its field — otherwise a multi-value field ('rats or mice') would bind every
    value to the first same-typed annotation, silently duplicating one and dropping
    the others. We therefore match on surface/label correspondence
    (:func:`_annotation_corresponds`).

    Returns the deduped list of verified GroundingHits (empty when no corresponding
    annotation, the type map has no entry for the field, or nothing in the set is in the
    vocabulary — so we never emit the enhancer's raw string, CONST-1). The caller folds
    these into a single candidate pool together with the normalized term and falls
    through to fragment-based fuzzy/LLM grounding when the pool is otherwise empty.
    """
    if not annotations:
        return []
    # entity_type (e.g. 'TOXICITY_PARAMETER') -> field name (e.g. 'toxicityParameter')
    type_map = service.termite_type_map
    hits: list[GroundingHit] = []
    seen: set[str] = set()
    for ann in annotations:
        if not ann.entity_type:
            continue
        if type_map.get(ann.entity_type) != component.field:
            continue
        if not _annotation_corresponds(ann, component.nl_fragment, index):
            continue
        # Ground the whole equivalent-term set: preferred label first (so it leads the
        # value list), then each synonym. Every member is verified against the taxonomy;
        # verified hits are unioned and deduped across all corresponding annotations.
        #
        # A member resolves one of two ways:
        #   * exact CSV leaf — the row itself ('NOAEL', 'Mouse').
        #   * class label — a parent node with no own row ('Rodent', 'Kinase
        #     inhibitors'). TERMite hands back the *group* preferred label, which the API
        #     resolves server-side to the whole member set; emitting the single class
        #     label (not its inlined children) is both correct and stays under the API's
        #     ~49-value cap. Without this, a group annotation whose label is parent-only
        #     fails the exact lookup and the high-precision path is silently lost
        #     ('Rodent' -> mis-grounds to the 'Rodent (unspecified)' leaf).
        for term in (ann.label, *ann.synonyms):
            if not term:
                continue
            exact = index.lookup(term, match="exact", limit=1)
            if exact:
                hit = exact[0]
                hit.match = "termite"  # provenance: reached via the enhancer's set
            else:
                class_label = index.class_label(term)
                if class_label is None:
                    continue
                hit = index.class_hit(class_label)  # match="class"; API expands it
            if hit.name.lower() in seen:
                continue
            seen.add(hit.name.lower())
            hits.append(hit)
    return hits


def _annotation_aliases(component, service, index, annotations) -> list[str]:
    """Raw equivalent-term surfaces (label + synonyms) from corresponding annotations.

    Unlike :func:`_annotation_hits` these are *not* CSV-verified — they are the
    enhancer's phrasings (brand/scientific/abbrev) to feed the LLM fallback when nothing
    in the pool grounds by string match, so the model sees every way the entity was named
    rather than the bare fragment. Field/correspondence gated exactly like the hits.
    """
    if not annotations:
        return []
    type_map = service.termite_type_map
    out: list[str] = []
    seen: set[str] = set()
    for ann in annotations:
        if not ann.entity_type or type_map.get(ann.entity_type) != component.field:
            continue
        if not _annotation_corresponds(ann, component.nl_fragment, index):
            continue
        for term in (ann.label, *ann.synonyms):
            term = (term or "").strip()
            if term and term.lower() not in seen:
                seen.add(term.lower())
                out.append(term)
    return out


def _translate_closed(
    component, spec, service, normalizer, *, llm_select=True, annotations=None
) -> MachineSubquery:
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

    # Resolution-order step 1: the Stage-0 enhancer's preferred label(s), verified
    # against the CSV. Highest precision — used when the field is not a class and
    # not a MedDRA-rollup field, so class expansion / family rollup still win when
    # the user named one of those (those branches key off the raw term). TERMite may
    # offer several synonyms for one span, so this is the *whole verified set*, not a
    # single hit; the normalized term itself is always also a candidate in the pool
    # below, whether or not annotations exist.
    ann_hits = _annotation_hits(component, spec, service, index, annotations)

    expanded_from = None
    canonical = term
    class_label = index.class_label(term) if not ann_hits else None
    if class_label is not None:
        # The term names a taxonomy class (drug class 'Kinase inhibitors', a species
        # class, an indication that is also a parent node). The API resolves a class
        # *label* server-side to its whole member set, so emit the single label rather
        # than inlining every child: inlining busts the API's ~49-value per-MATCH-list
        # cap (HTTP 400) for large classes (monoclonal antibodies has 100+ members)
        # and is redundant (the parent already matches its subtree). We record the
        # expanded children in the grounding for provenance only.
        hits = [index.class_hit(class_label)]
        canonical = class_label
        expanded_from = "class"
    elif spec.rollup_to_siblings:
        # Resolve to a canonical anchor, then roll up to its MedDRA family — but only
        # on a *high-confidence* anchor. A weak fuzzy hit (e.g. 'positive Ames Test'
        # ~ 'Amniotic membrane rupture test positive' @86, 'maternal toxicity' ~
        # 'Chemotherapy toxicity attenuation' @86) would otherwise drive a rollup into
        # an unrelated family. Below threshold we ask the LLM to map the phrase to a
        # real term instead (which re-grounds exactly), and if that fails we leave it
        # unmatched rather than inventing a family.
        anchor_is_exact = False
        llm_direct: list[GroundingHit] = []
        if ann_hits:
            # Every verified annotation label (TERMite synonym set) anchors a rollup.
            base = ann_hits
            anchor_is_exact = True
        else:
            base = index.lookup(term, match="exact", limit=1)
            anchor_is_exact = bool(base)
            if not base:
                fuzzy = index.lookup(term, match="fuzzy", limit=1)
                if fuzzy and fuzzy[0].score >= _ROLLUP_ANCHOR_MIN_SCORE:
                    base = fuzzy
                else:
                    # Result/assay phrase? Drop polarity words and re-ground on the
                    # assay/finding name ('positive Ames Test' -> 'Ames Test'). Only
                    # used when stripping actually changed the phrase, so plain terms
                    # are unaffected.
                    stripped = _strip_result_qualifiers(term)
                    if stripped and stripped.lower() != term.lower():
                        sfuzzy = index.lookup(stripped, match="fuzzy", limit=1)
                        if sfuzzy and sfuzzy[0].score >= _ROLLUP_QUALIFIER_MIN_SCORE:
                            base = sfuzzy
                    if not base and llm_select:
                        # Let the LLM resolve it (synonym map, then closed-set search).
                        # When it returns *several specific rows* (e.g. 'Ames Test' ->
                        # the four bacterial-reverse-mutation entries it picked from the
                        # vocabulary window), those ARE the answer — use them directly
                        # rather than collapsing onto the first and re-expanding a
                        # family, which would either lose the others or pull in unrelated
                        # siblings. A single LLM hit still feeds the normal rollup below.
                        llm_direct = _llm_map_to_vocab(frag, component.field, index)
                        if len(llm_direct) > 1:
                            hits = llm_direct
                            canonical = llm_direct[0].name
                            expanded_from = "llm"
                        elif llm_direct:
                            base = llm_direct[:1]
        if expanded_from == "llm":
            pass  # hits already the LLM-selected rows; skip family rollup
        elif base:
            # Additive rollup over the *whole* anchor set: each base hit (the term and
            # any TERMite synonyms) keeps itself alongside its MedDRA family, all unioned
            # so we never lose a grounded term, only add recall. The canonical/collapse
            # term is the first anchor.
            canonical = base[0].name
            names: dict[str, GroundingHit] = {}
            any_family = False
            any_class = False
            for anchor in base:
                names.setdefault(anchor.name, anchor)
                if anchor.match == "class":
                    # A class anchor (e.g. a group annotation label) is expanded
                    # server-side from the single label — never inline its children
                    # (that busts the API's ~49-value cap) and never family-roll it.
                    any_class = True
                    continue
                family = index.expand_family(anchor.name)
                if family:
                    any_family = True
                    for h in family:
                        names.setdefault(h.name, h)
            hits = list(names.values())
            expanded_from = "family" if any_family else ("class" if any_class else None)
        else:
            hits = []
        # When the anchor was *guessed* (fuzzy/LLM, not an exact CSV hit), the user's
        # original phrase may itself be a broad category the API resolves server-side
        # even though our local CSV has no such leaf ('Mutagenicity' -> 445 at the API,
        # while the nearest local leaf 'Mutagenic effect' + its NEC family -> 30, and
        # the LLM-picked assay rows are a different, narrower slice). Additively OR the
        # original fragment back in — preserving the user's casing, since the effects
        # field is case-sensitive at the API ('Mutagenicity' matches, 'mutagenicity'
        # does not). Values are OR'd, so a fragment the API doesn't recognise is a
        # harmless no-op; one it does recognise restores the broad reading.
        if hits and not anchor_is_exact and not ann_hits:
            have = {h.name.lower() for h in hits}
            # The effects field is case-sensitive at the API ('Mutagenicity' matches,
            # 'mutagenicity' does not), and upstream stages may have lowercased the
            # fragment. Offer both the fragment as written and a capitalized variant of a
            # single-word concept; the API resolves whichever it recognises and ignores
            # the rest (values are OR'd, so the extras are harmless no-ops).
            for cand in (frag, frag[:1].upper() + frag[1:] if frag and " " not in frag else frag):
                if cand.lower() not in have:
                    have.add(cand.lower())
                    hits = [*hits, GroundingHit(name=cand, match="llm", score=100.0)]
    else:
        # Search a POOL of terms and UNION every grounded hit. The pool is always the
        # normalized term plus any verified TERMite synonyms (ann_hits) — the normalized
        # term is a candidate whether or not annotations exist. Each pool member is
        # grounded exact -> close (fuzzy); the annotation labels are already CSV-verified
        # (they ground exact and rank first), and the term resolves on its own.
        #
        # Only when the ENTIRE pool grounds to nothing do the LLM fallbacks run, and they
        # see the whole pool (fragment + synonym aliases) so any phrasing the model
        # recognises can resolve the term: the synonym map ('homo sapiens' -> 'Human'),
        # then the closed-set search over a candidate window unioned across the pool.
        # Each LLM pick is re-grounded so the value stays in-vocabulary (CONST-1).
        # Offline (llm_select=False) the LLM path yields nothing and the gap is flagged
        # below rather than invented.
        # Raw equivalent-term phrasings (label + synonyms, NOT CSV-verified) for the LLM
        # fallback: when nothing in the pool grounds by string match, the model still
        # sees every way the entity was named (brand/scientific/abbrev), not just the
        # bare fragment. Includes phrasings even when no synonym was a vocab term.
        aliases = _annotation_aliases(component, service, index, annotations)
        pool: list[GroundingHit] = list(ann_hits)
        if ann_hits:
            # TERMite already resolved the concept; the term contributes only its EXACT
            # self-grounding so a raw multi-word fragment ('rat and mouse models') can't
            # drag unrelated fuzzy rows ('Deer mouse', 'Grass rat') into the union, while
            # an in-vocab term the enhancer missed is still never lost.
            pool.extend(index.lookup(term, match="exact", limit=1))
        else:
            candidates = index.lookup(term, match="fuzzy", limit=8)
            if candidates:
                chosen = (
                    _llm_select(frag, component.field, [h.name for h in candidates])
                    if llm_select
                    else None
                )
                if chosen:
                    chosen_set = {c.lower() for c in chosen}
                    pool.extend(h for h in candidates if h.name.lower() in chosen_set)
                else:
                    pool.extend(candidates[:5])
        # Dedup the unioned pool, keeping first occurrence (annotation hits rank first).
        seen_pool: set[str] = set()
        hits = []
        for h in pool:
            if h.name.lower() in seen_pool:
                continue
            seen_pool.add(h.name.lower())
            hits.append(h)
        # A class-label annotation hit ('Rodent', 'Kinase inhibitors') is expanded by the
        # API from the single label; record the provenance so the grounding reflects it.
        if any(h.match == "class" for h in hits):
            expanded_from = "class"
        # Whole pool grounded to nothing -> LLM fallbacks over the entire pool.
        if not hits and llm_select:
            hits = _llm_map_to_vocab(frag, component.field, index, aliases=aliases)

    if hits:
        values = [h.name for h in hits]
        grounding = Grounding(
            matched=hits[:25],
            expanded_from=expanded_from,
            confidence=min(1.0, (hits[0].score / 100.0)),
        )
    else:
        # Nothing grounded — not even via fuzzy or the LLM map. Emitting the raw
        # out-of-vocabulary phrase as a hard MATCH would silently zero the whole
        # query (an AND with a value that exists in no record). CONST-1: never emit
        # an invented value. Mark the subquery dropped so Stage 3 excludes it from
        # the query entirely (and the gap is recorded as an issue), leaving the
        # valid superset rather than a guaranteed-empty result.
        return MachineSubquery(
            field=spec.emit_field,
            operator=Operator.MATCH,
            value=term,
            boolean_group=component.boolean_group,
            entity_name=spec.entity_name,
            grounding=Grounding(
                matched=[GroundingHit(name=term, match="unmatched", score=0.0)],
                confidence=0.0,
            ),
            notes=f"ungroundable closed-vocab term {term!r}; dropped to avoid zeroing the query",
            dropped=True,
        )

    # Drug-style fuzzy broadening: trailing wildcard on a single leaf term. The API
    # rejects (HTTP 400) a bare trailing '*' on a multi-word value ('Cytotoxic drugs*',
    # 'Monoclonal antibodies*'), so only broaden single-token values; a multi-word
    # value is emitted as-is.
    if spec.fuzzy_wildcard and expanded_from is None and len(values) == 1 and " " not in values[0]:
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
    # The decomposer copies the user's surface words, so a boolean field arrives as a
    # phrase, not a literal 'true'. Treat an explicit truthy token OR a preclinical /
    # non-clinical phrasing ('non clinical species', 'preclinical', 'non-clinical') as
    # True; anything else (incl. an explicit negation) as False. Matching on the concept
    # keeps this general over how the user phrases the same boolean intent.
    frag = str(component.nl_fragment).strip().lower()
    val = frag in ("true", "yes", "1") or bool(
        re.search(r"\b(pre[- ]?clinical|non[- ]?clinical)\b", frag)
    )
    return MachineSubquery(field=spec.emit_field, operator=Operator.MATCH, value=val)


def _translate_enum(component, spec) -> MachineSubquery:
    frag = component.nl_fragment.strip().lower()
    # Exact match first; then accept an enum value appearing as a standalone word in
    # the fragment ('male subjects' / 'in males' -> 'Male'). The decomposer copies the
    # user's surface words, so a small qualifier ('subjects', plural) must not drop the
    # match. Longest enum value first so a more specific option wins over a substring.
    for allowed in sorted(spec.enum_values, key=len, reverse=True):
        low = allowed.lower()
        if low == frag or re.search(rf"\b{re.escape(low)}s?\b", frag):
            return MachineSubquery(field=spec.emit_field, operator=Operator.MATCH, value=allowed)
    return MachineSubquery(
        field=spec.emit_field,
        operator=Operator.MATCH,
        value=component.nl_fragment,
        notes="value not in enum allow-list",
    )


def _translate_open(component, spec, service=None, annotations=None) -> MachineSubquery:
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

    # Entity-routed open fields (e.g. targets -> DrugsTargets) are matched by the
    # back-end against the enhancer's *preferred label*, not the user's free phrase:
    # the DrugsTargets filter accepts 'Kinases' (the TERMite label) but returns
    # nothing for the raw 'inhibitors of kinases'. So when an enhancer annotation of
    # the matching type exists for this field, emit its label. There is no taxonomy
    # to verify against for an open field, but the label is exactly the API's
    # vocabulary — the same "use the enhancer's preferred label" principle applied to
    # closed fields. No annotation -> pass the fragment through as before.
    # Plain free-text field (e.g. parameterComment): the API matches the substantive
    # phrase, so drop a leading relational connective the decomposer copied from the
    # query ('related to maternal toxicity' -> 'maternal toxicity'). Entity-routed open
    # fields keep the full fragment (their label is resolved below).
    value = frag
    note = None
    if not spec.entity_name:
        stripped = _strip_leading_connective(frag)
        if stripped and stripped != frag:
            value = stripped
            note = f"{frag!r} -> {value!r} (stripped leading connective)"
    if spec.entity_name and service is not None and annotations:
        type_map = service.termite_type_map
        # TERMite may offer several synonyms for one span; take the entire matching set
        # (deduped), OR'd, rather than only the first. There is no vocabulary to ground
        # against for an open field, so textual overlap selects the relevant labels.
        labels: list[str] = []
        seen: set[str] = set()
        for ann in annotations:
            if (
                ann.entity_type
                and type_map.get(ann.entity_type) == component.field
                and ann.label
                and _surfaces_overlap(ann, frag)
            ):
                lab = ann.label.strip()
                if lab and lab.lower() not in seen:
                    seen.add(lab.lower())
                    labels.append(lab)
        if labels:
            value = labels[0] if len(labels) == 1 else labels
            if seen != {frag.lower()}:
                note = f"{frag!r} -> {value!r} (enhancer preferred label for {spec.entity_name})"

    return MachineSubquery(
        field=spec.emit_field,
        operator=Operator.MATCH,
        value=value,
        boolean_group=component.boolean_group,
        entity_name=spec.entity_name,
        notes=note,
    )
