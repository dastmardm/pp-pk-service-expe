"""Reshape inputs/sme_expected_cases.csv into a per-stage SME breakdown.

Output columns (one per pipeline stage, per dag.py / docs/03-proposed-design):
  nl query | counts | termite (Stage 0) | decompose (Stage 1)
          | translate (Stage 2) | aggregate (Stage 3) | machine query

Stage outputs are derived from the SME per-field annotations following the
format in docs/04-examples/worked-examples.md. They are a first pass for SMEs
to edit.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "inputs" / "sme_stage_cases.csv"

# Reusable effect expansions (verbatim from the SME source) ------------------
NEUTRO = [
    "Agranulocytosis", "Autoimmune neutropenia", "Benign ethnic neutropenia",
    "Cyclic neutropenia", "Febrile neutropenia", "Granulocytopenia",
    "Idiopathic neutropenia", "Neutropenia",
]
THROMBO = [
    "Heparin-induced thrombocytopenia test",
    "Heparin-induced thrombocytopenia test positive",
    "Haemangioma-thrombocytopenia syndrome",
    "Autoimmune heparin-induced thrombocytopenia",
    "Heparin-induced thrombocytopenia", "Immune thrombocytopenia",
    "Non-immune heparin associated thrombocytopenia",
    "Spontaneous heparin-induced thrombocytopenia syndrome",
    "Thrombocytopenia", "Thrombocytopenia neonatal",
    "Thrombosis with thrombocytopenia syndrome",
]
NEPHRITIS = [
    "Autoimmune nephritis", "Immune-mediated nephritis", "Lupus nephritis",
    "Nephritis", "Nephritis haemorrhagic", "Tubulointerstitial nephritis",
    "Tubulointerstitial nephritis and uveitis syndrome", "Nephritis bacterial",
    "Nephritis radiation", "Henoch-Schonlein purpura nephritis",
    "Nephritis allergic",
]
ARRHYTHMIA = [
    "Arrhythmia", "Arrhythmia neonatal", "Foetal arrhythmia",
    "Paroxysmal arrhythmia", "Reperfusion arrhythmia", "Withdrawal arrhythmia",
    "Arrhythmia supraventricular", "Nodal arrhythmia", "Sinus arrhythmia",
    "Ventricular arrhythmia", "Arrhythmia induced cardiomyopathy",
]
HEPATIC = ["Hepatic and hepatobiliary disorders NEC"]
MONKEYS = [
    "African green monkey", "Capuchin monkey", "Cynomolgus monkey",
    "Monkey (unspecified)", "Patas monkey", "Pig-tailed monkey",
    "Rhesus monkey", "Squirrel monkey", "Stumptail monkey", "Velvet monkey",
]
PRECLIN = [
    "Rat", "Mouse", "Dog", "pig", "minipig", "Cynomolgus Monkey",
    "Monkey (unspecified)", "Rhesus Monkey", "Rabbit",
]
ROUTES_ALL = [
    "oral", "intravenous", "intramuscular", "subcutaneous", "intradermal",
    "intraarterial", "inhalation", "intrathecal", "intraperitoneal",
    "intracerebral", "intracerebroventricular", "intravesical", "intravitreal",
    "intranasal", "rectal", "topical", "transdermal", "buccal", "sublingual",
    "Unreported",
]


def j(obj) -> str:
    """Compact JSON for the machine-query cell."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def abbrev(values: list[str], keep: int = 3) -> str:
    """Readable, abbreviated value list for the aggregate cell."""
    if len(values) <= keep:
        return ", ".join(values)
    return ", ".join(values[:keep]) + f", …(+{len(values) - keep} more)"


# Each row: (nl, counts, termite, decompose, translate, aggregate, machine_query)
ROWS: list[tuple] = []


def add(nl, counts, termite, decompose, translate, aggregate, mq):
    ROWS.append((nl, counts, termite, decompose, translate, aggregate, mq))


# Q1 -------------------------------------------------------------------------
add(
    "What are the ADRs of Sunitinib in human", "4300",
    "DRUG:Sunitinib; SPECIES:Human",
    'drugs[filter]:"Sunitinib"; species[filter]:"human"; effects[question]:"ADRs"',
    'MATCH drugsFuzzy=["Sunitinib*"] (+salt Sunitinib Malate); MATCH species="Human"; facet:effects',
    'AND[ drugsFuzzy=["Sunitinib*"], species="Human" ] | facets=[effects]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Sunitinib*"]}},
                         {"MATCH": {"field": "species", "value": "Human"}}]},
       "facets": ["effects"]}),
)

