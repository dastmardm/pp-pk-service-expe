"""Evaluation over the per-step SME gold set (docs/sme_stage_cases.csv).

The metric is **result-count accuracy**: each gold row carries the question
(`nl query`) and an expected number of matching records (`counts`). We translate
the question, execute the machine query against the PharmaPendium API, read
`countTotal`, and compare it to `counts`.

Reported: how often the query is valid, how often it executes, exact-count match
rate, and within-tolerance rate (counts drift as the DB updates, so a tolerance
band is the realistic signal).

(The per-field gold set `inputs/sme_expected_cases.csv` is still loaded by
:func:`load_gold_cases` for the side-by-side per-field view of `oppp run --case N`.)
"""

from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from oppp.config import get_settings
from oppp.execute import execute_count
from oppp.pipeline import run_pipeline
from oppp.services.base import get_service


def _parse_expected(cell: str) -> int | None:
    if not cell:
        return None
    m = re.search(r"\d[\d,]*", cell)
    return int(m.group(0).replace(",", "")) if m else None


@dataclass
class CaseResult:
    query_number: str
    question: str
    ok: bool  # produced a valid machine query
    expected: int | None = None
    actual: int | None = None
    executed: bool = False
    issues: list[str] = field(default_factory=list)
    exec_error: str | None = None

    @property
    def exact(self) -> bool:
        return (
            self.expected is not None and self.actual is not None and self.expected == self.actual
        )

    def within(self, tol: float) -> bool:
        if self.expected is None or self.actual is None:
            return False
        if self.expected == 0:
            return self.actual == 0
        return abs(self.actual - self.expected) / self.expected <= tol

    @property
    def ratio(self) -> float | None:
        if self.expected is None or self.actual is None or self.expected == 0:
            return None
        return self.actual / self.expected


@dataclass
class EvalReport:
    tolerance: float = 0.10
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def valid_rate(self) -> float:
        return _mean([1.0 if c.ok else 0.0 for c in self.cases])

    @property
    def executed_rate(self) -> float:
        return _mean([1.0 if c.executed else 0.0 for c in self.cases])

    @property
    def scored(self) -> list[CaseResult]:
        return [c for c in self.cases if c.executed and c.expected is not None]

    @property
    def exact_match_rate(self) -> float:
        s = self.scored
        return _mean([1.0 if c.exact else 0.0 for c in s]) if s else 0.0

    @property
    def within_tol_rate(self) -> float:
        s = self.scored
        return _mean([1.0 if c.within(self.tolerance) else 0.0 for c in s]) if s else 0.0


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def load_gold_cases() -> list[dict]:
    """Per-field SME gold set (inputs/sme_expected_cases.csv).

    Carries `query_number` and one column per field; used by `oppp run --case N`
    for the side-by-side gold-vs-agent per-field comparison (oppp.eval.compare).
    """
    path = get_settings().inputs_dir / "sme_expected_cases.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def evaluate(
    *,
    service: str = "safety",
    enhancer: str = "noop",
    decomposer: str = "gazetteer",
    translator: str = "deterministic",
    aggregator: str = "deterministic",
    normalizer: str = "fuzzy",
    tolerance: float = 0.10,
    execute: bool = True,
    limit: int | None = None,
) -> EvalReport:
    """Run each per-step gold question and compare executed `countTotal` to `counts`.

    Reads the question (`nl query`) and expected count (`counts`) from the per-step
    gold set `docs/sme_stage_cases.csv` (:func:`load_perstep_cases`). Defaults to the
    offline doubles (gazetteer + deterministic) so the harness is cheap and hermetic;
    pass decomposer='llm'/aggregator='llm' to evaluate the production pipeline.
    `execute=False` skips the API call: only validity is measured.
    """
    # The per-step gold set (docs/sme_stage_cases.csv) is owned by oppp.eval.per_step;
    # reuse its loader so `oppp eval` reads `nl query` / `counts` from that file.
    from oppp.eval.per_step import load_perstep_cases

    svc = get_service(service)
    report = EvalReport(tolerance=tolerance)
    rows = load_perstep_cases()
    if limit:
        rows = rows[:limit]

    for idx, row in enumerate(rows, start=1):
        q = (row.get("nl query") or "").strip()
        if not q:
            continue
        result = run_pipeline(
            q,
            service,
            enhancer=enhancer,
            decomposer=decomposer,
            translator=translator,
            aggregator=aggregator,
            normalizer=normalizer,
        )
        cr = CaseResult(
            query_number=str(idx),
            question=q,
            ok=result.ok,
            expected=_parse_expected(row.get("counts", "")),
            issues=[i.message for i in result.issues],
        )
        if execute and result.ok and result.machine_query is not None:
            ex = execute_count(result.machine_query, svc)
            cr.executed = ex.ok
            cr.actual = ex.count_total
            cr.exec_error = ex.error
        report.cases.append(cr)
    return report


