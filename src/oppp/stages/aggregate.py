"""Stage 3 — aggregation. Machine subqueries -> one final machine query.

Pluggable by backend (same interface), so it can be swapped and isolated:
  * llm (default) — an LLM reads the decomposition (the user's intent) plus every
    machine subquery and decides the *structure* (how to combine values within a
    field and how to combine fields). The concrete constraint JSON is then
    rendered and validated deterministically, so the output is always legal.
  * deterministic — OFFLINE double: build the boolean tree from per-field groups
    and a default cross-field AND. No LLM; used by the test suite and per-stage
    evaluation.

Both share entity-filter routing, facet/displayColumn extraction, budget
collapsing, service invariants, and validation.
"""

from __future__ import annotations

from typing import Any, Protocol

from oppp.models import (
    AggregationPlan,
    BooleanOp,
    ComponentType,
    Decomposition,
    MachineQuery,
    MachineSubquery,
    Operator,
    ValidationIssue,
)
from oppp.registry import Registry
from oppp.services.base import ServiceConfig

_VALID_TOP = {o.value for o in Operator}
# PharmaPendium rejects queries above this many constraints (one per MATCH value).
MAX_CONSTRAINTS = 20


class Aggregator(Protocol):
    def aggregate(
        self, decomp: Decomposition, subqueries: list[MachineSubquery], service: ServiceConfig
    ) -> tuple[MachineQuery, list[ValidationIssue]]: ...


aggregator_registry: Registry[Aggregator] = Registry("aggregator")


def get_aggregator(name: str = "llm", **kwargs) -> Aggregator:
    return aggregator_registry.create(name, **kwargs)


def _finalize(
    decomp: Decomposition,
    subqueries: list[MachineSubquery],
    service: ServiceConfig,
    query: dict[str, Any],
    issues: list[ValidationIssue],
    *,
    outputs: tuple[list[str], list[str]] | None = None,
) -> tuple[MachineQuery, list[ValidationIssue]]:
    """Shared tail for every aggregator: entity routing, outputs, invariants, validate.

    `query` is the already-built boolean tree (each backend builds it its own way);
    `outputs` optionally overrides the (facets, displayColumns) derivation.
    """
    entity = [s for s in subqueries if s.entity_name]
    entity_filters = [{s.entity_name: s.to_constraint()} for s in entity]
    facets, display = outputs if outputs is not None else _outputs(decomp, service)

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


def _drop_ungroundable(
    subqueries: list[MachineSubquery], issues: list[ValidationIssue]
) -> list[MachineSubquery]:
    """Remove subqueries Stage 2 flagged ``dropped`` (ungroundable closed-vocab terms).

    Such a constraint has no in-vocabulary value, so emitting it as a hard MATCH
    would zero the whole query (CONST-1). It is excluded from the boolean tree,
    entity routing, and the budget count alike; the gap is surfaced as a warning so
    the dropped filter is visible rather than silently absent.
    """
    kept: list[MachineSubquery] = []
    for s in subqueries:
        if s.dropped:
            issues.append(
                ValidationIssue(
                    level="warning",
                    message=(
                        f"dropped ungroundable {s.field} filter {s.value!r} "
                        "(no matching vocabulary value); it does not constrain the query"
                    ),
                )
            )
        else:
            kept.append(s)
    return kept


def aggregate(
    decomp: Decomposition,
    subqueries: list[MachineSubquery],
    service: ServiceConfig,
) -> tuple[MachineQuery, list[ValidationIssue]]:
    """Deterministic aggregation core (the `deterministic` backend / offline double)."""
    issues: list[ValidationIssue] = []
    subqueries = _drop_ungroundable(subqueries, issues)
    _apply_budget(subqueries, issues)
    top = [s for s in subqueries if not s.entity_name]
    return _finalize(decomp, subqueries, service, _build_tree(top), issues)


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
        issues.append(
            ValidationIssue(
                level="warning",
                message=(
                    f"budget: collapsed {sq.field} rollup ({sq.value_count()} terms) "
                    f"to '{sq.collapse_to}' to fit the {MAX_CONSTRAINTS}-constraint API limit"
                ),
            )
        )
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
            ValidationIssue(
                level="error", message=f"query must have exactly one top key, got {list(q)}"
            )
        )
    else:
        _validate_node(q, issues)

    for f in mq.facets:
        if f not in service.facet_allow_list:
            issues.append(ValidationIssue(level="error", message=f"facet '{f}' not in allow-list"))
    return issues