# Q2 -------------------------------------------------------------------------
add(
    "At which dose neutropenia occured for suntinib in homo sapiens", "97",
    "DRUG:Sunitinib (fuzzy on misspelled 'suntinib'); SPECIES:Human (homo sapiens); ADVERSE_EVENT:Neutropenia",
    'drugs[filter]:"suntinib"; species[filter]:"homo sapiens"; effects[filter]:"neutropenia"; dose[question]:"at which dose"',
    'MATCH drugsFuzzy=["Sunitinib*"]; MATCH species="Human"; MATCH effects=[neutropenia rollup, MedDRA]; question:dose',
    f'AND[ drugsFuzzy=["Sunitinib*"], species="Human", effects=[{abbrev(NEUTRO)}] ] | displayColumns=[dose]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Sunitinib*"]}},
                         {"MATCH": {"field": "species", "value": "Human"}},
                         {"MATCH": {"field": "effects", "value": NEUTRO}}]},
       "displayColumns": ["dose"]}),
)

# Q3 -------------------------------------------------------------------------
add(
    "What are the ADRs Of cabozantininb in rats", "518",
    "DRUG:Cabozantinib (NOT recognized by TERMite — falls back to CSV fuzzy); SPECIES:Rat",
    'drugs[filter]:"cabozantininb"; species[filter]:"rats"; effects[question]:"ADRs"',
    'MATCH drugsFuzzy=["Cabozantinib*"] (CSV fuzzy, TERMite missed); MATCH species="Rat"; facet:effects',
    'AND[ drugsFuzzy=["Cabozantinib*"], species="Rat" ] | facets=[effects]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Cabozantinib*"]}},
                         {"MATCH": {"field": "species", "value": "Rat"}}]},
       "facets": ["effects"]}),
)

# Q4 -------------------------------------------------------------------------
add(
    "Does abemaciclib cause liver disorders in rats or mice?", "2",
    "DRUG:Abemaciclib; SPECIES:Rat, Mouse; ADVERSE_EVENT:liver disorders→Hepatic and hepatobiliary disorders NEC",
    'drugs[filter]:"abemaciclib"; species[filter]:"rats or mice"(OR); effects[filter]:"liver disorders"',
    'MATCH drugsFuzzy=["Abemaciclib*"]; MATCH species=["Rat","Mouse"]; MATCH effects=[PT terms under "Hepatic and hepatobiliary disorders NEC"]',
    'AND[ drugsFuzzy=["Abemaciclib*"], species=["Rat","Mouse"], effects=["Hepatic and hepatobiliary disorders NEC"] ] | facets=[effects]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Abemaciclib*"]}},
                         {"MATCH": {"field": "species", "value": ["Rat", "Mouse"]}},
                         {"MATCH": {"field": "effects", "value": HEPATIC}}]},
       "facets": ["effects"]}),
)

# Q5 -------------------------------------------------------------------------
add(
    "What are the drug causing neutropenia in human, at which dose, dosing regimen and route?", "37838",
    "ADVERSE_EVENT:Neutropenia; SPECIES:Human",
    'effects[filter]:"neutropenia"; species[filter]:"human"; drug[question]:"what are the drug"; dose[question]:"at which dose"; doseType[question]:"dosing regimen"; route[question]:"route"',
    f'MATCH effects=[neutropenia rollup]; MATCH species="Human"; output drugs+dose+doseType+route',
    f'AND[ species="Human", effects=[{abbrev(NEUTRO)}] ] | displayColumns=[drug,dose,doseType,route]',
    j({"query": {"AND": [{"MATCH": {"field": "species", "value": "Human"}},
                         {"MATCH": {"field": "effects", "value": NEUTRO}}]},
       "displayColumns": ["drug", "dose", "doseType", "route"]}),
)

