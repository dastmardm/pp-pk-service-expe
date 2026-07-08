"""Offline tests for the per-step comparators and the (stubbed) LLM-as-judge.

The comparators run against the PK gold set (docs/PPPK.xlsx, PK_Query sheet)
with the offline doubles; the judge is exercised with an injected fake client so
the test needs no creds or network.
"""

import pytest

from oppp.eval.judge import JudgeVerdict, LLMJudge, Verdict
from oppp.eval.per_step import (
    compare_steps,
    load_perstep_cases,
    score_decompose,
    score_machine_query,
)
from oppp.models import (
    Component,
    ComponentType,
    Decomposition,
    PipelineResult,
)
from oppp.pipeline import run_pipeline

_Q = "What is the Cmax of sunitinib in rat after oral administration"


def _offline(query, service="pk"):
    return run_pipeline(
        query,
        service,
        expander="noop",
        decomposer="gazetteer",
        translator="deterministic",
        aggregator="deterministic",
        normalizer="fuzzy",
    )


def test_perstep_gold_loads():
    pytest.importorskip("openpyxl")
    rows = load_perstep_cases()
    assert isinstance(rows, list)
    if rows:
        assert len(rows) >= 1
        assert "Query" in rows[0] or "Quety number" in rows[0]


def test_compare_steps_returns_all_stages():
    result = _offline(_Q)
    gold_row = {
        "termite": "",
        "decompose": "drugs[filter] species[filter] routes[filter]",
        "translate": "drugsFuzzy= species= routes=",
        "machine query": "",
    }
    scores = compare_steps(result, gold_row)
    assert {"termite", "decompose", "translate", "machine query"} <= set(scores)
    assert all(0.0 <= s.score <= 1.0 for s in scores.values())


def test_decompose_comparator_is_routing_type_aware():
    comps = [
        Component(
            field="drugs", nl_fragment="x", type=ComponentType.FILTER, reason="r", source="t"
        ),
        Component(
            field="species", nl_fragment="y", type=ComponentType.FILTER, reason="r", source="t"
        ),
    ]
    result = PipelineResult(
        query="q",
        service="pk",
        decomposition=Decomposition(query="q", service="pk", components=comps),
    )
    good = score_decompose(result, 'drugs[filter]:"x"; species[filter]:"y"')
    bad = score_decompose(result, 'drugs[filter]:"x"; species[question]:"y"')
    assert good.score == 1.0
    assert bad.score < good.score


def test_machine_query_comparator_handles_unparseable_gold():
    result = _offline(_Q)
    assert score_machine_query(result, "not json").score == 0.0


class _FakeClient:
    def __init__(self, verdict):
        self._verdict = verdict

    def invoke(self, prompt):  # noqa: ARG002 - prompt unused in the stub
        return self._verdict


def test_judge_returns_typed_verdict_for_each_freetext_step():
    judge = LLMJudge(client=_FakeClient(JudgeVerdict(verdict=Verdict.PARTIAL, reason="ok")))
    for v in (
        judge.judge_fragment("question", "produced", "expected"),
        judge.judge_open_pattern("studyGroup", ".*hepatic.*", "hepatic impairment"),
        judge.judge_structure("question", '{"AND": []}', "AND of two fields"),
    ):
        assert isinstance(v, JudgeVerdict)
        assert v.verdict is Verdict.PARTIAL
