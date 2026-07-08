# CSV catalog (`inputs/`)

Every input CSV the translator depends on, what it contains, and how the pipeline uses
it. Row counts include the header line.

## Taxonomy CSVs (value vocabularies for closed-set fields)

These are the "unique values already exist as CSV" files the pipeline uses.
The hierarchical ones share the schema `name, id, parent_id, parent_name`.

| File | Rows | Schema | Backs field | Hierarchy |
|------|------|--------|-------------|-----------|
| [drugs.csv](../../inputs/drugs.csv) | 5,227 | name,id,parent_id,parent_name | `drugs`, `drugsFuzzy` | drug → drug class (parent) |
| [species.csv](../../inputs/species.csv) | 286 | name,id,parent_id,parent_name | `species` | class (Rodent, Primate, Fish…) → species |
| [route.csv](../../inputs/route.csv) | 204 | name,id,count | `routes` | flat (+ corpus `count`) |
| [sources.csv](../../inputs/sources.csv) | 56 | name,id,parent_id,parent_name | `documentSource` | document → FDA/EMA parent |
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
| [fields.csv](../../inputs/fields.csv) | 66 | field_key,label | Master list of response/display fields with human labels (e.g. `parameter` → "PK Parameter"). Drives `displayColumns` and the field router. |
| [query_criteria_fields.csv](../../inputs/query_criteria_fields.csv) | 17 | field,type | Request-side criteria and their types (`array<string>`, `array<integer>`, `boolean`, `SortColumn`, `Limitation`). Defines what the machine query may contain. |
| [enums.csv](../../inputs/enums.csv) | 24 | schema,field,allowed_value | `FuzzyLookupFilter.taxonomy` — the taxonomies the back-end fuzzy-lookup can resolve. |

The evaluation workbook is documented in
[../05-evaluation/gold-set-and-metrics.md](../05-evaluation/gold-set-and-metrics.md).
