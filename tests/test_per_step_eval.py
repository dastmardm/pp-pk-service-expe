"""Offline tests for the per-step comparators and the (stubbed) LLM-as-judge.

The comparators run against the per-step gold set (docs/sme_stage_cases.csv) with
the offline doubles; the judge is exercised with an injected fake client so the
test needs no creds or network.
"""

from oppp.eval.judge import JudgeVerdict, LLMJudge, Verdict
from oppp.eval.per_step import (
    compare_steps,
    find_perstep_case,
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

_Q = "What are the ADRs of Sunitinib in human"


def _offline(query, service="safety"):
    return run_pipeline(
        query,
        service,
        expander="noop",
        decomposer="gazetteer",
        translator="deterministic",
        aggregator="deterministic",
        normalizer="fuzzy",
    )


def test_perstep_gold_loads_with_expected_columns():
    rows = load_perstep_cases()
    assert len(rows) >= 20
    assert {"nl query", "decompose", "translate", "machine query"} <= set(rows[0])


def test_compare_steps_scores_a_matching_case():
    row = find_perstep_case(_Q)
    assert row is not None
    scores = compare_steps(_offline(_Q), row)
    assert {"termite", "decompose", "translate", "machine query"} <= set(scores)
    # The offline gazetteer routes drugs+species and the deterministic aggregator
    # builds the same fields the SME recorded.
    assert scores["decompose"].score >= 0.5
    assert scores["translate"].score >= 0.5
    assert scores["machine query"].score >= 0.5
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
        service="safety",
        decomposition=Decomposition(query="q", service="safety", components=comps),
    )
    # gold lists species as a question, not a filter -> routing mismatch lowers F1.
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
