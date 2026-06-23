"""Per-stage isolation tests for the pluggable pipeline.

Each stage (enhance / decompose / translate / aggregate) is resolvable by name
and runnable on its own. These tests exercise the offline doubles only — the LLM
backends are smoke-tested separately and need creds.
"""

from oppp.models import (
    BooleanGroup,
    BooleanOp,
    Component,
    ComponentType,
    Decomposition,
)
from oppp.services.base import get_service
from oppp.stages.aggregate import aggregator_registry, get_aggregator
from oppp.stages.decompose import decomposer_registry, get_decomposer
from oppp.stages.enhance import enhancer_registry, get_enhancer
from oppp.stages.translate import get_translator, translate_one, translator_registry

SVC = get_service("safety")


def test_registries_expose_expected_backends():
    assert "noop" in enhancer_registry.names() and "termite" in enhancer_registry.names()
    assert "llm" in decomposer_registry.names() and "gazetteer" in decomposer_registry.names()
    assert "tool" in translator_registry.names()
    assert {"llm", "deterministic"} <= set(aggregator_registry.names())


def test_default_backends_match_intended_design():
    # LLM by default for decompose + aggregate; no-op enhancer; tool translator.
    assert type(get_enhancer()).__name__ == "NoopEnhancer"
    assert type(get_decomposer()).__name__ == "LLMDecomposer"
    assert type(get_translator()).__name__ == "ToolTranslator"
    assert type(get_aggregator()).__name__ == "LLMAggregator"


def test_enhance_noop_passes_through():
    e = get_enhancer("noop").enhance("ADRs of sunitinib", SVC)
    assert e.text == "ADRs of sunitinib"
    assert e.annotations == []
    assert e.source == "noop"


def test_expand_noop_passes_through():
    from oppp.stages.expand import get_expander

    x = get_expander("noop").expand("ADRs of ADC in male", SVC)
    assert x.text == "ADRs of ADC in male"
    assert x.original == "ADRs of ADC in male"
    assert x.source == "noop"


def test_expand_llm_rewrites_and_preserves_original():
    # Inject a fake structured model so the test is hermetic (no creds/network).
    from oppp.models import QueryExpansion
    from oppp.stages.expand import LLMExpander

    expander = LLMExpander()

    class _Fake:
        def invoke(self, _prompt):
            return QueryExpansion(
                expanded="What adverse drug reactions (ADRs) of the antibody-drug "
                "conjugate (ADC) occur in male subjects?",
                reason="expanded ADR/ADC",
            )

    expander._structured = _Fake()
    x = expander.expand("ADRs of ADC in male", SVC)
    assert "antibody-drug conjugate (ADC)" in x.text
    assert x.original == "ADRs of ADC in male"  # original preserved for the record
    assert x.source == "llm"


def test_expand_llm_falls_back_to_passthrough_when_unavailable(monkeypatch):
    # No creds / LLM build fails -> the stage is present but never fatal: pass through.
    import oppp.llm as llm_mod
    from oppp.stages.expand import LLMExpander

    def boom(*a, **k):
        raise llm_mod.LLMUnavailable("no creds")

    monkeypatch.setattr(llm_mod, "structured", boom)
    x = LLMExpander().expand("ADRs of ADC in male", SVC)
    assert x.text == "ADRs of ADC in male"  # unchanged
    assert x.original == "ADRs of ADC in male"
    assert x.source.startswith("noop")


def test_decompose_gazetteer_isolated():
    d = get_decomposer("gazetteer").decompose("ADRs of Sunitinib in human", SVC)
    fields = {c.field for c in d.filters}
    assert {"drugs", "species"} <= fields


def test_reconcile_mechanism_phrase_resolves_to_drug_class_when_one_exists():
    """'inhibitors of kinases' (+TARGET:Kinases) resolves to the drug class, not target.

    The phrase has two readings; the gold answer is the antineoplastic drug class
    'Kinase inhibitors' (a real class node), the tighter intended set (~1851), not
    the broader DrugsTargets=Kinases set (~6980). Reconciliation keeps it on `drugs`
    and rewrites the fragment to the class label. Regression for the case-8 over-broad
    target routing.
    """
    from oppp.models import Component, ComponentType, Decomposition, EntityAnnotation
    from oppp.stages.decompose import reconcile_with_annotations

    decomp = Decomposition(
        query="adverse events for inhibitors of kinases in human",
        service="safety",
        components=[
            Component(
                field="drugs",
                nl_fragment="inhibitors of kinases",
                type=ComponentType.FILTER,
                reason="x",
            ),
            Component(field="species", nl_fragment="human", type=ComponentType.FILTER, reason="x"),
        ],
    )
    anns = [EntityAnnotation(surface="Kinases", label="Kinases", entity_type="TARGET")]
    reconcile_with_annotations(decomp, SVC, anns)

    drug = next(c for c in decomp.filters if c.field == "drugs")
    assert drug.nl_fragment == "Kinase inhibitors"  # rewritten to the class label
    assert "drug-class" in drug.source
    assert {c.field for c in decomp.filters} == {"drugs", "species"}  # no targets reroute


