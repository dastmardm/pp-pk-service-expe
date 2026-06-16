"""Stage 3 — aggregation. Machine subqueries -> one final machine query.

Deterministic assembly: build the boolean tree (honouring per-field groups and a
default cross-field AND), route entity filters, attach facets/displayColumns from
the QUESTION components, apply service invariants, then validate.
"""

from __future__ import annotations

from typing import Any

from oppp.models import (
    BooleanOp,
    ComponentType,
    Decomposition,
    MachineQuery,
    MachineSubquery,
    Operator,
    ValidationIssue,
)
from oppp.services.base import ServiceConfig

_VALID_TOP = {o.value for o in Operator}
# PharmaPendium rejects queries above this many constraints (one per MATCH value).
MAX_CONSTRAINTS = 20


def aggregate(
    decomp: Decomposition,
    subqueries: list[MachineSubquery],
    service: ServiceConfig,
) -> tuple[MachineQuery, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    _apply_budget(subqueries, issues)

    top: list[MachineSubquery] = [s for s in subqueries if not s.entity_name]
    entity: list[MachineSubquery] = [s for s in subqueries if s.entity_name]

    query = _build_tree(top)
    entity_filters = [{s.entity_name: s.to_constraint()} for s in entity]
    facets, display = _outputs(decomp, service)

    mq = MachineQuery(
        query=query,
        entityFilters=entity_filters,
        facets=facets,
        displayColumns=display,
    )
    if service.invariants is not None:
        mq = service.invariants(mq, decomp)

    issues.extend(validate(mq, service))
    return mq, issues


def _apply_budget(subqueries: list[MachineSubquery], issues: list[ValidationIssue]) -> None:
    """Keep the query within the API constraint budget.

    Each MATCH value counts as one constraint. A MedDRA rollup can push a query
    over the limit (e.g. neutropenia+cytopenia families = 26 values), which the
    API rejects. Collapse rolled-up families (largest first) back to their
    canonical term until under budget, recording a warning so the loss of breadth
    is visible rather than silent.
    """
    total = sum(s.value_count() for s in subqueries)
    if total <= MAX_CONSTRAINTS:
        return
    collapsible = sorted(
        (s for s in subqueries if s.collapse_to and s.value_count() > 1),
        key=lambda s: s.value_count(),
        reverse=True,
    )
    for sq in collapsible:
        if total <= MAX_CONSTRAINTS:
            break
        freed = sq.value_count() - 1
        issues.append(ValidationIssue(
            level="warning",
            message=(
                f"budget: collapsed {sq.field} rollup ({sq.value_count()} terms) "
                f"to '{sq.collapse_to}' to fit the {MAX_CONSTRAINTS}-constraint API limit"
            ),
        ))
        sq.value = sq.collapse_to
        if sq.grounding:
            sq.grounding.expanded_from = None
        sq.collapse_to = None
        total -= freed


def _build_tree(subqueries: list[MachineSubquery]) -> dict[str, Any]:
    groups: dict[str, tuple[BooleanOp, list[dict]]] = {}
    standalone: list[dict] = []
    for sq in subqueries:
        if sq.boolean_group is not None:
            op, members = groups.setdefault(sq.boolean_group.id, (sq.boolean_group.op, []))
            members.append(sq.to_constraint())
        else:
            standalone.append(sq.to_constraint())

    constraints: list[dict] = list(standalone)
    for op, members in groups.values():
        if len(members) == 1:
            constraints.append(members[0])
        else:
            constraints.append({op.value: members})

    if not constraints:
        return {}
    if len(constraints) == 1:
        return constraints[0]
    return {"AND": constraints}


def _outputs(decomp: Decomposition, service: ServiceConfig) -> tuple[list[str], list[str]]:
    facets: list[str] = []
    display: list[str] = []
    for q in decomp.components:
        if q.type is not ComponentType.QUESTION:
            continue
        spec = service.spec(q.field)
        if spec is None:
            continue
        if q.field in {"dose", "doseType", "route"}:
            if spec.display_column and spec.display_column not in display:
                display.append(spec.display_column)
        else:
            facet = "sources" if q.field == "documentSource" else q.field
            if facet in service.facet_allow_list and facet not in facets:
                facets.append(facet)
    # If we are displaying per-record columns, include the drug column for context.
    if display and "drug" not in display:
        display.insert(0, "drug")
    return facets, display


def validate(mq: MachineQuery, service: ServiceConfig) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    q = mq.query
    if not q:
        issues.append(ValidationIssue(level="error", message="empty query (no filters produced)"))
    elif len(q) != 1:
        issues.append(
            ValidationIssue(level="error", message=f"query must have exactly one top key, got {list(q)}")
        )
    else:
        _validate_node(q, issues)

    for f in mq.facets:
        if f not in service.facet_allow_list:
            issues.append(
                ValidationIssue(level="error", message=f"facet '{f}' not in allow-list")
            )
    return issues


def _validate_node(node: dict, issues: list[ValidationIssue]) -> None:
    if not isinstance(node, dict) or len(node) != 1:
        issues.append(ValidationIssue(level="error", message=f"malformed constraint: {node}"))
        return
    (op, body), = node.items()
    if op not in _VALID_TOP:
        issues.append(ValidationIssue(level="error", message=f"unknown operator '{op}'"))
        return
    if op in ("AND", "OR"):
        if not isinstance(body, list) or len(body) < 2:
            issues.append(ValidationIssue(level="error", message=f"{op} needs >= 2 children"))
            return
        for child in body:
            _validate_node(child, issues)
    elif op == "NOT":
        if isinstance(body, dict) and len(body) == 1 and next(iter(body)) in _VALID_TOP:
            _validate_node(body, issues)
        else:
            _validate_node(body, issues) if isinstance(body, dict) else None