# Q6 -------------------------------------------------------------------------
add(
    "Does abemaciclib cause liver disorders in rats or mice", "66",
    "DRUG:Abemaciclib; SPECIES:Rodent (broad class — expand to members); ADVERSE_EVENT:liver disorders",
    'drugs[filter]:"abemaciclib"; species[filter]:"rats or mice"→class "Rodent"; effects[filter]:"liver disorders"',
    'MATCH drugsFuzzy=["Abemaciclib*"]; MATCH species="Rodent" (class, broader than rat+mouse); MATCH effects=[neutropenia rollup]',
    f'AND[ drugsFuzzy=["Abemaciclib*"], species="Rodent", effects=[{abbrev(NEUTRO)}] ] | facets=[effects]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Abemaciclib*"]}},
                         {"MATCH": {"field": "species", "value": "Rodent"}},
                         {"MATCH": {"field": "effects", "value": NEUTRO}}]},
       "facets": ["effects"]}),
)

# Q7 -------------------------------------------------------------------------
add(
    "What are the drug causing neutropenia in at least one preclinical species and Human with IV administration", "7620",
    "ADVERSE_EVENT:Neutropenia; SPECIES:Human + preclinical list; ROUTE:intravenous",
    'effects[filter]:"neutropenia"; species[filter]:"preclinical species AND Human"(boolean); route[filter]:"IV"; drug[question]:"what are the drug"',
    f'MATCH effects=[neutropenia rollup]; species = Human AND (preclinical members); MATCH route=[intravenous,…]',
    f'AND[ effects=[{abbrev(NEUTRO)}], species:[ Human AND OR({abbrev(PRECLIN)}) ], route=[intravenous,…] ] | isPreclinical=Yes | facets=[drugs]',
    j({"query": {"AND": [{"MATCH": {"field": "effects", "value": NEUTRO}},
                         {"MATCH": {"field": "species", "value": "Human"}},
                         {"OR": [{"MATCH": {"field": "species", "value": PRECLIN}}]},
                         {"MATCH": {"field": "route", "value": ["intravenous", "intravenous/subcutaneous", "oral/intravenous"]}}]},
       "isPreclinical": True, "facets": ["drugs"]}),
)

# Q8 -------------------------------------------------------------------------
add(
    "What are the adverse events found for inhibitors of kinases in human after IV administration in repeated doses", "1851",
    "TARGET:Kinase (MIS-TYPED by NER — is a DRUG CLASS 'Kinase inhibitors'); SPECIES:Human; ROUTE:intravenous; doseType:Repeated",
    'drugs[filter]:"inhibitors of kinases"→class "Kinase inhibitors"; species[filter]:"human"; route[filter]:"IV"; doseType[filter]:"repeated doses"; effects[question]:"adverse events"',
    'MATCH drugsFuzzy=["Kinase inhibitors"] (class node, NOT target); MATCH species="Human"; MATCH route="intravenous"; MATCH doseType="Repeated"; facet:effects',
    'AND[ drugsFuzzy=["Kinase inhibitors"], species="Human", route="intravenous", doseType="Repeated" ] | facets=[effects] | note: SME wants top-20 ADR table by % of drugs',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Kinase inhibitors"]}},
                         {"MATCH": {"field": "species", "value": "Human"}},
                         {"MATCH": {"field": "route", "value": "intravenous"}},
                         {"MATCH": {"field": "doseType", "value": "Repeated"}}]},
       "facets": ["effects"]}),
)

# Q10 ------------------------------------------------------------------------
add(
    "what is the NOAEL for sunitinib", "43",
    "DRUG:Sunitinib; TOXICITY_PARAMETER:NOAEL",
    'drugs[filter]:"sunitinib"; toxicityParameter[filter]:"NOAEL"; value[question]:"what is the NOAEL"',
    'MATCH drugsFuzzy=["Sunitinib*"]; MATCH toxicityParameter="NOAEL" (verified in toxicity_parameters.csv); output value',
    'AND[ drugsFuzzy=["Sunitinib*"], toxicityParameter="NOAEL" ] | displayColumns=[value]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Sunitinib*"]}},
                         {"MATCH": {"field": "toxicityParameter", "value": "NOAEL"}}]},
       "displayColumns": ["value"]}),
)

# Q11 ------------------------------------------------------------------------
add(
    "what is the No Observed Adverse Effect Level for sunitinib in rats", "33",
    "DRUG:Sunitinib; TOXICITY_PARAMETER:NOAEL (No Observed Adverse Effect Level); SPECIES:Rat",
    'drugs[filter]:"sunitinib"; toxicityParameter[filter]:"No Observed Adverse Effect Level"; species[filter]:"rats"; value[question]:"what is the …Level"',
    'MATCH drugsFuzzy=["Sunitinib*"]; MATCH toxicityParameter="NOAEL"; MATCH species="Rat"; output value',
    'AND[ drugsFuzzy=["Sunitinib*"], toxicityParameter="NOAEL", species="Rat" ] | displayColumns=[value]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Sunitinib*"]}},
                         {"MATCH": {"field": "toxicityParameter", "value": "NOAEL"}},
                         {"MATCH": {"field": "species", "value": "Rat"}}]},
       "displayColumns": ["value"]}),
)

