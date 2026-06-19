"""Offline tests for the designed-for PK and RTB service configs.

Both reuse the shared pipeline; only their ServiceConfig data differs (CONST-12).
The doubles keep these hermetic: no network, no LLM.
"""

from oppp.pipeline import run_pipeline
from oppp.services import where_clause
from oppp.services.base import get_service, service_registry


def _offline(query, service):
    return run_pipeline(
        query,
        service,
        decomposer="gazetteer",
        translator="deterministic",
        aggregator="deterministic",
        normalizer="fuzzy",
    )


def test_all_three_services_register():
    assert {"safety", "pk", "rtb"} <= set(service_registry.names())


def test_pk_assembles_valid_query_with_invariants():
    r = _offline("What is the Cmax of sunitinib in rat after oral administration", "pk")
    assert r.ok
    flat = str(r.machine_query.query)
    # PK always-on invariants are applied (concomitants Fasted-or-empty, tissue, metabolites).
    assert "concomitants" in flat
    assert "tissueSpecific" in flat
    assert "metabolitesEnantiomers" in flat


def test_pk_service_exposes_pk_fields_and_facets():
    svc = get_service("pk")
    assert {"parameter", "concomitants", "tissueSpecific", "metabolitesEnantiomers"} <= set(
        svc.fields
    )
    assert {"parameters", "tissueSpecific"} <= svc.facet_allow_list


def test_rtb_emits_where_clause_from_same_filter_set():
    r = _offline("clearance of imatinib in dog after intravenous administration", "rtb")
    assert r.ok
    clause = where_clause(r.machine_query)
    assert clause  # non-empty CrossFire clause
    # RTB emits DAT.* columns and always includes the required category column.
    assert "DAT.BSPECIE='Dog'" in clause
    assert "DAT.MROUTE=" in clause
    assert "DAT.CATEG=" in clause


def test_rtb_where_clause_empty_query_is_empty_string():
    from oppp.models import MachineQuery

    assert where_clause(MachineQuery(query={})) == ""
