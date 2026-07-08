"""Offline tests for the PK service config.

The PK service is the active service; these tests verify its 16-field schema,
EARLY_CONTRIBUTOR_THRESHOLD, invariants, and facet allow-list.
"""

from oppp.pipeline import run_pipeline
from oppp.services.base import EARLY_CONTRIBUTOR_THRESHOLD, get_service, service_registry


def _offline(query, service="pk"):
    return run_pipeline(
        query,
        service,
        expander="noop",
        decomposer="gazetteer",
        translator="deterministic",
        aggregator="deterministic",
        normalizer="fuzzy",
    )


def test_pk_registers():
    assert "pk" in service_registry.names()


def test_early_contributor_threshold():
    assert EARLY_CONTRIBUTOR_THRESHOLD == 500
    svc = get_service("pk")
    assert svc.early_contributor_threshold == 500


def test_pk_has_16_fields():
    svc = get_service("pk")
    expected_fields = {
        "drugs",
        "species",
        "routes",
        "documentSource",
        "documentYear",
        "parameter",
        "parameterDisplay",
        "studyGroup",
        "age",
        "dose",
        "duration",
        "sex",
        "concomitants",
        "tissueSpecific",
        "metabolitesEnantiomers",
        "isPreclinical",
    }
    assert expected_fields == set(svc.fields)


def test_pk_assembles_valid_query_with_invariants():
    r = _offline("What is the Cmax of sunitinib in rat after oral administration")
    assert r.ok
    flat = str(r.machine_query.query)
    assert "concomitants" in flat
    assert "tissueSpecific" in flat
    assert "metabolitesEnantiomers" in flat


def test_pk_service_exposes_pk_fields_and_facets():
    svc = get_service("pk")
    assert {"parameter", "concomitants", "tissueSpecific", "metabolitesEnantiomers"} <= set(
        svc.fields
    )
    assert {"parameters", "tissueSpecific"} <= svc.facet_allow_list


def test_pk_termite_map():
    svc = get_service("pk")
    assert svc.termite_type_map.get("DRUG") == "drugs"
    assert svc.termite_type_map.get("SPECIES") == "species"
    assert svc.termite_type_map.get("ROUTE") == "routes"
    assert svc.termite_type_map.get("PARAMETER") == "parameter"
    assert svc.termite_type_map.get("AGE") == "age"


def test_pk_closed_fields_include_drugs_species_routes():
    svc = get_service("pk")
    closed = set(svc.closed_fields())
    assert {"drugs", "species", "routes"} <= closed


def test_pk_enum_fields_have_correct_values():
    svc = get_service("pk")
    assert svc.fields["sex"].enum_values == ["Male", "Female", "Both"]
    assert "Fasted" in svc.fields["concomitants"].enum_values
    assert svc.fields["isPreclinical"].bucket == "boolean"


def test_pk_invariants_applied():
    r = _offline("Cmax of sunitinib in rat")
    assert r.ok
    flat = str(r.machine_query.query)
    assert "tissueSpecific" in flat
    assert "metabolitesEnantiomers" in flat
