"""Evaluation over the SME gold set (inputs/sme_expected_cases.csv).

The metric is **result-count accuracy**: each gold row carries an expected number
of matching records in column `s`. We translate the question, execute the machine
query against the PharmaPendium API, read `countTotal`, and compare it to `s`.

Reported: how often the query is valid, how often it executes, exact-count match
rate, and within-tolerance rate (counts drift as the DB updates, so a tolerance
band is the realistic signal).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field

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
        return self.expected is not None and self.actual is not None and self.expected == self.actual

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
    """Run each gold question and compare executed `countTotal` to expected `s`.

    Defaults to the offline doubles (gazetteer + deterministic) so the harness is
    cheap and hermetic; pass decomposer='llm'/aggregator='llm' to evaluate the
    production pipeline. `execute=False` skips the API call: only validity is measured.
    """
    svc = get_service(service)
    report = EvalReport(tolerance=tolerance)
    rows = load_gold_cases()
    if limit:
        rows = rows[:limit]

    for row in rows:
        q = row.get("question", "").strip()
        if not q:
            continue
        result = run_pipeline(
            q, service, enhancer=enhancer, decomposer=decomposer,
            translator=translator, aggregator=aggregator, normalizer=normalizer,
        )
        cr = CaseResult(
            query_number=row.get("query_number", "?"),
            question=q,
            ok=result.ok,
            expected=_parse_expected(row.get("s", "")),
            issues=[i.message for i in result.issues],
        )
        if execute and result.ok and result.machine_query is not None:
            ex = execute_count(result.machine_query, svc)
            cr.executed = ex.ok
            cr.actual = ex.count_total
            cr.exec_error = ex.error
        report.cases.append(cr)
    return report