# Q12 ------------------------------------------------------------------------
add(
    "what is the NOAEL for sunitinib in rats related to maternal  toxicity", "1",
    "DRUG:Sunitinib; TOXICITY_PARAMETER:NOAEL; SPECIES:Rat  (maternal toxicity → OPEN field, no NER)",
    'toxicityParameter[filter]:"NOAEL"; drugs[filter]:"sunitinib"; species[filter]:"rats"; parameterComment[filter]:"maternal toxicity"; value[question]:"what is the NOAEL"',
    'MATCH toxicityParameter="NOAEL"; MATCH drugsFuzzy=["Sunitinib*"]; MATCH species="Rat"; MATCH parameterComment="Maternal toxicity" (OPEN, LLM decides); output value',
    'AND[ drugsFuzzy=["Sunitinib*"], toxicityParameter="NOAEL", species="Rat", parameterComment="Maternal toxicity" ] | displayColumns=[value]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Sunitinib*"]}},
                         {"MATCH": {"field": "toxicityParameter", "value": "NOAEL"}},
                         {"MATCH": {"field": "species", "value": "Rat"}},
                         {"MATCH": {"field": "parameterComment", "value": "Maternal toxicity"}}]},
       "displayColumns": ["value"]}),
)

# Q13 ------------------------------------------------------------------------
add(
    "What are the drug causing neutropenia or Thrombocytopenia in human, at which dose, dosing regimen and route?", "61198",
    "ADVERSE_EVENT:Neutropenia; ADVERSE_EVENT:Thrombocytopenia; SPECIES:Human",
    'effects[filter]:"neutropenia"(OR g1); effects[filter]:"Thrombocytopenia"(OR g1); species[filter]:"human"; drug[question]; dose[question]; doseType[question]:"dosing regimen"; route[question]',
    'MATCH species="Human"; OR( MATCH effects=[neutropenia rollup], MATCH effects=[thrombocytopenia rollup] ); output drugs+dose+doseType+route',
    f'AND[ species="Human", OR( effects=[{abbrev(NEUTRO)}], effects=[{abbrev(THROMBO)}] ) ] | displayColumns=[drug,dose,doseType,route]',
    j({"query": {"AND": [{"MATCH": {"field": "species", "value": "Human"}},
                         {"OR": [{"MATCH": {"field": "effects", "value": NEUTRO}},
                                 {"MATCH": {"field": "effects", "value": THROMBO}}]}]},
       "displayColumns": ["drug", "dose", "doseType", "route"]}),
)

# Q14 ------------------------------------------------------------------------
add(
    "What are the drug causing neutropenia and cytopenia in human, at which dose, dosing regimen and route?", "60128",
    "ADVERSE_EVENT:Neutropenia; ADVERSE_EVENT:cytopenia/Thrombocytopenia; SPECIES:Human",
    'effects[filter]:"neutropenia"(AND g1); effects[filter]:"cytopenia"(AND g2); species[filter]:"human"; route[question]; drug[question]; dose[question]; doseType[question]',
    'MATCH species="Human"; AND( MATCH effects=[neutropenia rollup], MATCH effects=[thrombocytopenia rollup] ); MATCH route=[all routes]',
    f'AND[ species="Human", effects=[{abbrev(NEUTRO)}], effects=[{abbrev(THROMBO)}], route=[{abbrev(ROUTES_ALL)}] ] | displayColumns=[drug,dose,doseType,route]',
    j({"query": {"AND": [{"MATCH": {"field": "species", "value": "Human"}},
                         {"MATCH": {"field": "effects", "value": NEUTRO}},
                         {"MATCH": {"field": "effects", "value": THROMBO}},
                         {"MATCH": {"field": "route", "value": ROUTES_ALL}}]},
       "displayColumns": ["drug", "dose", "doseType", "route"]}),
)

