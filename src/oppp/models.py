"""Pydantic contracts shared across all stages.

These are the typed boundaries the design mandates (docs/06-implementation):
every LLM step emits one of these validated objects rather than free text, and
every stage hands the next a typed value.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ComponentType(StrEnum):
    """How a decomposed component is used (docs/03/stage-1)."""

    FILTER = "filter"  # -> becomes a machine subquery, constrains retrieval
    QUESTION = "question"  # -> answered over the retrieved records (facet/display)


class Operator(StrEnum):
    """Machine-query constraint types (docs/02/machine-query-schema)."""

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
    """Marks several same-field components that must combine with one operator."""

    id: str
    op: BooleanOp = BooleanOp.OR


# ---------------------------------------------------------------------------
# Stage 1 output
# ---------------------------------------------------------------------------
class Component(BaseModel):
    """One single-field fragment produced by decomposition (Stage 1)."""

    field: str
    nl_fragment: str
    type: ComponentType
    reason: str = Field(description="One-sentence justification for field+type.")
    source: str = "llm"  # e.g. "termite:DRUG" | "gazetteer:species" | "llm"
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
    name: str  # preferred label sent to the API
    id: str | None = None
    parent_id: str | None = None
    parent_name: str | None = None
    score: float = 1.0
    match: str = "exact"  # exact | fuzzy | phonetic | termite | expand
    count: int | None = None


class Grounding(BaseModel):
    matched: list[GroundingHit] = Field(default_factory=list)
    expanded_from: str | None = None  # "class" | "term" | None
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Stage 2 output
# ---------------------------------------------------------------------------
class MachineSubquery(BaseModel):
    """A single filter: (operator, field, value). The atom of the machine query."""

    field: str
    operator: Operator = Operator.MATCH
    value: Any = None  # str | list[str] | {min,max} | bool depending on operator
    pattern: str | None = None  # for REGEX
    boolean_group: BooleanGroup | None = None
    entity_name: str | None = None  # if set, Stage 3 routes via entityFilters
    collapse_to: str | None = None  # canonical term to fall back to under API budget
    grounding: Grounding | None = None
    notes: str | None = None

    def value_count(self) -> int:
        """How many API constraints this filter contributes (one per MATCH value)."""
        if self.operator is Operator.MATCH:
            return len(self.value) if isinstance(self.value, list) else 1
        return 1

    def to_constraint(self) -> dict[str, Any]:
        """Serialize this single filter to the API constraint shape."""
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
        # MATCH (default)
        return {"MATCH": {"field": self.field, "value": self.value}}


# ---------------------------------------------------------------------------
# Stage 3 output
# ---------------------------------------------------------------------------
class MachineQuery(BaseModel):
    """The final request body posted to the PharmaPendium API."""

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
    level: str  # "error" | "warning"
    message: str


class PipelineResult(BaseModel):
    """Everything one full run produced — auditable end to end."""

    query: str
    service: str
    decomposition: Decomposition
    subqueries: list[MachineSubquery] = Field(default_factory=list)
    machine_query: MachineQuery | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.machine_query is not None and not any(
            i.level == "error" for i in self.issues
        )
