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


def test_translate_preclinical_species_curated_expansion():
    # "preclinical species" is a curated concept (no single taxonomy node): it must
    # expand to grounded member species, never pass through as the raw, invented
    # value (CONST-1). Substring-matched, so LLM phrasings resolve too. Regression
    # for the case-7 eval bug.
    for frag in ("preclinical species", "at least one preclinical species", "non-clinical species"):
        comp = Component(field="species", nl_fragment=frag, type=ComponentType.FILTER, reason="x")
        sq = translate_one(comp, "safety", "noop", llm_select=False)
        values = sq.value if isinstance(sq.value, list) else [sq.value]
        assert sq.grounding is not None and sq.grounding.expanded_from == "curated", frag
        assert frag not in values
        assert {"Rat", "Mouse", "Dog"}.issubset(set(values)), frag


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
