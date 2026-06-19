"""Safety service configuration (the gold set is Safety-centric).

Mirrors the field set and rules in
utils/ppendium/prompts.py::pp_base_safety_translation, but as data.
"""

from __future__ import annotations

from oppp.models import Decomposition, MachineQuery
from oppp.services.base import FieldSpec, ServiceConfig, service_registry

SAFETY_FIELDS: dict[str, FieldSpec] = {
    # --- closed-vocabulary (CSV-backed) ---
    "drugs": FieldSpec(
        "drugs",
        "closed",
        taxonomy="drugs",
        value_field="drugsFuzzy",
        fuzzy_wildcard=True,
        facetable=True,
        display_column="drug",
    ),
    "effects": FieldSpec(
        "effects",
        "closed",
        taxonomy="effects",
        facetable=True,
        display_column="effect",
        rollup_to_siblings=True,  # MedDRA rollup: neutropenia -> its PT family
    ),
    "species": FieldSpec(
        "species",
        "closed",
        taxonomy="species",
        facetable=True,
        display_column="specie",
    ),
    "route": FieldSpec(
        "route",
        "closed",
        taxonomy="route",
        facetable=True,
        display_column="route",
    ),
    "toxicityParameter": FieldSpec(
        "toxicityParameter",
        "closed",
        taxonomy="toxicity_parameters",
        display_column="toxicityParameter",
    ),
    "documentSource": FieldSpec(
        "documentSource",
        "closed",
        taxonomy="sources",
        facetable=True,
        display_column="source",
    ),
    "doseType": FieldSpec(
        "doseType",
        "closed",
        taxonomy="dose_type",
        facetable=True,
        display_column="doseType",
    ),
    "documentYear": FieldSpec(
        "documentYear",
        "closed",
        taxonomy="document_year",
        facetable=True,
        display_column="documentYear",
    ),
    # closed-vocab but routed via a linked entity
    "indications": FieldSpec(
        "indications",
        "closed",
        taxonomy="indications",
        entity_name="DrugsIndications",
    ),
    # taxonomy not shipped yet (docs open question) -> best-effort, via entity
    "targets": FieldSpec("targets", "open", entity_name="DrugsTargets"),
    # --- open / free-text ---
    "parameterComment": FieldSpec("parameterComment", "open", display_column="parameterComment"),
    "studyGroup": FieldSpec("studyGroup", "open"),
    "ages": FieldSpec("ages", "open"),
    "dose": FieldSpec("dose", "open", display_column="dose"),
    # --- small enums / boolean ---
    "sex": FieldSpec("sex", "enum", enum_values=["Male", "Female", "Both"]),
    "isPreclinical": FieldSpec("isPreclinical", "boolean"),
}

SAFETY_FACETS = {"drugs", "species", "sources", "effects", "route", "doseType", "documentYear"}

SAFETY_TERMITE_MAP = {
    "DRUG": "drugs",
    "SPECIES": "species",
    "ROUTE": "route",
    "ADVERSE_EVENT": "effects",
    "TOXICITY_PARAMETER": "toxicityParameter",
    "INDICATION": "indications",
    "TARGET": "targets",
    "AGE": "ages",
}


def _safety_invariants(mq: MachineQuery, decomp: Decomposition) -> MachineQuery:
    # Safety has no always-on filter invariants (unlike PK's concomitants rule).
    # Hook kept for parity and future rules.
    return mq


@service_registry.register("safety")
def build_safety() -> ServiceConfig:
    return ServiceConfig(
        name="safety",
        search_url="https://api-dev.ppnp.cm-elsevier.com/v1/safety/search/advanced",
        fields=SAFETY_FIELDS,
        facet_allow_list=SAFETY_FACETS,
        termite_type_map=SAFETY_TERMITE_MAP,
        invariants=_safety_invariants,
    )
