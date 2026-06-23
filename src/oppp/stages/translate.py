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
_REGEX_OPEN_FIELDS = {"studyGroup", "ages"}

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


def translate_one(
    component: Component,
    service: str = "safety",
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


def _llm_map_synonym(
    fragment: str,
    field: str,
    index,
    *,
    limit: int,
    accept_score: float,
    attempts: int,
) -> list[GroundingHit]:
    """Stage-A fallback: the LLM names canonical term(s); we re-ground them.

    The phrase is a synonym / scientific name / brand / abbreviation, or a class/group
    whose *members* are vocabulary rows even though the group name is not (``'homo
    sapiens' -> 'Human'``, ``'Columvi' -> 'Glofitamab'``, ``'ADC' -> the member
    drugs``). The model points at the real entities from its own pharmacology
    knowledge; each proposal is re-grounded against the CSV so the result is always a
    subset of the closed set. This is the original mapping design — cheap (no vocab
    rows in the prompt) and right for the synonym/abbreviation/class-member shapes.
    """
    selector = _get_term_selector()
    if selector is None:
        return []
    prompt = (
        "You map a user's phrase to a controlled pharmacology vocabulary for the "
        f"field {field!r}. The phrase did NOT match the vocabulary by exact or fuzzy "
        "string match.\n"
        f"User phrase: {fragment!r}\n"
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
    """
    selector = _get_term_selector()
    if selector is None:
        return []
    window = index.candidate_window(fragment)
    if not window:
        return []
    options = "\n".join(f"- {c}" for c in window)
    prompt = (
        "You ground a user's phrase to a controlled pharmacology vocabulary for the "
        f"field {field!r}. Exact and fuzzy string match failed, so here are the actual "
        "vocabulary rows that look related — choose the ones that genuinely match the "
        "phrase's meaning.\n"
        f"User phrase: {fragment!r}\n"
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
    """
    hits = _llm_map_synonym(
        fragment, field, index, limit=limit, accept_score=accept_score, attempts=attempts
    )
    if hits:
        return hits
    return _llm_search_closed_set(
        fragment, field, index, limit=limit, accept_score=accept_score
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


def _annotation_hit(component, spec, service, index, annotations) -> GroundingHit | None:
    """Resolution-order step 1: ground the Stage-0 enhancer's preferred label.

    If an enhancer (e.g. TERMite) recognized an entity whose type maps to this
    component's field, its preferred label is usually already a controlled-vocab
    term ('No Observed Adverse Effect Level' -> 'NOAEL'). We *verify* that label
    exists in the field's CSV (exact, incl. singular forms) and use that hit —
    the highest-precision path, ahead of fuzzy/LLM on the raw user fragment.

    The annotation must *correspond to this component's fragment*, not merely share
    its field — otherwise a multi-value field ('rats or mice') would bind every
    value to the first same-typed annotation, silently duplicating one and dropping
    the others. We therefore match on surface/label correspondence
    (:func:`_annotation_corresponds`).

    Returns the verified GroundingHit, or None when no corresponding annotation,
    the type map has no entry for the field, or the label is not in the vocabulary
    (so we never emit the enhancer's raw string — CONST-1) — in which case the
    caller falls through to fragment-based fuzzy/LLM grounding.
    """
    if not annotations:
        return None
    # entity_type (e.g. 'TOXICITY_PARAMETER') -> field name (e.g. 'toxicityParameter')
    type_map = service.termite_type_map
    for ann in annotations:
        if not ann.entity_type:
            continue
        if type_map.get(ann.entity_type) != component.field:
            continue
        if not _annotation_corresponds(ann, component.nl_fragment, index):
            continue
        hits = index.lookup(ann.label, match="exact", limit=1)
        if hits:
            hit = hits[0]
            hit.match = "termite"  # provenance: reached via the enhancer's label
            return hit
    return None


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

    # Resolution-order step 1: the Stage-0 enhancer's preferred label, verified
    # against the CSV. Highest precision — used when the field is not a class and
    # not a MedDRA-rollup field, so class expansion / family rollup still win when
    # the user named one of those (those branches key off the raw term).
    ann_hit = _annotation_hit(component, spec, service, index, annotations)

    expanded_from = None
    canonical = term
    class_label = index.class_label(term) if not ann_hit else None
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
        if ann_hit:
            base = [ann_hit]
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
            pass  # hits already set to the LLM-selected rows; skip family rollup
        elif base:
            canonical = base[0].name
            family = index.expand_family(canonical)
            if family:
                # Additive rollup: keep the canonical term itself alongside its family
                # so we never lose the broad/grounded term, only add recall.
                names = {canonical: base[0]}
                for h in family:
                    names.setdefault(h.name, h)
                # When the anchor was *guessed* (fuzzy/LLM, not an exact CSV hit), the
                # user's original phrase may be a broad category the API resolves
                # server-side even though it isn't a local leaf ('Mutagenicity' -> 445,
                # while the LLM's nearest leaf 'Mutagenic effect' + its NEC family -> 30).
                # Additively include the original term so the broad reading is kept;
                # values are OR'd, so a non-matching extra term is harmless.
                if not anchor_is_exact and term not in names:
                    names[term] = GroundingHit(name=term, match="llm", score=100.0)
                hits = list(names.values())
                expanded_from = "family"
            else:
                hits = base
        else:
            hits = []
    elif ann_hit:
        hits = [ann_hit]
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
        for ann in annotations:
            if (
                ann.entity_type
                and type_map.get(ann.entity_type) == component.field
                and ann.label
                # open field: no vocabulary to ground against, so use textual overlap
                and _surfaces_overlap(ann, frag)
            ):
                value = ann.label.strip()
                if value.lower() != frag.lower():
                    note = (
                        f"{frag!r} -> {value!r} (enhancer preferred label for {spec.entity_name})"
                    )
                break

    return MachineSubquery(
        field=spec.emit_field,
        operator=Operator.MATCH,
        value=value,
        boolean_group=component.boolean_group,
        entity_name=spec.entity_name,
        notes=note,
    )
