"""RTB (Reaxys bioactivity / CrossFire) service configuration + serializer.

Designed-for service (Safety is the realised scope). RTB shares the decompose →
translate → aggregate pipeline shape, but its output surface differs: instead of a
JSON payload it emits a CrossFire `where_clause` string over `DAT.*` columns
(docs/03 → architecture: "Safety/PK emit JSON; RTB emits a where_clause string").
The field set and column names mirror utils/ppendium/prompts.py::
rtb_cross_fire_conversion_prompt, carried as data (CONST-12).
"""

from __future__ import annotations

from typing import Any

from oppp.models import Decomposition, MachineQuery
from oppp.services.base import FieldSpec, ServiceConfig, service_registry

# DAT.CATEG is a required, non-empty column; default to the PK bioassay category
# when the question does not pin one (the legacy prompt's most common category).
DEFAULT_CATEGORY = "Pharmacokinetic"

RTB_FIELDS: dict[str, FieldSpec] = {
    # --- closed-vocabulary (reuse the shared taxonomies); emit to DAT.* columns ---
    "drugs": FieldSpec(
        "drugs",
        "closed",
        taxonomy="drugs",
        value_field="DAT.MNAME",
        fuzzy_wildcard=True,
    ),
    "species": FieldSpec("species", "closed", taxonomy="species", value_field="DAT.BSPECIE"),
    "route": FieldSpec("route", "closed", taxonomy="route", value_field="DAT.MROUTE"),
    # --- open / free-text columns ---
    "parameter": FieldSpec("parameter", "open", value_field="DAT.VTYPE"),
    "model": FieldSpec("model", "open", value_field="DAT.MODEL"),
    "cellLine": FieldSpec("cellLine", "open", value_field="DAT.BCELL"),
    "tissue": FieldSpec("tissue", "open", value_field="MEASLOC.TISSUE"),
    "regimen": FieldSpec("regimen", "open", value_field="DAT.MREGIM"),
    # --- required enum ---
    "category": FieldSpec(
        "category",
        "enum",
        value_field="DAT.CATEG",
        enum_values=[
            "In vitro (efficacy)",
            "In vivo (animal models)",
            "Metabolism/transport",
            "Pharmacokinetic",
            "Toxicity/safety pharmacology",
        ],
    ),
}

# RTB returns a where_clause, not faceted JSON — no facet surface.
RTB_FACETS: set[str] = set()

RTB_TERMITE_MAP = {
    "DRUG": "drugs",
    "SPECIES": "species",
    "ROUTE": "route",
    "PARAMETER": "parameter",
}


def _rtb_invariants(mq: MachineQuery, decomp: Decomposition) -> MachineQuery:
    """Ensure the required DAT.CATEG column is present (it cannot be empty)."""
    base = mq.query
    if not base or "DAT.CATEG" in str(base):
        return mq
    categ = {"MATCH": {"field": "DAT.CATEG", "value": DEFAULT_CATEGORY}}
    if "AND" in base and isinstance(base["AND"], list):
        new_query = {"AND": [*base["AND"], categ]}
    else:
        new_query = {"AND": [base, categ]}
    return mq.model_copy(update={"query": new_query})


@service_registry.register("rtb")
def build_rtb() -> ServiceConfig:
    return ServiceConfig(
        name="rtb",
        search_url="https://api-dev.ppnp.cm-elsevier.com/v1/rtb/search/advanced",
        fields=RTB_FIELDS,
        facet_allow_list=RTB_FACETS,
        termite_type_map=RTB_TERMITE_MAP,
        invariants=_rtb_invariants,
    )


# ---------------------------------------------------------------------------
# CrossFire where_clause serializer — the RTB output surface.
# ---------------------------------------------------------------------------
def _literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _render(node: dict[str, Any]) -> str:
    ((op, body),) = node.items()
    if op == "MATCH":
        col, value = body["field"], body["value"]
        if isinstance(value, list):
            if len(value) == 1:
                return f"{col}={_literal(value[0])}"
            return "(" + " OR ".join(f"{col}={_literal(v)}" for v in value) + ")"
        return f"{col}={_literal(value)}"
    if op in ("AND", "OR"):
        return "(" + f" {op} ".join(_render(child) for child in body) + ")"
    if op == "NOT":
        return f"NOT ({_render(body)})"
    if op == "RANGE":
        col = body["field"]
        parts = []
        if body.get("min") is not None:
            parts.append(f"{col}>={body['min']}")
        if body.get("max") is not None:
            parts.append(f"{col}<={body['max']}")
        return "(" + " AND ".join(parts) + ")" if len(parts) > 1 else (parts[0] if parts else "")
    if op == "REGEX":
        pattern = body.get("pattern") or ""
        return f"{body['field']} LIKE {_literal('%' + pattern + '%')}"
    if op == "EMPTY":
        return f"{body['field']} IS NULL"
    return ""


def where_clause(machine_query: MachineQuery) -> str:
    """Serialize an assembled RTB machine query to a CrossFire `where_clause` string.

    The top-level boolean is flattened (no enclosing parentheses) to match the
    legacy CrossFire output; nested groups keep their parentheses.
    """
    query = machine_query.query
    if not query:
        return ""
    ((op, body),) = query.items()
    if op in ("AND", "OR") and isinstance(body, list):
        return f" {op} ".join(_render(child) for child in body)
    return _render(query)
