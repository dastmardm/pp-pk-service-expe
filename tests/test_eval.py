from oppp.eval import evaluate, load_gold_cases
from oppp.eval.harness import _parse_expected


def test_parse_expected_counts():
    assert _parse_expected("4300") == 4300
    assert _parse_expected("61,198") == 61198
    assert _parse_expected("") is None


def test_gold_set_loads():
    rows = load_gold_cases()
    assert len(rows) >= 20
    assert "s" in rows[0] and "question" in rows[0]


def test_eval_offline_measures_validity_and_expected():
    # execute=False keeps the test offline (no API). The metric still parses the
    # expected count column `s` for each case.
    report = evaluate(execute=False, limit=5)
    assert len(report.cases) == 5
    assert report.executed_rate == 0.0
    assert all(c.actual is None for c in report.cases)
    assert any(c.expected is not None for c in report.cases)
    assert 0.0 <= report.valid_rate <= 1.0