# Q15 ------------------------------------------------------------------------
EFF_ADV = ["adverse*", "toxicity", "side effect", "adverse drug reaction", "adverse event"]
add(
    "What are the adverse events found for drugs treating non small lung cancer in human with subcutaneous administration?", "13559",
    "INDICATION:non small lung cancer; SPECIES:Human; ROUTE:subcutaneous",
    'indications[filter]:"non small lung cancer"; species[filter]:"human"; route[filter]:"subcutaneous"; effects[question]:"adverse events"',
    'MATCH indications="non small lung cancer"; MATCH species="Human"; MATCH route="subcutaneous"; facet:effects (adverse* / toxicity / side effect …)',
    'AND[ indications="non small lung cancer", species="Human", route="subcutaneous" ] | facets=[effects]',
    j({"query": {"AND": [{"MATCH": {"field": "indications", "value": "non small lung cancer"}},
                         {"MATCH": {"field": "species", "value": "Human"}},
                         {"MATCH": {"field": "route", "value": "subcutaneous"}}]},
       "facets": ["effects"]}),
)

# Q16 ------------------------------------------------------------------------
add(
    "What are the drugs causing cardiac disorders in non clinical species with single administration in adult female", "174",
    "ADVERSE_EVENT:Cardiac disorders (SOC level 1); SPECIES:non clinical (preclinical); doseType:Single; SEX:Female  (adult → substring on Ages)",
    'effects[filter]:"cardiac disorders"(SOC); species[filter]:"non clinical species"; doseType[filter]:"single"; ages[filter]:"adult"; sex[filter]:"female"; drug[question]',
    'MATCH effects=[Cardiac disorders SOC rollup]; isPreclinical=Yes; MATCH doseType="Single"; REGEX ages=".*adult.*" (substring, OPEN); MATCH sex="Female"',
    'AND[ effects=["Cardiac disorders"], doseType="Single", ages~"adult", sex="Female" ] | isPreclinical=Yes | facets=[drugs]',
    j({"query": {"AND": [{"MATCH": {"field": "effects", "value": ["Cardiac disorders"]}},
                         {"MATCH": {"field": "doseType", "value": "Single"}},
                         {"REGEX": {"field": "ages", "value": ".*adult.*"}},
                         {"MATCH": {"field": "sex", "value": "Female"}}]},
       "isPreclinical": True, "facets": ["drugs"]}),
)

# Q17 ------------------------------------------------------------------------
add(
    "What is the LD50 of Acyclovir in Rat or mouse after per os administration?", "6",
    "DRUG:Acyclovir (strange TERMite match — also surfaced Hydrocortisone); SPECIES:Rat, Mouse; TOXICITY_PARAMETER:LD50; ROUTE:Oral (per os)",
    'toxicityParameter[filter]:"LD50"; drugs[filter]:"Acyclovir"; species[filter]:"Rat or mouse"(OR); route[filter]:"per os"; value[question]:"what is the LD50"',
    'MATCH toxicityParameter="LD50"; MATCH drugsFuzzy=["Acyclovir*"]; MATCH species=["Rat","Mouse"]; MATCH route="Oral"; output value',
    'AND[ drugsFuzzy=["Acyclovir*"], toxicityParameter="LD50", species=["Rat","Mouse"], route="Oral" ] | displayColumns=[value]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Acyclovir*"]}},
                         {"MATCH": {"field": "toxicityParameter", "value": "LD50"}},
                         {"MATCH": {"field": "species", "value": ["Rat", "Mouse"]}},
                         {"MATCH": {"field": "route", "value": "Oral"}}]},
       "displayColumns": ["value"]}),
)

# Q18 ------------------------------------------------------------------------
add(
    "What is the Maximal tolerated dose of Alpelisib in human after repeated Oral Administration", "3",
    "DRUG:Alpelisib; SPECIES:Human; TOXICITY_PARAMETER:MTD (Maximal tolerated dose); ROUTE:Oral; doseType:Repeated",
    'toxicityParameter[filter]:"Maximal tolerated dose"; drugs[filter]:"Alpelisib"; species[filter]:"human"; doseType[filter]:"repeated"; route[filter]:"Oral"; value[question]',
    'MATCH toxicityParameter="MTD"; MATCH drugsFuzzy=["Alpelisib*"]; MATCH species="Human"; MATCH doseType="Repeated"; MATCH route="Oral"; output value',
    'AND[ drugsFuzzy=["Alpelisib*"], toxicityParameter="MTD", species="Human", doseType="Repeated", route="Oral" ] | displayColumns=[value]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Alpelisib*"]}},
                         {"MATCH": {"field": "toxicityParameter", "value": "MTD"}},
                         {"MATCH": {"field": "species", "value": "Human"}},
                         {"MATCH": {"field": "doseType", "value": "Repeated"}},
                         {"MATCH": {"field": "route", "value": "Oral"}}]},
       "displayColumns": ["value"]}),
)

