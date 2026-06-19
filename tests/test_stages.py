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