def test_reconcile_routes_to_targets_when_no_matching_drug_class():
    """A TARGET phrase with no '<x> inhibitors' drug class falls back to `targets`.

    When the mechanism phrase does not name a drug class in the taxonomy, the target
    reading (DrugsTargets entity filter) is correct. Keeps the two readings distinct.
    """
    from oppp.models import Component, ComponentType, Decomposition, EntityAnnotation
    from oppp.stages.decompose import reconcile_with_annotations

    decomp = Decomposition(
        query="effects for inhibitors of zzznotadrugclass",
        service="safety",
        components=[
            Component(
                field="drugs",
                nl_fragment="inhibitors of zzznotadrugclass",
                type=ComponentType.FILTER,
                reason="x",
            ),
        ],
    )
    anns = [
        EntityAnnotation(surface="zzznotadrugclass", label="zzznotadrugclass", entity_type="TARGET")
    ]
    reconcile_with_annotations(decomp, SVC, anns)
    assert decomp.filters[0].field == "targets"


def test_reconcile_leaves_drug_inhibitor_without_target_annotation():
    """Without a TARGET annotation, 'CDk4 inhibitors' stays a drug filter.

    Gold row 21 ('CDk4 inhibitors') has no TERMite TARGET, so it must remain on
    `drugs` (drugsFuzzy='CDk4 inhibitors*') rather than being rerouted.
    """
    from oppp.models import Component, ComponentType, Decomposition
    from oppp.stages.decompose import reconcile_with_annotations

    decomp = Decomposition(
        query="NOEL of CDk4 inhibitors in mice",
        service="safety",
        components=[
            Component(
                field="drugs", nl_fragment="CDk4 inhibitors", type=ComponentType.FILTER, reason="x"
            ),
        ],
    )
    reconcile_with_annotations(decomp, SVC, annotations=[])  # no TARGET annotation
    assert decomp.filters[0].field == "drugs"  # untouched


def test_reconcile_promotes_recognized_tox_parameter_question_to_filter():
    """A recognized tox parameter must constrain retrieval, not just be a column.

    'What is the Maximum tolerated dose of X' -> the decomposer often emits a
    toxicityParameter QUESTION (reported column), dropping the filter and going
    overbroad (MTD: 2292 vs gold 4). TERMite recognized MTD, so the question is
    promoted to a FILTER on the preferred label. Regression for case 17.
    """
    from oppp.models import Component, ComponentType, Decomposition, EntityAnnotation
    from oppp.stages.decompose import reconcile_with_annotations

    decomp = Decomposition(
        query="What is the Maximum tolerated dose of Alpelisib in human",
        service="safety",
        components=[
            Component(
                field="toxicityParameter",
                nl_fragment="Maximum tolerated dose",
                type=ComponentType.QUESTION,
                reason="x",
            ),
            Component(
                field="drugs", nl_fragment="Alpelisib", type=ComponentType.FILTER, reason="x"
            ),
        ],
    )
    anns = [EntityAnnotation(surface="MTD", label="MTD", entity_type="TOXICITY_PARAMETER")]
    reconcile_with_annotations(decomp, SVC, anns)

    tox = next(c for c in decomp.components if c.field == "toxicityParameter")
    assert tox.type is ComponentType.FILTER  # promoted from question
    assert tox.nl_fragment == "MTD"  # uses the recognized preferred label


def test_reconcile_leaves_pure_question_field_alone():
    """A non-retrieval-defining question (e.g. dose) is NOT promoted to a filter.

    'what is the dose' is a reported column, not a constraint — only fields in
    _RETRIEVAL_DEFINING_FIELDS (tox parameters) are promoted, and only when an
    annotation recognized them. A plain dose question stays a question.
    """
    from oppp.models import Component, ComponentType, Decomposition
    from oppp.stages.decompose import reconcile_with_annotations

    decomp = Decomposition(
        query="drugs causing neutropenia in human, at which dose",
        service="safety",
        components=[
            Component(
                field="dose", nl_fragment="at which dose", type=ComponentType.QUESTION, reason="x"
            ),
        ],
    )
    reconcile_with_annotations(decomp, SVC, annotations=[])
    assert decomp.components[0].type is ComponentType.QUESTION  # untouched


def test_translate_entity_routed_open_field_uses_enhancer_label():
    """An entity-routed open field emits the enhancer's preferred label, not the phrase.

    The DrugsTargets entity filter matches 'Kinases' (the TERMite label, 213k records)
    but returns nothing for the raw 'inhibitors of kinases'. So the targets field must
    emit the matching-type annotation's label. Regression for the zero-results
    'inhibitors of kinases' bug (route + target value both had to be right).
    """
    from oppp.models import Component, ComponentType, EntityAnnotation

    comp = Component(
        field="targets",
        nl_fragment="inhibitors of kinases",
        type=ComponentType.FILTER,
        reason="x",
    )
    anns = [EntityAnnotation(surface="Kinases", label="Kinases", entity_type="TARGET")]

    # No annotation -> the raw phrase passes through (legacy behaviour preserved).
    raw = translate_one(comp, "safety", "noop", llm_select=False)
    assert raw.value == "inhibitors of kinases" and raw.entity_name == "DrugsTargets"

    # Matching TARGET annotation -> emit its preferred label, still entity-routed.
    grounded = translate_one(comp, "safety", "noop", llm_select=False, annotations=anns)
    assert grounded.value == "Kinases"
    assert grounded.entity_name == "DrugsTargets"


