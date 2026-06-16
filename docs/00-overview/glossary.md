# Glossary

| Term | Meaning |
|------|---------|
| **NL query** | The raw natural-language question from the user. |
| **Machine query** | The structured request body the PharmaPendium API executes. A nested boolean tree of filters plus options (`facets`, `displayColumns`, `entityFilters`, …). |
| **Filter / constraint** | The atomic unit of a machine query: an `(operator, field, value)` triple. |
| **NL subquery** | A small natural-language fragment that concerns exactly one field, produced by decomposing the NL query (Stage 1). |
| **Machine subquery** | The single filter that one NL subquery translates into (Stage 2). |
| **Operator / constraint type** | `MATCH`, `OR`, `AND`, `NOT`, `REGEX`, `RANGE`, `DATE_RANGE`, `EMPTY`, `PROXIMITY`. |
| **Field** | A searchable column, e.g. `species`, `effects`, `documentYear`. The full list is in [inputs/fields.csv](../../inputs/fields.csv) and the request-side criteria in [inputs/query_criteria_fields.csv](../../inputs/query_criteria_fields.csv). |
| **Closed-vocabulary (CV) field** | A field whose legal values are fully enumerable and exist as a CSV taxonomy in `inputs/`. Values are *grounded* against that CSV. |
| **Open field** | A field whose value space we cannot enumerate; the LLM decides the value freely (often a `REGEX` or `RANGE`). |
| **Grounding** | Forcing a generated value to be (or map to) a real entry in a CSV taxonomy, rather than a model invention. |
| **Hierarchy / rollup** | Parent→child relationships inside a taxonomy CSV (`parent_id`, `parent_name`). E.g. "Rodent" → Rat, Mouse…; a drug class → its member drugs; a MedDRA category → its preferred terms. |
| **Preferred label** | The canonical name for an entity in a taxonomy (the `name` column of a CSV). |
| **TERMite** | SciBite's NER service ([utils/termite/](../../utils/termite/)) that annotates the query with recognised entities and their preferred labels/IDs. |
| **Service** | One of the three back-end search collections this translator targets: **Safety** (adverse effects/toxicity), **PK** (pharmacokinetics), **RTB** (Reaxys bioactivity / CrossFire). |
| **Facet** | A field requested for grouped counts in the response (allow-listed per service). |
| **Entity filter** | A filter applied via a linked entity rather than a direct field (`DrugsTargets`, `DrugsIndications`, …). |
| **SME gold set** | [inputs/sme_expected_cases.csv](../../inputs/sme_expected_cases.csv): subject-matter-expert questions with the expected per-field values — the decomposition target and the evaluation reference. |
