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


def test_reconcile_reroutes_mechanism_filter_to_targets_on_target_annotation():
    """A mechanism phrase ('inhibitors of kinases') belongs on `targets`, not `drugs`.

    The decomposer parks it on `drugs` (where it fuzzy-matches nonsense and returns
    zero records); TERMite's TARGET annotation reroutes it to the DrugsTargets
    entity filter. Regression for the zero-results 'inhibitors of kinases' bug
    (gold case expects ~1851 records).
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

    by_frag = {c.nl_fragment: c.field for c in decomp.filters}
    assert by_frag["inhibitors of kinases"] == "targets"  # rerouted
    assert by_frag["human"] == "species"  # untouched


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


def test_every_llm_call_is_built_with_temperature_zero(monkeypatch):
    """Every LLM client (central factory + Stage-2 selector) is temperature=0.

    Stubs langchain_openai with a recorder so the test stays hermetic whether or
    not the optional 'llm' extra is installed (CONST-8/9), then exercises both
    construction routes and asserts the recorded temperature is 0.
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