# Q19 ------------------------------------------------------------------------
add(
    "What are the drugs causing Mutagenicity in Rats", "447",
    "ADVERSE_EVENT:Mutagenicity; SPECIES:Rat",
    'effects[filter]:"Mutagenicity"; species[filter]:"Rats"; drug[question]:"what are the drugs"',
    'MATCH effects="Mutagenicity"; MATCH species="Rat"; facet:drugs',
    'AND[ effects="Mutagenicity", species="Rat" ] | facets=[drugs]',
    j({"query": {"AND": [{"MATCH": {"field": "effects", "value": "Mutagenicity"}},
                         {"MATCH": {"field": "species", "value": "Rat"}}]},
       "facets": ["drugs"]}),
)

# Q20 ------------------------------------------------------------------------
add(
    "What are the drug having a positive Ames Test?", "180",
    "ADVERSE_EVENT/ASSAY:Ames Test  (broad effect retrieval — SME warns 'mutagenicity and others' over-matches)",
    'effects[filter]:"positive Ames Test"; drug[question]:"what are the drug"',
    'MATCH effects="Ames Test" (narrow — do NOT expand to mutagenicity); facet:drugs',
    'AND[ effects="Ames Test" ] | facets=[drugs]',
    j({"query": {"AND": [{"MATCH": {"field": "effects", "value": "Ames Test"}}]},
       "facets": ["drugs"]}),
)

# Q21 ------------------------------------------------------------------------
add(
    "What is the No Observed Effect Level of CDk4 inhibitors in mice?", "2",
    "TARGET:Cyclin-dependent kinase 4 (CDK4) (NER matched 'Cyclin-dependent kinase 4', PP term adds '(CDK4)'); SPECIES:Mouse; TOXICITY_PARAMETER:NOEL",
    'targets[filter]:"CDk4 inhibitors"→target "Cyclin-dependent kinase 4 (CDK4)"; toxicityParameter[filter]:"No Observed Effect Level"; species[filter]:"mice"; value[question]',
    'MATCH targets="Cyclin-dependent kinase 4 (CDK4)"; MATCH toxicityParameter="NOEL"; MATCH species="Mouse"; output value',
    'AND[ targets="Cyclin-dependent kinase 4 (CDK4)", toxicityParameter="NOEL", species="Mouse" ] | displayColumns=[value]',
    j({"query": {"AND": [{"MATCH": {"field": "targets", "value": "Cyclin-dependent kinase 4 (CDK4)"}},
                         {"MATCH": {"field": "toxicityParameter", "value": "NOEL"}},
                         {"MATCH": {"field": "species", "value": "Mouse"}}]},
       "displayColumns": ["value"]}),
)

# Q22 ------------------------------------------------------------------------
add(
    "What are the drugs treating Gastro intestinal disorders causing arrythmia in human in single doses after IV administration", "12",
    "INDICATION:Gastro intestinal disorders; ADVERSE_EVENT:Arrhythmia (substring across PT & LLT synonyms); SPECIES:Human; doseType:Single; ROUTE:Intravenous",
    'indications[filter]:"Gastro intestinal disorders"; effects[filter]:"arrythmia"; species[filter]:"human"; doseType[filter]:"single doses"; route[filter]:"IV"; drug[question]',
    f'MATCH indications="Gastro intestinal disorders"; MATCH effects=[arrhythmia substring rollup]; MATCH species="Human"; MATCH doseType="Single"; MATCH route="Intravenous"; facet:drugs',
    f'AND[ indications="Gastro intestinal disorders", effects=[{abbrev(ARRHYTHMIA)}], species="Human", doseType="Single", route="Intravenous" ] | facets=[drugs]',
    j({"query": {"AND": [{"MATCH": {"field": "indications", "value": "Gastro intestinal disorders"}},
                         {"MATCH": {"field": "effects", "value": ARRHYTHMIA}},
                         {"MATCH": {"field": "species", "value": "Human"}},
                         {"MATCH": {"field": "doseType", "value": "Single"}},
                         {"MATCH": {"field": "route", "value": "Intravenous"}}]},
       "facets": ["drugs"]}),
)