# --- report export ----------------------------------------------------------
CASE_COLUMNS = [
    "query_number",
    "question",
    "expected",
    "actual",
    "ok",
    "executed",
    "exact",
    "within_tol",
    "ratio",
    "issues",
    "exec_error",
]


def _case_row(c: CaseResult, tol: float) -> list:
    return [
        c.query_number,
        c.question,
        c.expected,
        c.actual,
        c.ok,
        c.executed,
        c.exact,
        c.within(tol),
        round(c.ratio, 4) if c.ratio is not None else None,
        "; ".join(c.issues),
        c.exec_error or "",
    ]


def _metric_rows(report: EvalReport) -> list[tuple[str, object]]:
    return [
        ("generated", time.strftime("%Y-%m-%d %H:%M:%S")),
        ("cases", len(report.cases)),
        ("tolerance", report.tolerance),
        ("valid_rate", round(report.valid_rate, 4)),
        ("executed_rate", round(report.executed_rate, 4)),
        ("exact_match_rate", round(report.exact_match_rate, 4)),
        ("within_tol_rate", round(report.within_tol_rate, 4)),
    ]


# Section titles that head the parameters / summary / cases blocks on top of the report.
_PARAMS_TITLE = "Parameters"
_SUMMARY_TITLE = "Summary"
_BOLD_FIRST_CELLS = {_PARAMS_TITLE, _SUMMARY_TITLE, CASE_COLUMNS[0]}


def _report_blocks(report: EvalReport, run_config: dict | None) -> list[list]:
    """The top-of-report rows: the run parameters, then the summary metrics.

    Returned as a list of row-lists so both the .xlsx and .csv writers lay the
    parameters used and the run summary *above* the per-case table.
    """
    blocks: list[list] = [[_PARAMS_TITLE]]
    for k, v in (run_config or {}).items():
        blocks.append([k, v])
    blocks.append([])
    blocks.append([_SUMMARY_TITLE])
    for k, v in _metric_rows(report):
        blocks.append([k, v])
    blocks.append([])
    return blocks


def write_report(report: EvalReport, path: str | Path, run_config: dict | None = None) -> Path:
    """Write the eval report to ``path``. Format from the extension (default ``.xlsx``).

    The report is a single sheet: the **parameters used** and the **run summary** on
    top, then the per-case table. ``.xlsx`` (the default — a bare path with no suffix
    becomes ``.xlsx``) needs the optional ``openpyxl`` dependency
    (``pip install -e '.[report]'``); ``.csv`` uses the stdlib. Creates the parent
    directory if needed. Raises ``ValueError`` on an unsupported extension and
    ``RuntimeError`` if ``.xlsx`` is requested without ``openpyxl`` installed.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == "":  # default to Excel when no extension is given
        path = path.with_suffix(".xlsx")
        suffix = ".xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)

    header_blocks = _report_blocks(report, run_config)
    case_rows = [_case_row(c, report.tolerance) for c in report.cases]

    if suffix == ".csv":
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            for row in header_blocks:
                w.writerow(row)
            w.writerow(CASE_COLUMNS)
            for row in case_rows:
                w.writerow(row)
    elif suffix == ".xlsx":
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except ImportError as e:  # pragma: no cover - optional extra
            raise RuntimeError(
                "Excel output needs the 'report' extra: pip install -e '.[report]' "
                "(or `pip install openpyxl`). Or write a .csv instead."
            ) from e
        wb = Workbook()
        ws = wb.active
        ws.title = "report"
        for row in header_blocks:
            ws.append(row)
        ws.append(CASE_COLUMNS)
        for row in case_rows:
            ws.append(row)
        # Bold the section titles and the case-table header.
        for r in ws.iter_rows():
            if r and r[0].value in _BOLD_FIRST_CELLS:
                for cell in r:
                    if cell.value is not None:
                        cell.font = Font(bold=True)
        ws.column_dimensions["A"].width = 16
        ws.column_dimensions["B"].width = 48
        wb.save(path)
    else:
        raise ValueError(f"unsupported report extension {suffix!r}; use .xlsx or .csv")
    return path