def test_annotation_binds_to_corresponding_fragment_not_first_of_type():
    """Multi-value same-field: each value binds to its OWN annotation, not the first.

    'rats or mice' with only a 'mouse' annotation must NOT collapse both species to
    Mouse — 'Rat' has to ground from its own fragment. Regression for the OR(Mouse,
    Mouse) bug that silently dropped half of any multi-value closed field (cases 12,
    16: neutropenia/thrombocytopenia, Rat/Mouse).
    """
    from oppp.models import Component, ComponentType, EntityAnnotation

    anns = [EntityAnnotation(surface="mouse", label="Mouse", entity_type="SPECIES")]
    rat = Component(field="species", nl_fragment="Rat", type=ComponentType.FILTER, reason="x")
    mouse = Component(field="species", nl_fragment="mice", type=ComponentType.FILTER, reason="x")

    rat_sq = translate_one(rat, "safety", "noop", llm_select=False, annotations=anns)
    mouse_sq = translate_one(mouse, "safety", "noop", llm_select=False, annotations=anns)
    assert rat_sq.value == "Rat"  # not hijacked to Mouse by the lone annotation
    assert mouse_sq.value == "Mouse"


def test_annotation_binds_abbreviation_when_fragment_has_no_self_grounding():
    """An abbreviation annotation still binds when surfaces differ but don't conflict.

    TERMite tags 'No Observed Adverse Effect Level' as label/surface 'NOAEL' (the
    abbreviation, not the matched span). The fragment text doesn't textually overlap
    'NOAEL' AND doesn't self-ground to any *other* vocab term, so the verified NOAEL
    label must still win. Regression: the fragment-correspondence guard (added for
    the Rat/Mouse multi-value bug) must NOT re-break the original NOAEL grounding.
    """
    from oppp.models import Component, ComponentType, EntityAnnotation

    for frag, label in [
        ("No Observed Adverse Effect Level", "NOAEL"),
        ("No Observed Effect Level", "NOEL"),
    ]:
        comp = Component(
            field="toxicityParameter", nl_fragment=frag, type=ComponentType.FILTER, reason="x"
        )
        ann = [EntityAnnotation(surface=label, label=label, entity_type="TOXICITY_PARAMETER")]
        sq = translate_one(comp, "safety", "noop", llm_select=False, annotations=ann)
        assert sq.value == label, frag  # grounds to the verified abbreviation


def test_translate_unions_all_termite_synonyms_for_one_fragment():
    """TERMite may offer several synonyms for one span; the WHOLE verified set is used.

    The search pool for a closed field is [normalized term] + [TERMite synonym labels].
    Every annotation whose label verifies against the CSV contributes a hit, all OR'd
    together — not just the first. Here one fragment carries two SPECIES synonyms; both
    must land in the value, each marked 'termite'.
    """
    from oppp.models import Component, ComponentType, EntityAnnotation

    comp = Component(
        field="species", nl_fragment="rat and mouse models", type=ComponentType.FILTER, reason="x"
    )
    anns = [
        EntityAnnotation(surface="rat", label="Rat", entity_type="SPECIES"),
        EntityAnnotation(surface="mouse", label="Mouse", entity_type="SPECIES"),
    ]
    sq = translate_one(comp, "safety", "noop", llm_select=False, annotations=anns)
    values = sq.value if isinstance(sq.value, list) else [sq.value]
    assert set(values) == {"Rat", "Mouse"}  # the entire synonym set, unioned
    assert all(h.match == "termite" for h in sq.grounding.matched)
    assert sq.grounding.confidence == 1.0


def test_translate_grounds_synonym_when_preferred_label_not_in_vocab():
    """The whole TERMite set is searched: a synonym grounds when the label does not.

    TERMite packs the equivalent-term set into one annotation (``synonyms``). When the
    preferred label is not a controlled-vocab term but a synonym is, the synonym must
    still resolve — and ungroundable members (label + bogus synonym) are dropped, so the
    value stays a subset of the closed set (CONST-1).
    """
    from oppp.models import Component, ComponentType, EntityAnnotation

    comp = Component(
        field="species", nl_fragment="homo sapiens", type=ComponentType.FILTER, reason="x"
    )
    anns = [
        EntityAnnotation(
            surface="homo sapiens",
            label="homo sapiens",  # not a CSV species term
            synonyms=["Human", "people"],  # 'Human' IS a CSV term; 'people' is not
            entity_type="SPECIES",
        )
    ]
    sq = translate_one(comp, "safety", "noop", llm_select=False, annotations=anns)
    assert sq.value == "Human"  # grounded via the synonym, label/bogus syn dropped
    assert sq.grounding.matched[0].match == "termite"
    assert "homo sapiens" not in str(sq.value) and "people" not in str(sq.value)


