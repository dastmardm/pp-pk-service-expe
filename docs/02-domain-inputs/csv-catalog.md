# CSV catalog (`inputs/`)

Every file the redesign depends on, what it contains, and how the pipeline uses
it. Row counts include the header line.

## Taxonomy CSVs (value vocabularies for closed-set fields)

These are the "unique values already exist as CSV" the redesign is built around.
The hierarchical ones share the schema `name, id, parent_id, parent_name`.

| File | Rows | Schema | Backs field | Hierarchy |
|------|------|--------|-------------|-----------|
| [drugs.csv](../../inputs/drugs.csv) | 5,227 | name,id,parent_id,parent_name | `drugs`, `drugsFuzzy` | drug → drug class (parent) |
| [effects.csv](../../inputs/effects.csv) | 12,724 | name,id,parent_id,parent_name | `effects` | MedDRA-style category → terms |
| [indications.csv](../../inputs/indications.csv) | 3,152 | name,id,parent_id,parent_name | `indications` | disease → group |
| [species.csv](../../inputs/species.csv) | 286 | name,id,parent_id,parent_name | `species` | class (Rodent, Primate, Fish…) → species |
| [route.csv](../../inputs/route.csv) | 204 | name,id,count | `route` | flat (+ corpus `count`) |
| [sources.csv](../../inputs/sources.csv) | 56 | name,id,parent_id,parent_name | `documentSource` | document → FDA/EMA parent |
| [toxicity_parameters.csv](../../inputs/toxicity_parameters.csv) | 33 | name,id,parent_id,parent_name | `toxicityParameter` | endpoint → category (Death, ADR…) |
| [dose_type.csv](../../inputs/dose_type.csv) | 7 | name,id,count | `doseType` | flat enum (+ `count`) |
| [document_year.csv](../../inputs/document_year.csv) | 118 | name,id,count | `documentYear` | flat; mixes single years and ranges ("1911 - 1920") |

**How used:** at Stage 2 an input closed-set field's value is translated against
its CSV using exact search, fuzzy search, LLM pool enrichment, and LLM selection
from the closed set when needed. Selected values may then expand through
`parent_id`/`parent_name` for class/rollup queries. The `id` column is the stable
taxonomy key; the `name` column is the preferred label sent to the API. `count`
(where present) is the corpus frequency, useful for ranking ambiguous matches
and for ordering facet output.

## Schema / catalog CSVs (describe the query surface, not values)

| File | Rows | Schema | Purpose |
|------|------|--------|---------|
| [fields.csv](../../inputs/fields.csv) | 66 | field_key,label | Master list of response/display fields with human labels (e.g. `effect` → "Adverse Effect / Toxicity"). Drives `displayColumns` and the field router. |
| [query_criteria_fields.csv](../../inputs/query_criteria_fields.csv) | 17 | field,type | Request-side criteria and their types (`array<string>`, `array<integer>`, `boolean`, `SortColumn`, `Limitation`). Defines what the machine query may contain. |
| [enums.csv](../../inputs/enums.csv) | 24 | schema,field,allowed_value | Two enum sets: `SafetyEntity.trScore` (translational-relevance scores) and `FuzzyLookupFilter.taxonomy` (the taxonomies the back-end fuzzy-lookup can resolve). |

## Evaluation CSV

| File | Rows | Purpose |
|------|------|---------|
| [sme_expected_cases.csv](../../inputs/sme_expected_cases.csv) | 25 (24 cases) | The SME gold set. Each row is a question already decomposed into expected per-field values, plus a `mapping_comment` recording where the legacy system failed. This is **both** the decomposition target (it literally has one column per field) and the evaluation reference. See [../05-evaluation/gold-set-and-metrics.md](../05-evaluation/gold-set-and-metrics.md). |

> A **per-step** companion gold set — one column per pipeline stage
> (`termite, decompose, translate, aggregate, machine query`) plus expected
> `counts` — lives at [docs/sme_stage_cases.csv](../sme_stage_cases.csv) *(in
> `docs/`, not `inputs/`)*. It is the reference for **per-step**
> evaluation; see [../05-evaluation/gold-set-and-metrics.md](../05-evaluation/gold-set-and-metrics.md).

### Gold-set columns

`query_number, query_type, question, s` (expected result count), `comment,
mapping_comment`, then **one column per field**: `drugsFuzzy, indications,
targets, species, effects, parameterComment, toxicityParameter, doseType, route,
ages, sex, studyGroup, isPreclinical, concomitants`.

The very existence of this per-field column layout is the strongest evidence for
the decomposed design: the experts already think of a query as a set of
independent per-field values. Multi-value cells are `;`-separated; the file even
encodes booleans inline, e.g. `Human AND (Rat, Mouse, Dog, …)` for "at least one
preclinical species and Human" (Q7) and a parenthesised `(…) AND (…)` for
"neutropenia and cytopenia" (Q14).
