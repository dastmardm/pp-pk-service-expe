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


def test_fuzzy_gazetteer_recovers_misspelled_drug():
    # Stage 1 must DETECT a misspelled drug (not just correct an already-routed one).
    r = run_pipeline("ADRs of suntinib in human", normalizer="fuzzy")
    drugs = [c for c in r.decomposition.filters if c.field == "drugs"]
    assert drugs and drugs[0].nl_fragment == "Sunitinib"
    assert drugs[0].source == "gazetteer-fuzzy:drugs"


def test_fuzzy_gazetteer_no_false_positives():
    # 'related' / 'maternal toxicity' must NOT be fuzzy-matched to doseType/effects.
    r = run_pipeline(
        "What is the NOAEL for sunitinib in rats related to maternal toxicity",
        normalizer="fuzzy",
    )
    fuzzy = {(c.field, c.nl_fragment) for c in r.decomposition.filters
             if c.source.startswith("gazetteer-fuzzy")}
    assert fuzzy == set()  # all four entities are exact matches; no fuzzy noise
    fields = {c.field for c in r.decomposition.filters}
    assert {"toxicityParameter", "drugs", "species", "parameterComment"} >= fields or \
           {"toxicityParameter", "drugs", "species"} <= fields


def test_meddra_rollup_expands_effect_to_family():
    # 'neutropenia' must roll up to its MedDRA family (parent 'Neutropenias').
    r = run_pipeline("drugs causing neutropenia in human", normalizer="fuzzy")
    eff = [s for s in r.subqueries if s.field == "effects"]
    assert eff and isinstance(eff[0].value, list)
    assert {"Neutropenia", "Agranulocytosis", "Febrile neutropenia"} <= set(eff[0].value)
    assert eff[0].grounding and eff[0].grounding.expanded_from == "family"


def test_budget_guard_collapses_oversized_rollup():
    # neutropenia + cytopenia families = 26 values > 20-constraint API limit;
    # the guard must collapse one back to its canonical term and stay valid.
    from oppp.stages.aggregate import MAX_CONSTRAINTS

    r = run_pipeline(
        "drugs causing neutropenia and cytopenia in human", normalizer="fuzzy"
    )
    total = sum(s.value_count() for s in r.subqueries)
    assert total <= MAX_CONSTRAINTS
    assert r.ok  # still a valid query, no error
    assert any(i.level == "warning" and "budget" in i.message for i in r.issues)


def test_year_range():
    r = run_pipeline("adverse events for tolvaptan in human after 2020", normalizer="fuzzy")
    flat = str(r.machine_query.to_payload())
    assert "RANGE" in flat and "2020" in flat


def test_validation_flags_empty_query():
    from oppp.models import MachineQuery
    issues = validate(MachineQuery(query={}), get_service("safety"))
    assert any(i.level == "error" for i in issues)
