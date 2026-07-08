# Glossary

| Term | Meaning |
|------|---------|
| **NL query** | The raw natural-language question from the user. |
| **Expanded query** | Stage -1's faithful rewrite of the NL query: clearer wording and expanded abbreviations and correction of possible misspellings, with the original query preserved. |
| **Machine query** | The structured request body the PharmaPendium API executes. A nested boolean tree of filters plus options (`facets`, `displayColumns`, `entityFilters`, …). |
| **Filter / constraint** | The atomic unit of a machine query: an `(operator, field, value)` triple. |
| **NL subquery** | A small natural-language fragment that concerns exactly one field, produced by decomposing the NL query (Stage 1). |
| **Machine subquery** | The single filter that one NL subquery translates into (Stage 2). |
| **Operator / constraint type** | `MATCH`, `OR`, `AND`, `NOT`, `REGEX`, `RANGE`, `DATE_RANGE`, `EMPTY`, `PROXIMITY`. |
| **Field** | A searchable column, e.g. `species`, `routes`, `documentYear`. The full list is in [inputs/fields.csv](../../inputs/fields.csv) and the request-side criteria in [inputs/query_criteria_fields.csv](../../inputs/query_criteria_fields.csv). |
| **Closed-set field** | A field whose legal values are fully enumerable before the first API call, either from an `inputs/` CSV taxonomy, an inline enum, or a boolean domain. Values are *grounded* against that set. |
| **Open-set field** | A field whose value space is not fully enumerable before the first API call. The translator emits these fields as direct `MATCH` or `REGEX` constraints and can optionally guard them with zero-count probes. |
| **Zero-count probe** | An optional live guard for open-set filters: execute one isolated count query and drop the filter only when the API confirms it matches no records. |
| **Grounding** | Forcing a generated or selected value to be a real member of a closed set, rather than a model invention. |
| **Hierarchy / rollup** | Parent→child relationships inside a taxonomy CSV (`parent_id`, `parent_name`). E.g. "Rodent" → Rat, Mouse…; a drug class → its member drugs. |
| **Preferred label** | The canonical name for an entity in a taxonomy (the `name` column of a CSV). |
| **TERMite** | SciBite's NER service ([utils/termite/](../../utils/termite/)) that annotates the query with recognised entities and their preferred labels/IDs. |
| **Service** | The back-end search collection this translator targets: **PK** (pharmacokinetics), served by the PharmaPendium API. |
| **Facet** | A field requested for grouped counts in the response (allow-listed per service). |
| **Entity filter** | A filter applied via a linked entity rather than a direct field. The PK service routes all field filters directly into the top-level query. |
| **SME gold set** | [PPPK.xlsx](../PPPK.xlsx): subject-matter-expert questions with the expected datapoint counts. |
