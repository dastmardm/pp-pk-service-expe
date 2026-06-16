from oppp.models import ComponentType
from oppp.pipeline import run_pipeline
from oppp.services.base import get_service
from oppp.stages.aggregate import validate


def test_simple_drug_species_query():
    r = run_pipeline("What are the ADRs of Sunitinib in human", normalizer="fuzzy")
    assert r.ok
    fields = {c.field for c in r.decomposition.filters}
    assert {"drugs", "species"} <= fields
    payload = r.machine_query.to_payload()
    flat = str(payload)
    assert "drugsFuzzy" in flat and "Sunitinib*" in flat and "Human" in flat
    # "ADRs" is a question -> effects facet, not a filter
    assert "effects" in payload["facets"]
    assert any(c.type is ComponentType.QUESTION and c.field == "effects"
               for c in r.decomposition.components)


def test_boolean_or_within_effects():
    q = ("What are the drug causing neutropenia or Thrombocytopenia in human, "
         "at which dose, dosing regimen and route?")
    r = run_pipeline(q, normalizer="fuzzy")
    assert r.ok
    payload = r.machine_query.to_payload()
    # OR group over two effects MATCHes
    assert '"OR"' in str(payload).replace("'", '"')
    assert "displayColumns" in payload and "dose" in payload["displayColumns"]


def test_misspelled_drug_corrected_in_stage2():
    # The normalizer correction seam lives in Stage 2 (docs/misspelling-strategy):
    # a fragment already routed to `drugs` is bridged to the taxonomy entry.
    from oppp.models import Component, ComponentType
    from oppp.stages.translate import translate_one

    comp = Component(
        field="drugs", nl_fragment="suntinib", type=ComponentType.FILTER,
        reason="isolated", source="test",
    )
    sq = translate_one(comp, "safety", "fuzzy")
    assert sq is not None and sq.value == "Sunitinib*"


def test_year_range():
    r = run_pipeline("adverse events for tolvaptan in human after 2020", normalizer="fuzzy")
    flat = str(r.machine_query.to_payload())
    assert "RANGE" in flat and "2020" in flat


def test_validation_flags_empty_query():
    from oppp.models import MachineQuery
    issues = validate(MachineQuery(query={}), get_service("safety"))
    assert any(i.level == "error" for i in issues)