def test_translate_grounds_annotation_class_label_to_class_not_leaf():
    """A group annotation whose label is a class node resolves to the CLASS, not a leaf.

    TERMite tags 'rodent' as SPECIES label 'Rodent' — a parent node with no own CSV row.
    The exact lookup of 'Rodent' returns nothing, so the high-precision annotation must
    fall back to class resolution and emit the single class label 'Rodent' (the API
    expands it server-side to Mouse/Rat/Vole/…), NOT mis-ground to the 'Rodent
    (unspecified)' leaf. Regression for the 0-results 'liver disorders in rodent' query.
    """
    from oppp.models import Component, ComponentType, EntityAnnotation

    comp = Component(
        field="species", nl_fragment="rodent species", type=ComponentType.FILTER, reason="x"
    )
    anns = [EntityAnnotation(surface="Rodent", label="Rodent", entity_type="SPECIES")]
    sq = translate_one(comp, "safety", "noop", llm_select=False, annotations=anns)
    assert sq.value == "Rodent"  # the class label, expanded server-side
    assert sq.grounding.expanded_from == "class"
    assert sq.grounding.matched[0].match == "class"
    assert "unspecified" not in str(sq.value)  # not the leaf mis-grounding


def test_termite_enhancer_captures_public_synonyms(monkeypatch):
    """The TERMite enhancer records publicSynonyms (deduped, label excluded).

    Real TERMite returns the equivalent-term set inside each entity as publicSynonyms;
    the enhancer must surface them on the annotation so Stage 2 can ground the whole set.
    """
    from oppp.models import EntityAnnotation
    from oppp.stages.enhance import TermiteEnhancer

    raw = {
        "included": [
            {
                "entities": [
                    {
                        "vocabularyId": "PP_TOX",
                        "name": "NOAEL",
                        "originalText": "No Observed Adverse Effect Level",
                        "publicSynonyms": [
                            "NOAEL",  # == label -> excluded
                            "No Observed Adverse Effect Level",
                            "no adverse effect level",
                            "no adverse effect level",  # dup -> collapsed
                        ],
                    }
                ]
            }
        ]
    }
    enh = TermiteEnhancer.__new__(TermiteEnhancer)  # bypass creds/SDK __init__
    monkeypatch.setattr(enh, "_annotate", lambda *a, **k: raw, raising=False)
    out = enh.enhance("...", SVC)
    assert len(out.annotations) == 1
    ann: EntityAnnotation = out.annotations[0]
    assert ann.label == "NOAEL"
    assert ann.synonyms == ["No Observed Adverse Effect Level", "no adverse effect level"]


def test_translate_term_contributes_exact_only_when_annotations_exist():
    """With TERMite synonyms present, the raw term adds only its EXACT self-grounding.

    A noisy multi-word fragment must not drag unrelated fuzzy rows into the union once
    TERMite has authoritatively resolved the concept: 'rat and mouse models' fuzzy-
    matches 'Deer mouse'/'Grass rat', but those must NOT appear alongside the clean
    'Rat'/'Mouse' synonym labels. (Fuzzy/LLM still apply when no annotation exists.)
    """
    from oppp.models import Component, ComponentType, EntityAnnotation

    comp = Component(
        field="species", nl_fragment="rat and mouse models", type=ComponentType.FILTER, reason="x"
    )
    anns = [
        EntityAnnotation(surface="rat", label="Rat", entity_type="SPECIES"),
        EntityAnnotation(surface="mouse", label="Mouse", entity_type="SPECIES"),
    ]
    sq = translate_one(comp, "safety", "noop", llm_select=False, annotations=anns)
    names = {h.name for h in sq.grounding.matched}
    assert not (names - {"Rat", "Mouse"})  # no fuzzy noise leaked into the union


def test_translate_normalized_term_is_always_a_candidate():
    """The normalized term is in the pool whether or not annotations exist.

    A drug annotation of the SPECIES type does not correspond to a SPECIES fragment, so
    ann_hits is empty here — and the normalized term ('Rat') must still ground on its
    own. The term is never gated behind an annotation existing.
    """
    from oppp.models import Component, ComponentType

    comp = Component(field="species", nl_fragment="Rat", type=ComponentType.FILTER, reason="x")
    sq = translate_one(comp, "safety", "noop", llm_select=False, annotations=[])
    assert sq.value == "Rat"


def test_no_trailing_wildcard_on_multiword_drug_value():
    """A bare trailing '*' on a multi-word drugsFuzzy value is rejected (HTTP 400).

    So 'CDk4 inhibitors' must NOT become 'CDk4 inhibitors*'; a single-token drug
    still gets the wildcard. Regression for cases 14/20/22 (multi-word wildcard 400).
    """
    from oppp.models import Component, ComponentType

    multi = Component(
        field="drugs", nl_fragment="CDk4 inhibitors", type=ComponentType.FILTER, reason="x"
    )
    single = Component(
        field="drugs", nl_fragment="Sunitinib", type=ComponentType.FILTER, reason="x"
    )
    assert translate_one(multi, "safety", "noop", llm_select=False).value == "CDk4 inhibitors"
    assert translate_one(single, "safety", "noop", llm_select=False).value == "Sunitinib*"


