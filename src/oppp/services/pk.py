"""PK (Pharmacokinetics) service configuration.

The pipeline shape is shared; only this data differs. Field set, buckets,
facet allow-list, and the always-on PK invariants live here as data (CONST-10).
"""

from __future__ import annotations

from oppp.models import Decomposition, MachineQuery
from oppp.services.base import EARLY_CONTRIBUTOR_THRESHOLD, FieldSpec, ServiceConfig, service_registry

PK_FIELDS: dict[str, FieldSpec] = {
    "drugs": FieldSpec(
        "drugs",
        "closed",
        taxonomy="drugs",
        value_field="drugsFuzzy",
        fuzzy_wildcard=True,
        facetable=True,
        display_column="drug",
    ),
    "species": FieldSpec(
        "species",
        "closed",
        taxonomy="species",
        facetable=True,
        display_column="specie",
    ),
    "routes": FieldSpec(
        "routes",
        "closed",
        taxonomy="route",
        facetable=True,
        display_column="route",
    ),
    "documentSource": FieldSpec(
        "documentSource",
        "closed",
        taxonomy="sources",
        facetable=True,
        display_column="source",
    ),
    "documentYear": FieldSpec(
        "documentYear",
        "closed",
        taxonomy="document_year",
        facetable=True,
        display_column="documentYear",
    ),
    "parameter": FieldSpec("parameter", "open", display_column="parameter"),
    "parameterDisplay": FieldSpec("parameterDisplay", "open"),
    "studyGroup": FieldSpec("studyGroup", "open"),
    "age": FieldSpec("age", "open"),
    "dose": FieldSpec("dose", "open", display_column="dose"),
    "duration": FieldSpec("duration", "open"),
    "sex": FieldSpec("sex", "enum", enum_values=["Male", "Female", "Both"]),
    "concomitants": FieldSpec("concomitants", "enum", enum_values=["Fed", "Fasted"]),
    "tissueSpecific": FieldSpec(
        "tissueSpecific",
        "enum",
        enum_values=["Not tissue-specific", "Tissue-specific"],
    ),
    "metabolitesEnantiomers": FieldSpec(
        "metabolitesEnantiomers",
        "enum",
        enum_values=["Not metabolites/enantiomers", "Metabolite", "Enantiomer"],
    ),
    "isPreclinical": FieldSpec("isPreclinical", "boolean"),
}

PK_FACETS = {
    "drugs",
    "species",
    "sources",
    "parameters",
    "concomitantsAndClasses",
    "routes",
    "concomitants",
    "studyGroup",
    "metabolitesEnantiomers",
    "tissueSpecific",
    "documentYear",
}

PK_TERMITE_MAP = {
    "DRUG": "drugs",
    "SPECIES": "species",
    "ROUTE": "routes",
    "PARAMETER": "parameter",
    "AGE": "age",
}

PK_INVARIANTS = [
    ("concomitants", "Fasted"),
    ("tissueSpecific", "Not tissue-specific"),
    ("metabolitesEnantiomers", "Not metabolites/enantiomers"),
]


def _pk_invariants(mq: MachineQuery, decomp: Decomposition) -> MachineQuery:
    """Apply PK always-on filters.

    Every PK query restricts concomitants to Fasted-or-empty, and defaults
    tissueSpecific and metabolitesEnantiomers unless the question overrides them.
    """
    base = mq.query
    if not base:
        return mq
    present = str(base)
    extra: list[dict] = []
    if "concomitants" not in present:
        extra.append(
            {
                "OR": [
                    {"MATCH": {"field": "concomitants", "value": "Fasted"}},
                    {"EMPTY": {"field": "concomitants"}},
                ]
            }
        )
    if "tissueSpecific" not in present:
        extra.append({"MATCH": {"field": "tissueSpecific", "value": "Not tissue-specific"}})
    if "metabolitesEnantiomers" not in present:
        extra.append(
            {"MATCH": {"field": "metabolitesEnantiomers", "value": "Not metabolites/enantiomers"}}
        )
    if not extra:
        return mq
    if "AND" in base and isinstance(base["AND"], list):
        new_query = {"AND": [*base["AND"], *extra]}
    else:
        new_query = {"AND": [base, *extra]}
    return mq.model_copy(update={"query": new_query})


@service_registry.register("pk")
def build_pk() -> ServiceConfig:
    return ServiceConfig(
        name="pk",
        search_url="https://api-dev.ppnp.cm-elsevier.com/v1/pk/search/advanced",
        fields=PK_FIELDS,
        facet_allow_list=PK_FACETS,
        termite_type_map=PK_TERMITE_MAP,
        invariants=_pk_invariants,
        early_contributor_threshold=EARLY_CONTRIBUTOR_THRESHOLD,
    )