def _validate_node(node: dict, issues: list[ValidationIssue]) -> None:
    if not isinstance(node, dict) or len(node) != 1:
        issues.append(ValidationIssue(level="error", message=f"malformed constraint: {node}"))
        return
    ((op, body),) = node.items()
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


# ---------------------------------------------------------------------------
# Pluggable aggregators
# ---------------------------------------------------------------------------
class DeterministicAggregator:
    """Offline double — assembles the tree from per-field groups + cross-field AND."""

    def aggregate(self, decomp, subqueries, service):
        return aggregate(decomp, subqueries, service)


aggregator_registry.add("deterministic", lambda **kw: DeterministicAggregator(**kw))


def _render_tree_from_plan(top: list[MachineSubquery], plan: AggregationPlan) -> dict[str, Any]:
    """Build the boolean tree from top-level subqueries per the LLM's plan.

    Defensive: the plan only steers structure. Fields it omits fall back to the
    subquery's own boolean-group op (or OR), so a partial/garbled plan still
    yields a valid tree.
    """
    by_field: dict[str, list[MachineSubquery]] = {}
    for sq in top:
        by_field.setdefault(sq.field, []).append(sq)
    plan_by_field = {fc.field: fc for fc in plan.fields}

    constraints: list[dict] = []
    for fieldname, members in by_field.items():
        fc = plan_by_field.get(fieldname)
        # op precedence: explicit plan > subquery boolean-group > default OR
        group_op = next((m.boolean_group.op for m in members if m.boolean_group), None)
        op = (fc.op if fc else None) or group_op or BooleanOp.OR
        rendered = [m.to_constraint() for m in members]
        node = rendered[0] if len(rendered) == 1 else {op.value: rendered}
        if fc and fc.negate:
            node = {"NOT": node}
        constraints.append(node)

    if not constraints:
        return {}
    if len(constraints) == 1:
        return constraints[0]
    return {plan.top_op.value: constraints}


class LLMAggregator:
    """Default — an LLM decides the combination structure; code renders + validates.

    Lazy: the chat model is built on first use, so importing this stage needs no
    creds. If the LLM call fails the planner falls back to a deterministic plan so
    a query is still produced.
    """

    def __init__(self, model: str | None = None) -> None:
        self._model = model
        self._structured = None

    def _plan(self, decomp: Decomposition, top: list[MachineSubquery]) -> AggregationPlan:
        from oppp.llm import structured

        if self._structured is None:
            self._structured = structured(AggregationPlan, model=self._model)
        lines = []
        for sq in top:
            grp = f" [group:{sq.boolean_group.op.value}]" if sq.boolean_group else ""
            lines.append(f"- field={sq.field} op={sq.operator.value} value={sq.value!r}{grp}")
        questions = ", ".join(f"{c.field}({c.nl_fragment})" for c in decomp.questions) or "(none)"
        prompt = (
            "Assemble a machine query from already-translated field constraints. "
            "Decide ONLY the boolean structure — do not change any field values.\n\n"
            f"User question: {decomp.query!r}\n"
            f"Reported (question) fields: {questions}\n"
            "Translated subqueries (one per line):\n"
            + "\n".join(lines)
            + "\n\nReturn an AggregationPlan: for each field set op (OR if the user lists "
            "alternatives like 'X or Y', AND if all must hold) and negate=true only if the "
            "user explicitly excludes it; set top_op for how fields combine (usually AND); "
            "and optionally facets/display_columns for the reported fields."
        )
        return self._structured.invoke(prompt)  # type: ignore[return-value]

    def aggregate(self, decomp, subqueries, service):
        issues: list[ValidationIssue] = []
        subqueries = _drop_ungroundable(subqueries, issues)
        _apply_budget(subqueries, issues)
        top = [s for s in subqueries if not s.entity_name]

        try:
            plan = self._plan(decomp, top)
        except Exception as e:  # pragma: no cover - fall back to deterministic structure
            issues.append(
                ValidationIssue(
                    level="warning",
                    message=f"llm aggregator fell back to deterministic structure: {e}",
                )
            )
            return _finalize(decomp, subqueries, service, _build_tree(top), issues)

        query = _render_tree_from_plan(top, plan)
        # Honour plan outputs only if valid; otherwise derive deterministically.
        det_facets, det_display = _outputs(decomp, service)
        facets = [f for f in plan.facets if f in service.facet_allow_list] or det_facets
        display = plan.display_columns or det_display
        return _finalize(decomp, subqueries, service, query, issues, outputs=(facets, display))


aggregator_registry.add("llm", lambda **kw: LLMAggregator(**kw))