def test_drug_class_emits_label_not_member_explosion():
    """A drug/indication class emits its LABEL (API resolves it), not all children.

    Inlining 100+ class members busts the API's ~49-value-per-list cap (HTTP 400).
    'monoclonal antibodies' and 'kinase inhibitors' must emit the single class label.
    Regression for cases 14/22 (uncapped class expansion 400).
    """
    from oppp.models import Component, ComponentType

    for frag, label in [
        ("monoclonal antibodies", "Monoclonal antibodies"),
        ("kinase inhibitors", "Kinase inhibitors"),
    ]:
        comp = Component(field="drugs", nl_fragment=frag, type=ComponentType.FILTER, reason="x")
        sq = translate_one(comp, "safety", "noop", llm_select=False)
        assert sq.value == label  # single class label, not a list of members
        assert sq.grounding.expanded_from == "class"


def test_colloquial_species_plural_resolves_to_common_parent_class():
    """'Monkeys' resolves to the 'Primate' class; specific species stay leaves.

    'Monkeys' has no own taxonomy node (the parent is 'Primate'), so it fuzzy-matched
    only 'Monkey (unspecified)' (14 records vs the intended 27). When a colloquial
    plural's singular is a standalone word in several entries that ALL share one
    parent, resolve to that parent (the API expands it server-side). A specific
    species ('Mouse'/'mice', 'Rat') is an exact leaf and must NOT widen to its class.
    Regression for case 22 (monoclonal antibodies in Monkeys).
    """
    from oppp.models import Component, ComponentType

    monkeys = Component(
        field="species", nl_fragment="Monkeys", type=ComponentType.FILTER, reason="x"
    )
    sq = translate_one(monkeys, "safety", "noop", llm_select=False)
    assert sq.value == "Primate"
    assert sq.grounding.expanded_from == "class"

    for frag, leaf in [("mice", "Mouse"), ("Rat", "Rat")]:
        comp = Component(field="species", nl_fragment=frag, type=ComponentType.FILTER, reason="x")
        sq = translate_one(comp, "safety", "noop", llm_select=False)
        assert sq.value == leaf  # specific species stays a leaf, not its parent class


def test_effects_rollup_is_additive_and_score_gated():
    """Family rollup keeps the canonical term (additive) and skips weak anchors.

    'Neutropenia' rolls up to its family but the value set still INCLUDES
    'Neutropenia' (additive — never loses the broad term). Regression for case 18
    (Mutagenicity over-narrow): the broad/canonical term must survive the rollup.
    """
    from oppp.models import Component, ComponentType

    neutro = Component(
        field="effects", nl_fragment="Neutropenia", type=ComponentType.FILTER, reason="x"
    )
    sq = translate_one(neutro, "safety", "noop", llm_select=False)
    values = sq.value if isinstance(sq.value, list) else [sq.value]
    assert sq.grounding.expanded_from == "family"
    assert "Neutropenia" in values  # additive: canonical term retained
    assert len(values) > 1


def test_effects_result_qualifier_is_stripped_before_grounding():
    """A polarity word must not hijack the rollup anchor into an unrelated family.

    'positive Ames Test' grounds whole-phrase to 'Amniotic membrane rupture test
    positive' (shared 'positive'/'test' words) -> the foetal-diagnostics family.
    Stripping the result qualifier keys grounding on 'Ames Test' -> the Ames assay
    family. The raw phrase is also kept additively. Regression for case 19.
    """
    from oppp.models import Component, ComponentType

    ames = Component(
        field="effects", nl_fragment="positive Ames Test", type=ComponentType.FILTER, reason="x"
    )
    sq = translate_one(ames, "safety", "noop", llm_select=False)
    vals = sq.value if isinstance(sq.value, list) else [sq.value]
    assert sq.grounding.expanded_from == "family"
    assert any("Ames test" in v for v in vals)  # correct assay family
    assert not any("Amniotic" in v for v in vals)  # not the foetal mis-match


def test_llm_map_unions_over_attempts_for_flaky_mapping(monkeypatch):
    """The empty-pool LLM map is flaky; unioning attempts recovers a dropped term.

    The mapping call is non-deterministic in practice (e.g. 'IV administration' ->
    'intravenous' only ~half the calls). A single empty response must not drop the
    constraint to confidence 0 — a later attempt should recover it. Here the first
    call returns nothing and the second proposes 'intravenous'.
    """
    from oppp.models import TermSelection
    from oppp.stages.translate import _llm_map_to_vocab
    from oppp.taxonomy.index import get_index

    calls = {"n": 0}

    class FlakySelector:
        def invoke(self, _prompt):
            calls["n"] += 1
            # empty on the first attempt, real proposal on the second
            return TermSelection(selected=[] if calls["n"] == 1 else ["intravenous"])

    monkeypatch.setattr("oppp.stages.translate._get_term_selector", lambda: FlakySelector())
    hits = _llm_map_to_vocab("IV administration", "route", get_index("route"), attempts=3)
    assert [h.name for h in hits] == ["intravenous"]
    assert calls["n"] >= 2  # it did not give up after the first empty response


