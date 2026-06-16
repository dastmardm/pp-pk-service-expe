"""Per-service configuration. The pipeline code is shared; services differ only
in this data (fields, buckets, facet allow-list, invariants, output mapping).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from oppp.models import Decomposition, MachineQuery
from oppp.registry import Registry

Bucket = str  # "closed" | "open" | "enum" | "boolean"


@dataclass
class FieldSpec:
    name: str  # logical field name used in decomposition
    bucket: Bucket
    taxonomy: str | None = None  # taxonomy index name (closed-vocab)
    value_field: str | None = None  # API field to emit (defaults to name)
    fuzzy_wildcard: bool = False  # append trailing '*' (drug-style broadening)
    entity_name: str | None = None  # route via entityFilters under this entity
    enum_values: list[str] = field(default_factory=list)
    facetable: bool = False
    display_column: str | None = None  # response column for displayColumns
    rollup_to_siblings: bool = False  # MedDRA-style: leaf -> parent's children

    @property
    def emit_field(self) -> str:
        return self.value_field or self.name


@dataclass
class ServiceConfig:
    name: str
    search_url: str
    fields: dict[str, FieldSpec]
    facet_allow_list: set[str] = field(default_factory=set)
    termite_type_map: dict[str, str] = field(default_factory=dict)
    invariants: Callable[[MachineQuery, Decomposition], MachineQuery] | None = None

    def spec(self, field_name: str) -> FieldSpec | None:
        return self.fields.get(field_name)

    def closed_fields(self) -> list[str]:
        return [n for n, s in self.fields.items() if s.bucket == "closed" and s.taxonomy]


service_registry: Registry[ServiceConfig] = Registry("service")


def get_service(name: str) -> ServiceConfig:
    return service_registry.create(name)
