import csv

import pytest

from oppp.eval import evaluate, load_gold_cases
from oppp.eval.harness import CASE_COLUMNS, _parse_expected, write_report


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


def test_eval_report_writes_csv(tmp_path):
    report = evaluate(execute=False, limit=2)
    out = tmp_path / "r.csv"
    assert write_report(report, out, run_config={"decomposer": "gazetteer"}) == out
    with open(out, encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    first_cells = [r[0] for r in rows if r]
    # parameters + summary appear on top, then the per-case table.
    assert "Parameters" in first_cells and "Summary" in first_cells
    assert "decomposer" in first_cells  # the run params were written
    header_idx = rows.index(CASE_COLUMNS)
    assert len(rows) - (header_idx + 1) == len(report.cases)


def test_eval_report_writes_xlsx_with_params_and_summary_on_top(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    report = evaluate(execute=False, limit=2)
    out = tmp_path / "r.xlsx"
    write_report(report, out, run_config={"decomposer": "gazetteer"})
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames == ["report"]
    col_a = [c.value for c in wb["report"]["A"]]
    # params + summary blocks precede the case-table header in the single sheet.
    assert col_a.index("Parameters") < col_a.index("Summary") < col_a.index(CASE_COLUMNS[0])
    assert "decomposer" in col_a and "valid_rate" in col_a


def test_eval_report_defaults_to_xlsx(tmp_path):
    pytest.importorskip("openpyxl")
    out = write_report(evaluate(execute=False, limit=1), tmp_path / "r")  # no extension
    assert out.suffix == ".xlsx" and out.exists()


def test_eval_report_rejects_unknown_extension(tmp_path):
    with pytest.raises(ValueError):
        write_report(evaluate(execute=False, limit=1), tmp_path / "r.txt")