def test_llm_fallback_sees_whole_pool_via_aliases(monkeypatch):
    """When the whole pool fails to ground, the LLM fallback sees every pool phrasing.

    The pool is the fragment + the TERMite synonym labels. If none ground by
    exact/fuzzy, both LLM stages must be shown the *entire* pool (not just the bare
    fragment) so a synonym the model recognises can still resolve the term.
    """
    from oppp.models import TermSelection
    from oppp.stages.translate import _llm_map_to_vocab
    from oppp.taxonomy.index import get_index

    seen_prompts = []

    class CapturingSelector:
        def invoke(self, prompt):
            seen_prompts.append(prompt)
            return TermSelection(selected=["Human"])  # a real species row

    monkeypatch.setattr("oppp.stages.translate._get_term_selector", lambda: CapturingSelector())
    hits = _llm_map_to_vocab(
        "homo sapiens", "species", get_index("species"), aliases=["Human being", "people"]
    )
    assert [h.name for h in hits] == ["Human"]  # re-grounded to the real row
    assert any("Human being" in p and "people" in p for p in seen_prompts)  # whole pool shown


def test_llm_map_grounds_class_members_as_subset_of_closed_set(monkeypatch):
    """A class/group phrase ('ADC') has no row, but its members do.

    The string matcher can't reach 'ADC' (no such drug/class name in drugs.csv), so
    the LLM points at the specific member entries it knows. Each is re-grounded against
    the taxonomy (exact first), so the emitted value is always a SUBSET of the closed
    set — real rows, never the invented group string. Regression for case 24 (ADC).
    """
    from oppp.models import TermSelection
    from oppp.stages.translate import _llm_map_to_vocab
    from oppp.taxonomy.index import get_index

    class MemberSelector:
        def invoke(self, _prompt):
            # real drugs.csv rows + one hallucination that must be dropped (not in CSV)
            return TermSelection(
                selected=[
                    "Brentuximab Vedotin",
                    "Gemtuzumab Ozogamicin",
                    "Not A Real Drug 123",
                ]
            )

    monkeypatch.setattr("oppp.stages.translate._get_term_selector", lambda: MemberSelector())
    hits = _llm_map_to_vocab("ADC", "drugs", get_index("drugs"))
    names = {h.name for h in hits}
    assert "Brentuximab Vedotin" in names  # real member -> grounded
    assert "Gemtuzumab Ozogamicin" in names
    assert "Not A Real Drug 123" not in names  # ungroundable proposal dropped (CONST-1)
    assert all(get_index("drugs").get_exact(n) is not None for n in names)  # all real rows


def test_translate_one_closed_field_isolated():
    comp = Component(
        field="species",
        nl_fragment="mice",
        type=ComponentType.FILTER,
        reason="isolated",
        source="test",
    )
    sq = translate_one(comp, "safety", "noop")
    assert sq is not None and sq.value == "Mouse"


def test_translate_grounds_enhancer_preferred_label_for_closed_field():
    """Resolution-order step 1: the Stage-0 enhancer's preferred label wins.

    The decomposer copies the user's verbatim words ('No Observed Adverse Effect
    Level'), which fuzzy-match the toxicityParameter CSV poorly (no synonym row).
    But TERMite already recognized it and resolved it to the preferred label
    'NOAEL', a real vocab term. Passing that annotation makes Stage 2 ground to
    'NOAEL' (confidence 1.0) instead of emitting the unmatched raw phrase.
    Regression for the zero-results NOAEL bug.
    """
    from oppp.models import EntityAnnotation

    comp = Component(
        field="toxicityParameter",
        nl_fragment="No Observed Adverse Effect Level",
        type=ComponentType.FILTER,
        reason="x",
        source="test",
    )
    anns = [
        EntityAnnotation(
            surface="No Observed Adverse Effect Level",
            label="NOAEL",
            entity_type="TOXICITY_PARAMETER",
        )
    ]

    # Without the annotation the raw phrase grounds poorly (the reported bug).
    bad = translate_one(comp, "safety", "noop", llm_select=False)
    assert bad.value != "NOAEL" and bad.grounding.confidence < 0.5

    # With the enhancer's verified preferred label it grounds to the vocab term.
    good = translate_one(comp, "safety", "noop", llm_select=False, annotations=anns)
    assert good.value == "NOAEL"
    assert good.grounding is not None and good.grounding.confidence == 1.0
    assert good.grounding.matched[0].match == "termite"


