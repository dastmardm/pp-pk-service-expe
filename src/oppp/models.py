"""Pydantic contracts shared across all stages."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ComponentType(StrEnum):
    FILTER = "filter"
    QUESTION = "question"


class Operator(StrEnum):
    MATCH = "MATCH"
    OR = "OR"
    AND = "AND"
    NOT = "NOT"
    REGEX = "REGEX"
    RANGE = "RANGE"
    DATE_RANGE = "DATE_RANGE"
    EMPTY = "EMPTY"


class BooleanOp(StrEnum):
    AND = "AND"
    OR = "OR"


class BooleanGroup(BaseModel):
    id: str
    op: BooleanOp = BooleanOp.OR


# ---------------------------------------------------------------------------
# Stage 1 output
# ---------------------------------------------------------------------------
class Component(BaseModel):
    field: str
    nl_fragment: str
    type: ComponentType
    reason: str = Field(description="One-sentence justification for field+type.")
    source: str = "llm"
    boolean_group: BooleanGroup | None = None


class Decomposition(BaseModel):
    query: str
    service: str
    components: list[Component] = Field(default_factory=list)

    @property
    def filters(self) -> list[Component]:
        return [c for c in self.components if c.type is ComponentType.FILTER]

    @property
    def questions(self) -> list[Component]:
        return [c for c in self.components if c.type is ComponentType.QUESTION]


# ---------------------------------------------------------------------------
# Grounding / lookup
# ---------------------------------------------------------------------------
class GroundingHit(BaseModel):
    name: str
    id: str | None = None
    parent_id: str | None = None
    parent_name: str | None = None
    score: float = 1.0
    match: str = "exact"
    count: int | None = None


class Grounding(BaseModel):
    matched: list[GroundingHit] = Field(default_factory=list)
    expanded_from: str | None = None
    confidence: float = 1.0


class TermSelection(BaseModel):
    selected: list[str] = Field(default_factory=list)
    reason: str = Field(default="")


# ---------------------------------------------------------------------------
# Stage -1 — query expansion
# ---------------------------------------------------------------------------
class QueryExpansion(BaseModel):
    expanded: str = Field(description="The clarified, abbreviation-expanded question.")
    reason: str = Field(default="")


class ExpandedQuery(BaseModel):
    text: str
    original: str
    source: str = "noop"


# ---------------------------------------------------------------------------
# Stage 0 — enhancement
# ---------------------------------------------------------------------------
class EntityAnnotation(BaseModel):
    surface: str
    label: str
    entity_type: str | None = None
    synonyms: list[str] = Field(default_factory=list)


class EnhancedQuery(BaseModel):
    text: str
    annotations: list[EntityAnnotation] = Field(default_factory=list)
    source: str = "noop"


# ---------------------------------------------------------------------------
# Stage 3 — aggregation plan
# ---------------------------------------------------------------------------
class FieldCombine(BaseModel):
    field: str
    op: BooleanOp = BooleanOp.OR
    negate: bool = False


class AggregationPlan(BaseModel):
    top_op: BooleanOp = BooleanOp.AND
    fields: list[FieldCombine] = Field(default_factory=list)
    facets: list[str] = Field(default_factory=list)
    display_columns: list[str] = Field(default_factory=list)
    reason: str = ""


# ---------------------------------------------------------------------------
# Stage 2 output
# ---------------------------------------------------------------------------
class MachineSubquery(BaseModel):
    field: str
    operator: Operator = Operator.MATCH
    value: Any = None
    pattern: str | None = None
    boolean_group: BooleanGroup | None = None
    entity_name: str | None = None
    collapse_to: str | None = None
    grounding: Grounding | None = None
    notes: str | None = None
    dropped: bool = False

    def value_count(self) -> int:
        if self.operator is Operator.MATCH:
            return len(self.value) if isinstance(self.value, list) else 1
        return 1

    def to_constraint(self) -> dict[str, Any]:
        op = self.operator
        if op is Operator.REGEX:
            return {"REGEX": {"field": self.field, "pattern": self.pattern}}
        if op is Operator.RANGE:
            rng: dict[str, Any] = {"field": self.field}
            if isinstance(self.value, dict):
                rng.update({k: v for k, v in self.value.items() if v is not None})
            return {"RANGE": rng}
        if op is Operator.DATE_RANGE:
            dr: dict[str, Any] = {"field": self.field}
            if isinstance(self.value, dict):
                dr.update({k: v for k, v in self.value.items() if v is not None})
            return {"DATE_RANGE": dr}
        if op is Operator.EMPTY:
            return {"EMPTY": {"field": self.field}}
        return {"MATCH": {"field": self.field, "value": self.value}}


# ---------------------------------------------------------------------------
# Stage 3 output
# ---------------------------------------------------------------------------
class MachineQuery(BaseModel):
    query: dict[str, Any] = Field(default_factory=dict)
    entityFilters: list[dict[str, Any]] = Field(default_factory=list)
    facets: list[str] = Field(default_factory=list)
    displayColumns: list[str] = Field(default_factory=list)
    sortColumns: list[dict[str, Any]] = Field(default_factory=list)
    leafOnly: bool = False

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": self.query}
        if self.entityFilters:
            payload["entityFilters"] = self.entityFilters
        if self.facets:
            payload["facets"] = self.facets
        if self.displayColumns:
            payload["displayColumns"] = self.displayColumns
        if self.sortColumns:
            payload["sortColumns"] = self.sortColumns
        payload["leafOnly"] = self.leafOnly
        return payload


class ValidationIssue(BaseModel):
    level: str
    message: str


# ---------------------------------------------------------------------------
# Execution results
# ---------------------------------------------------------------------------
class ExecutionResult(BaseModel):
    ok: bool
    count_total: int | None = None
    status: int | None = None
    error: str | None = None


class RowExecutionResult(BaseModel):
    ok: bool
    count_total: int | None = None
    datapoints: list[dict[str, Any]] = Field(default_factory=list)
    status: int | None = None
    error: str | None = None
    page_state: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Runtime post-filtering contracts
# ---------------------------------------------------------------------------
class RuntimeClosedSet(BaseModel):
    field: str
    values: list[str] = Field(default_factory=list)


class PostFilterResult(BaseModel):
    field: str
    pool: str
    runtime_closed_set: list[str] = Field(default_factory=list)
    selected: list[str] = Field(default_factory=list)
    valid: bool = True
    reason: str = ""


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------
class PipelineResult(BaseModel):
    query: str
    service: str
    expanded: ExpandedQuery | None = None
    enhanced: EnhancedQuery | None = None
    decomposition: Decomposition
    subqueries: list[MachineSubquery] = Field(default_factory=list)
    machine_query: MachineQuery | None = None
    execution: ExecutionResult | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    # Row-mode fields (populated when fetch_rows=True)
    row_execution: RowExecutionResult | None = None
    runtime_closed_sets: list[RuntimeClosedSet] = Field(default_factory=list)
    runtime_translations: list[PostFilterResult] = Field(default_factory=list)
    filtered_datapoints: list[dict[str, Any]] = Field(default_factory=list)
    final_filtered_count: int | None = None

    @property
    def ok(self) -> bool:
        return self.machine_query is not None and not any(i.level == "error" for i in self.issues)
