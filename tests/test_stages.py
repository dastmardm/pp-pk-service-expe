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
