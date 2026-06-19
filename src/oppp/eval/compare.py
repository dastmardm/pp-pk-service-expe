"""Gold-vs-agent filter comparison for a single SME case.

Used by `oppp run --case N` to put the agent's per-field filters next to the
values the SME recorded in inputs/sme_expected_cases.csv, so they can be eyeballed
side by side.
"""

from __future__ import annotations

import re

from oppp.eval.harness import load_gold_cases
from oppp.models import Operator, PipelineResult
from oppp.services.base import ServiceConfig

# gold CSV column -> logical field name
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
    "concomitants": "concomitants",
}
_EMPTY = {"", "empty", "none", "n/a", "na"}


def find_gold_case(number: int) -> dict | None:
    target = str(number)
    for row in load_gold_cases():
        if (row.get("query_number") or "").strip() == target:
            return row
    return None


def _norm_set(cell: str) -> set[str]:
    if not cell or cell.strip().lower() in _EMPTY:
        return set()
    cell = re.sub(r"\b(AND|OR)\b", ";", cell)
    cell = cell.replace("(", " ").replace(")", " ")
    return {
        p.strip().lower().rstrip("*")
        for p in re.split(r"[;,]", cell)
        if p.strip() and p.strip().lower() not in _EMPTY
    }


def gold_filters(row: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for col, logical in GOLD_FIELD_MAP.items():
        val = (row.get(col) or "").strip()
        if val and val.lower() not in _EMPTY:
            out[logical] = val
    return out


def _value_repr(sq) -> str:
    if sq.operator is Operator.REGEX:
        return f"~regex {sq.pattern}"
    if sq.operator in (Operator.RANGE, Operator.DATE_RANGE):
        return f"{sq.operator.value} {sq.value}"
    if isinstance(sq.value, list):
        return "; ".join(str(v) for v in sq.value)
    return str(sq.value)


def agent_filters(result: PipelineResult, service: ServiceConfig) -> dict[str, str]:
    reverse = {spec.emit_field: name for name, spec in service.fields.items()}
    out: dict[str, list[str]] = {}
    for sq in result.subqueries:
        logical = reverse.get(sq.field, sq.field)
        out.setdefault(logical, []).append(_value_repr(sq))
    return {k: " | ".join(v) for k, v in out.items()}


def _status(gold: str | None, agent: str | None) -> str:
    if gold and not agent:
        return "MISSING"  # gold expects a filter the agent did not produce
    if agent and not gold:
        return "EXTRA"  # agent produced a filter not in gold
    g, a = _norm_set(gold or ""), _norm_set(agent or "")
    if g == a:
        return "match"
    if g & a:
        return "partial"
    return "DIFF"


def compare_rows(result: PipelineResult, row: dict, service: ServiceConfig):
    """Return [(field, status, gold, agent)] over the union of fields."""
    gold = gold_filters(row)
    agent = agent_filters(result, service)
    # questions aren't filters; show them so 'missing' gold filters aren't confused
    questions = {c.field for c in result.decomposition.questions}
    rows = []
    for field in sorted(set(gold) | set(agent)):
        g = gold.get(field)
        a = agent.get(field)
        if a is None and field in questions:
            a = "(question → facet/display, not a filter)"
        rows.append((field, _status(g, a), g or "", a or ""))
    return rows
