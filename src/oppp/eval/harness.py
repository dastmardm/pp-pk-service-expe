"""Evaluation over the SME gold set (inputs/sme_expected_cases.csv).

The gold set is already per-field, so we score per field (docs/05). Layers:
  * routing — did we produce a filter for each gold field?
  * value   — overlap (P/R/F1) between predicted and expected value sets.

This is a pragmatic harness over messy cells (';'-separated, inline AND/()).
Each stage is isolatable, so this can also be pointed at a single stage later.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field

from oppp.config import get_settings
from oppp.models import Operator
from oppp.pipeline import run_pipeline

# gold CSV column -> our logical field name
GOLD_FIELD_MAP = {
    "drugsFuzzy": "drugs",
    "indications": "indications",
    "targets": "targets",
    "species": "species",
    "effects": "effects",
    "parameterComment": "parameterComment",
    "toxicityParameter": "toxicityParameter",
    "doseType": "doseType",
    "route": "route",
    "ages": "ages",
    "sex": "sex",
    "studyGroup": "studyGroup",
    "isPreclinical": "isPreclinical",
}
_EMPTY = {"", "empty", "none", "n/a", "na"}


def _split_values(cell: str) -> set[str]:
    """Best-effort split of a messy gold cell into a value set."""
    if not cell or cell.strip().lower() in _EMPTY:
        return set()
    cell = re.sub(r"\b(AND|OR)\b", ";", cell)
    cell = cell.replace("(", " ").replace(")", " ")
    parts = re.split(r"[;,]", cell)
    return {p.strip().lower() for p in parts if p.strip() and p.strip().lower() not in _EMPTY}


def _prf(pred: set[str], gold: set[str]) -> tuple[float, float, float]:
    if not gold and not pred:
        return 1.0, 1.0, 1.0
    if not gold or not pred:
        return 0.0, 0.0, 0.0
    tp = len(pred & gold)
    p = tp / len(pred)
    r = tp / len(gold)
    f = 0.0 if (p + r) == 0 else 2 * p * r / (p + r)
    return p, r, f


@dataclass
class CaseResult:
    query_number: str
    question: str
    ok: bool
    issues: list[str] = field(default_factory=list)
    per_field: dict[str, dict[str, float]] = field(default_factory=dict)
    routing_recall: float = 0.0


@dataclass
class EvalReport:
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def valid_rate(self) -> float:
        return _mean([1.0 if c.ok else 0.0 for c in self.cases])

    @property
    def routing_recall(self) -> float:
        return _mean([c.routing_recall for c in self.cases])

    def field_f1(self) -> dict[str, float]:
        acc: dict[str, list[float]] = {}
        for c in self.cases:
            for fname, m in c.per_field.items():
                acc.setdefault(fname, []).append(m["f1"])
        return {k: _mean(v) for k, v in sorted(acc.items())}

    @property
    def macro_f1(self) -> float:
        f1s = self.field_f1()
        return _mean(list(f1s.values()))


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def load_gold_cases() -> list[dict]:
    path = get_settings().inputs_dir / "sme_expected_cases.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _predicted_values(result, logical_field: str) -> set[str]:
    out: set[str] = set()
    spec_emit = {
        "drugs": "drugsFuzzy",
    }.get(logical_field, logical_field)
    for sq in result.subqueries:
        if sq.field != spec_emit:
            continue
        if sq.operator is Operator.MATCH:
            vals = sq.value if isinstance(sq.value, list) else [sq.value]
            for v in vals:
                out.add(str(v).rstrip("*").strip().lower())
        elif sq.operator is Operator.REGEX and sq.pattern:
            for tok in re.findall(r"[A-Za-z][A-Za-z0-9\- ]+", sq.pattern):
                out.add(tok.strip().lower())
    return out


def evaluate(
    *, service: str = "safety", decomposer: str = "gazetteer", normalizer: str = "fuzzy",
    limit: int | None = None,
) -> EvalReport:
    report = EvalReport()
    rows = load_gold_cases()
    if limit:
        rows = rows[:limit]
    for row in rows:
        q = row.get("question", "").strip()
        if not q:
            continue
        result = run_pipeline(q, service, decomposer=decomposer, normalizer=normalizer)
        cr = CaseResult(
            query_number=row.get("query_number", "?"),
            question=q,
            ok=result.ok,
            issues=[i.message for i in result.issues],
        )
        gold_fields_present = 0
        routed = 0
        for gcol, logical in GOLD_FIELD_MAP.items():
            gold = _split_values(row.get(gcol, ""))
            if not gold:
                continue
            gold_fields_present += 1
            pred = _predicted_values(result, logical)
            if pred:
                routed += 1
            p, r, f = _prf(pred, gold)
            cr.per_field[logical] = {"precision": p, "recall": r, "f1": f}
        cr.routing_recall = routed / gold_fields_present if gold_fields_present else 1.0
        report.cases.append(cr)
    return report
