# Legacy architecture (as-is)

The current translator lives in
[utils/ppendium/__init__.py](../../utils/ppendium/__init__.py) and
[utils/ppendium/prompts.py](../../utils/ppendium/prompts.py).

## Flow

```
            ┌─────────────────────────────────────────────────────────┐
 NL query ─▶│ 1. TERMite annotation                                   │
            │    Termite7ResponseHandler.get_mark_up_with_entity_...  │
            │    → annotated query: "... {! Sunitinib | DRUG !} ..."  │
            └─────────────────────────────────────────────────────────┘
                                │
                                ▼
            ┌─────────────────────────────────────────────────────────┐
 ONE giant │ 2. Single LLM call with the whole service prompt         │
  prompt   │    pp_base_safety_translation  /  pp_base_pk_translation │
   per     │    prompt.replace("{{it}}", query)                       │
 service   │          .replace("{{it_annotated}}", annotated_query)   │
            │    llm.invoke(prompt) → raw text                        │
            └─────────────────────────────────────────────────────────┘
                                │
                                ▼
            ┌─────────────────────────────────────────────────────────┐
            │ 3. Regex/brace extraction of the JSON blob              │
            │    extract_payload_req() → dict                         │
            └─────────────────────────────────────────────────────────┘
                                │
                                ▼
            ┌─────────────────────────────────────────────────────────┐
            │ 4. POST to PharmaPendium search API                     │
            │    get_solr_response() → items                          │
            └─────────────────────────────────────────────────────────┘
```

Key methods in [utils/ppendium/__init__.py](../../utils/ppendium/__init__.py):

- `solr_json_translation()` — runs TERMite, picks the service prompt, does the
  single LLM call, and extracts the JSON.
- `extract_payload_req()` / `_find_matching_brace()` — best-effort parsing of a
  JSON object out of free-form LLM text.
- `get_solr_response()` / `fetch_all_items()` — execute the query against the
  Safety / PK / MoA endpoints.
- `retrieve_structured_data()` — the public entry point that ties it together.

## The prompts

[utils/ppendium/prompts.py](../../utils/ppendium/prompts.py) is ~1600 lines and
holds the entire intelligence of the system as prose. Each service has a single
mega-prompt:

- `pp_base_safety_translation` (+ a `drugsFuzzy` variant)
- `pp_base_pk_translation` (+ a `drugsFuzzy` variant)
- `rtb_cross_fire_conversion_prompt` (Reaxys bioactivity / CrossFire)

Each mega-prompt bundles, in one block of text:

- the database description and scope;
- the full list of searchable fields and their meanings;
- the constraint-type syntax (`MATCH`/`OR`/`AND`/`NOT`/`REGEX`/`RANGE`/…);
- per-field rules (drug field selection, toxicity-parameter handling, species
  rules, route rules, study-group synonym expansion, unit normalization,
  facet allow-lists, …);
- a handful of few-shot examples.

The model is expected to internalise **all** of this and emit a correct,
parseable machine query in a single pass.

## What grounding exists today

Only **TERMite annotation**. TERMite tags recognised entities with a preferred
label and type (e.g. `{! Sunitinib | DRUG !}`), and the prompt instructs the
model to prefer those labels. There is **no** lookup against the taxonomy CSVs
in [inputs/](../../inputs/): the model is free to emit any string as a field
value, and nothing checks that the value exists in the vocabulary or expands it
along the hierarchy.

Continue to [pain-points.md](pain-points.md) for why this is a problem.