def test_translate_ignores_annotation_not_in_vocab():
    """CONST-1: an enhancer label absent from the CSV is never emitted raw.

    If TERMite proposes a label that does not verify against the field's CSV, we
    must fall through to the normal lookup path rather than trusting the string.
    """
    from oppp.models import EntityAnnotation

    comp = Component(
        field="toxicityParameter",
        nl_fragment="NOAEL",
        type=ComponentType.FILTER,
        reason="x",
        source="test",
    )
    anns = [
        EntityAnnotation(
            surface="NOAEL", label="Totally Not A Real Param", entity_type="TOXICITY_PARAMETER"
        )
    ]
    sq = translate_one(comp, "safety", "noop", llm_select=False, annotations=anns)
    # The bogus annotation is dropped; the raw fragment grounds to the real term.
    assert sq.value == "NOAEL"
    assert "Totally Not A Real Param" not in str(sq.value)


def test_aggregator_deterministic_builds_or_group():
    # Build subqueries directly and aggregate in isolation (no decompose/translate).
    decomp = Decomposition(query="rats or mice", service="safety", components=[])
    grp = BooleanGroup(id="species-group", op=BooleanOp.OR)
    subs = [
        translate_one(
            Component(
                field="species",
                nl_fragment="rats",
                type=ComponentType.FILTER,
                reason="x",
                source="t",
                boolean_group=grp,
            ),
            "safety",
            "noop",
        ),
        translate_one(
            Component(
                field="species",
                nl_fragment="mice",
                type=ComponentType.FILTER,
                reason="x",
                source="t",
                boolean_group=grp,
            ),
            "safety",
            "noop",
        ),
    ]
    mq, issues = get_aggregator("deterministic").aggregate(decomp, subs, SVC)
    assert not any(i.level == "error" for i in issues)
    assert "OR" in str(mq.query)


def test_translate_preclinical_phrase_on_species_is_dropped_not_invented():
    # "non clinical species" is NOT a real species value. The decomposer routes the
    # preclinical concept to the boolean isPreclinical field (see the boolean test
    # below); should the phrase ever reach the *species* field, Stage 2 must NOT emit
    # the raw out-of-vocabulary string as a hard MATCH (that silently zeroes the whole
    # query). CONST-1: ground or drop — never invent. The constraint is flagged dropped
    # so Stage 3 excludes it, leaving the valid superset rather than 0.
    for frag in ("preclinical species", "non-clinical species", "non clinical species"):
        comp = Component(field="species", nl_fragment=frag, type=ComponentType.FILTER, reason="x")
        sq = translate_one(comp, "safety", "noop", llm_select=False)
        assert sq.dropped is True, frag
        assert sq.grounding is not None and sq.grounding.confidence == 0.0, frag


def test_translate_ispreclinical_boolean_true_on_preclinical_phrasings():
    for frag, expected in [
        ("at least one preclinical species", True),
        ("preclinical", True),
        ("yes", True),
        ("clinical only", False),
    ]:
        comp = Component(
            field="isPreclinical", nl_fragment=frag, type=ComponentType.FILTER, reason="x"
        )
        sq = translate_one(comp, "safety", "noop", llm_select=False)
        assert sq.value is expected, (frag, sq.value)


def test_ungroundable_closed_vocab_is_dropped_and_excluded_by_aggregator():
    # An ungroundable closed-vocab term must not become a hard MATCH (it would zero the
    # whole AND). Stage 2 flags it dropped; the aggregator excludes it from the tree and
    # records a warning, so the remaining valid filters still produce a query.
    oov = Component(
        field="species", nl_fragment="non clinical species", type=ComponentType.FILTER, reason="x"
    )
    good = Component(field="drugs", nl_fragment="Sunitinib", type=ComponentType.FILTER, reason="x")
    oov_sq = translate_one(oov, "safety", "noop", llm_select=False)
    good_sq = translate_one(good, "safety", "noop", llm_select=False)
    assert oov_sq.dropped is True

    decomp = Decomposition(query="q", service="safety", components=[oov, good])
    mq, issues = get_aggregator("deterministic").aggregate(decomp, [oov_sq, good_sq], SVC)
    assert not any(i.level == "error" for i in issues)
    # the dropped species value must not appear anywhere in the emitted query
    assert "non clinical species" not in str(mq.query)
    assert "Sunitinib" in str(mq.query)
    assert any("dropped ungroundable" in i.message for i in issues)