# Q23 ------------------------------------------------------------------------
add(
    "What are the monoclonal antibodies causing Nephritis in Monkeys?", "27",
    "DRUG_CLASS:Monoclonal antibodies (class node, NOT 'monoclonal antibody'); ADVERSE_EVENT:Nephritis; SPECIES:Monkeys (class → expand to members)",
    'drugs[filter]:"monoclonal antibodies"(class); effects[filter]:"Nephritis"; species[filter]:"Monkeys"(expand-children); drug[question]',
    f'MATCH drugsFuzzy=["Monoclonal antibodies"] (class node); MATCH effects=[nephritis rollup]; MATCH species=[all monkey members]',
    f'AND[ drugsFuzzy=["Monoclonal antibodies"], effects=[{abbrev(NEPHRITIS)}], species=[{abbrev(MONKEYS)}] ] | facets=[drugs]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Monoclonal antibodies"]}},
                         {"MATCH": {"field": "effects", "value": NEPHRITIS}},
                         {"MATCH": {"field": "species", "value": MONKEYS}}]},
       "facets": ["drugs"]}),
)

# Q24 ------------------------------------------------------------------------
add(
    "What are the ADRs of ADC after single intravenous administration in male?", "13",
    "DRUG_CLASS:Antibody-Drug Conjugate (ADC) (NER gave 'ADC'; map to class node); SPECIES:Human; doseType:Single; ROUTE:Intravenous; SEX:Male",
    'drugs[filter]:"ADC"→class "Antibody-Drug Conjugate (ADC)"; species[filter]:(default Human); doseType[filter]:"single"; route[filter]:"intravenous"; sex[filter]:"male"; effects[question]:"ADRs"',
    'MATCH drugsFuzzy=["Antibody-Drug Conjugate (ADC)"] (class node, NOT bare "ADC"); MATCH species="Human"; MATCH doseType="Single"; MATCH route="Intravenous"; MATCH sex="Male"; facet:effects',
    'AND[ drugsFuzzy=["Antibody-Drug Conjugate (ADC)"], species="Human", doseType="Single", route="Intravenous", sex="Male" ] | facets=[effects]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Antibody-Drug Conjugate (ADC)"]}},
                         {"MATCH": {"field": "species", "value": "Human"}},
                         {"MATCH": {"field": "doseType", "value": "Single"}},
                         {"MATCH": {"field": "route", "value": "Intravenous"}},
                         {"MATCH": {"field": "sex", "value": "Male"}}]},
       "facets": ["effects"]}),
)

# Q25 ------------------------------------------------------------------------
add(
    "At which dose Tachycardia occurs for Columvi in Human after IV repeated dose?", "2",
    "DRUG:Glofitamab (TERMite resolved brand 'Columvi' → INN Glofitamab); SPECIES:Human; ADVERSE_EVENT:Tachycardia; doseType:Repeated; ROUTE:Intravenous",
    'drugs[filter]:"Columvi"→"Glofitamab"; effects[filter]:"Tachycardia"; species[filter]:"Human"; doseType[filter]:"repeated dose"; route[filter]:"IV"; dose[question]:"at which dose"',
    'MATCH drugsFuzzy=["Glofitamab*"] (brand Columvi normalized by TERMite); MATCH effects="Tachycardia"; MATCH species="Human"; MATCH doseType="Repeated"; MATCH route="Intravenous"; output dose',
    'AND[ drugsFuzzy=["Glofitamab*"], effects="Tachycardia", species="Human", doseType="Repeated", route="Intravenous" ] | displayColumns=[dose]',
    j({"query": {"AND": [{"MATCH": {"field": "drugsFuzzy", "value": ["Glofitamab*"]}},
                         {"MATCH": {"field": "effects", "value": "Tachycardia"}},
                         {"MATCH": {"field": "species", "value": "Human"}},
                         {"MATCH": {"field": "doseType", "value": "Repeated"}},
                         {"MATCH": {"field": "route", "value": "Intravenous"}}]},
       "displayColumns": ["dose"]}),
)


HEADER = ["nl query", "counts", "termite", "decompose", "translate",
          "aggregate", "machine query"]

with OUT.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(HEADER)
    w.writerows(ROWS)

print(f"wrote {len(ROWS)} rows -> {OUT}")