def test_open_set_zero_count_filter_is_probed_and_dropped(monkeypatch):
    # Open-set fields have no CSV to validate against, so Stage 3 probes each one's
    # isolated server-side count and drops it ONLY when 0 (matches no record). Closed
    # and entity-routed fields are not probed. On probe error it keeps (fail open).
    import oppp.execute as execute_mod
    from oppp.execute import ExecutionResult
    from oppp.models import MachineSubquery, Operator
    from oppp.stages.aggregate import drop_empty_open_filters

    # value -> (ok, count): 'related to maternal toxicity' matches nothing.
    counts = {
        "maternal toxicity": ExecutionResult(ok=True, count_total=1029),
        "related to maternal toxicity": ExecutionResult(ok=True, count_total=0),
    }

    def fake_count(mq, service, **kw):
        val = mq.query.get("MATCH", {}).get("value")
        return counts.get(val, ExecutionResult(ok=False, error="boom"))

    monkeypatch.setattr(execute_mod, "execute_count", fake_count)

    good = MachineSubquery(field="parameterComment", operator=Operator.MATCH, value="maternal toxicity")
    empty = MachineSubquery(
        field="parameterComment", operator=Operator.MATCH, value="related to maternal toxicity"
    )
    failopen = MachineSubquery(field="parameterComment", operator=Operator.MATCH, value="unknown phrase")
    closed = MachineSubquery(field="drugsFuzzy", operator=Operator.MATCH, value="Sunitinib*")
    entity = MachineSubquery(
        field="targets", operator=Operator.MATCH, value="Kinases", entity_name="DrugsTargets"
    )

    issues = []
    kept = drop_empty_open_filters([good, empty, failopen, closed, entity], SVC, issues)
    kept_vals = {(s.field, s.value) for s in kept}
    assert ("parameterComment", "maternal toxicity") in kept_vals  # nonzero -> kept
    assert ("parameterComment", "related to maternal toxicity") not in kept_vals  # zero -> dropped
    assert ("parameterComment", "unknown phrase") in kept_vals  # probe failed -> fail open
    assert ("drugsFuzzy", "Sunitinib*") in kept_vals  # closed field -> not probed
    assert ("targets", "Kinases") in kept_vals  # entity-routed -> not probed
    assert any("dropped open-set parameterComment" in i.message for i in issues)


def test_enum_matches_value_as_word_in_fragment():
    # The expander/decomposer may carry a qualifier ('male subjects', 'female patients').
    # The enum match accepts the enum value as a standalone word, and must not confuse
    # 'female' with 'male' (word boundaries).
    for frag, want in [
        ("male subjects", "Male"),
        ("in males", "Male"),
        ("female patients", "Female"),
        ("both sexes", "Both"),
    ]:
        comp = Component(field="sex", nl_fragment=frag, type=ComponentType.FILTER, reason="x")
        sq = translate_one(comp, "safety", "noop", llm_select=False)
        assert sq.value == want, (frag, sq.value)


def test_free_text_field_strips_leading_connective():
    # parameterComment is a free-text field; the decomposer copies the query's glue
    # ('...related to maternal toxicity') into the fragment, but the API matches the
    # substantive phrase. The leading connective is stripped so 'related to maternal
    # toxicity' searches 'maternal toxicity'. General over open free-text fields.
    comp = Component(
        field="parameterComment",
        nl_fragment="related to maternal toxicity",
        type=ComponentType.FILTER,
        reason="x",
    )
    sq = translate_one(comp, "safety", "noop", llm_select=False)
    assert sq.value == "maternal toxicity"


def test_term_selector_routes_through_central_llm_factory(monkeypatch):
    """Stage-2 term selector builds its model via oppp.llm, not its own client.

    The single-factory routing is what guarantees every LLM call shares one
    temperature=0 setting. On the old (duplicated-client) code this returned None
    offline; now it must go through oppp.llm.structured. Hermetic: no creds.
    """
    import oppp.llm as llm_mod
    import oppp.stages.translate as translate_mod
    from oppp.models import TermSelection

    sentinel = object()
    seen = {}

    def fake_structured(schema, **kwargs):
        seen["schema"] = schema
        return sentinel

    monkeypatch.setattr(llm_mod, "structured", fake_structured)
    translate_mod._get_term_selector.cache_clear()

    assert translate_mod._get_term_selector() is sentinel
    assert seen["schema"] is TermSelection


def test_every_llm_call_is_built_for_reproducibility(monkeypatch):
    """Every LLM client (central factory + Stage-2 selector) is built deterministically.

    Stubs langchain_openai with a recorder so the test stays hermetic whether or
    not the optional 'llm' extra is installed (CONST-8/9), then exercises both
    construction routes and asserts the reproducibility knobs: temperature=0,
    top_p=0, and a fixed integer seed.
    """
    import sys
    import types

    import oppp.config as config
    import oppp.llm as llm_mod
    import oppp.stages.translate as translate_mod

    recorded = []

    class _FakeChat:
        def __init__(self, **kwargs):
            recorded.append(kwargs)

        def with_structured_output(self, schema):
            return self

    fake_mod = types.ModuleType("langchain_openai")
    fake_mod.ChatOpenAI = _FakeChat
    monkeypatch.setitem(sys.modules, "langchain_openai", fake_mod)

    monkeypatch.setenv("PORTKEY_ENDPOINT", "https://fake.endpoint")
    monkeypatch.setenv("PORTKEY_API_KEY", "fake-key")
    monkeypatch.setenv("PORTKEY_PROVIDER", "openai")
    monkeypatch.setenv("TOOL_MODEL", "fake-model")
    config.get_settings.cache_clear()
    llm_mod.get_chat_model.cache_clear()
    translate_mod._get_term_selector.cache_clear()

    llm_mod.get_chat_model()  # used by decompose / aggregate / judge via structured()
    translate_mod._get_term_selector()  # Stage-2 term selector

    assert recorded, "no LLM client was constructed"
    assert all(kw.get("temperature") == 0 for kw in recorded), recorded
    assert all(kw.get("top_p") == 0 for kw in recorded), recorded
    assert all(isinstance(kw.get("seed"), int) for kw in recorded), recorded
