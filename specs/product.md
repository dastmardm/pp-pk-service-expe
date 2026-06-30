# Product Specification

## Sources
- `docs/README.md`
- `docs/index.md`
- `docs/agent-dag.png`
- `docs/sme_stage_cases.csv`
- `docs/00-overview/glossary.md`
- `docs/00-overview/problem-statement.md`
- `docs/01-current-system/legacy-architecture.md`
- `docs/01-current-system/pain-points.md`
- `docs/02-domain-inputs/csv-catalog.md`
- `docs/02-domain-inputs/field-taxonomy.md`
- `docs/02-domain-inputs/machine-query-schema.md`
- `docs/03-proposed-design/architecture.md`
- `docs/03-proposed-design/grounding-and-tool-calling.md`
- `docs/03-proposed-design/misspelling-strategy.md`
- `docs/03-proposed-design/stage-1-decomposition.md`
- `docs/03-proposed-design/stage-2-subquery-translation.md`
- `docs/03-proposed-design/stage-3-aggregation.md`
- `docs/04-examples/worked-examples.md`
- `docs/05-evaluation/gold-set-and-metrics.md`
- `docs/06-implementation/build-status.md`
- `docs/06-implementation/operations.md`
- `docs/06-implementation/streamlit-ui.md`
- `docs/06-implementation/tech-stack.md`

## Purpose
The product converts a user's natural-language PharmaPendium question into the
machine query that the search service can execute. It replaces a monolithic
"single prompt emits everything" translator with a staged, auditable pipeline
where field values are selected from known value sets whenever those sets exist.

The core promise is: ground values before filtering. A closed-set field may only
filter on values from its known vocabulary, enum, or boolean domain. An open-set
field is deferred until retrieved datapoints provide the unique values for that
field; those values become a runtime closed set, and the same translation rules
select a valid subset for post-filtering.

## Core Capabilities
- Accept a natural-language question and produce a machine-query filter tree
  with optional facets, display columns, entity filters, and service-specific
  options.
- Preserve the user's original question while allowing a faithful pre-step
  expansion that clarifies abbreviations without adding or removing meaning.
- Optionally enhance the question with recognized entities and preferred labels.
  Enhancement improves recall but is not required for the pipeline to run.
- Decompose the question into single-field components, each marked as a retrieval
  filter or a post-retrieval question/output request.
- Translate closed-set filters by exact match, fuzzy match, enriched synonym
  search, and closed-set selection. A successful translation is always a subset
  of the field's known values; an empty or missing result is invalid and does not
  narrow downstream processing.
- Expand hierarchy and rollups where intended: drug classes, species classes,
  colloquial species groups such as "Monkeys", effect families, and curated
  preclinical/non-clinical concepts.
- Aggregate valid input closed-set filters into the first API query, execute it,
  derive runtime closed sets for deferred open-set filters from fetched
  datapoints, translate those open-set filters, and apply valid post-filters.
- Keep the current count/probe-oriented behavior visible as the v0.1 limitation
  until full row fetching and runtime post-filtering are materialized.
- Evaluate quality per step, per field, and end to end against SME gold sets.
- Provide command-line and interactive inspection surfaces that expose stage
  outputs for debugging and review.

## Key Actors
| Actor | Role |
|-------|------|
| Analyst | Asks the natural-language question and consumes retrieved evidence. |
| Subject-matter expert | Provides gold questions, expected mappings, counts, and notes on legacy failures. |
| Developer / evaluator | Runs isolated stages, inspects traces, updates tests, and evaluates regressions. |
| PharmaPendium search service | Executes the machine query and returns counts or datapoints. |
| Entity recognizer | Optionally supplies preferred labels and entity types before decomposition. |
| Language model | Supports expansion, decomposition, translation fallbacks, aggregation structure, and judged comparisons when configured. |

## Data Flow
1. The raw question enters the pipeline.
2. Stage -1 may rewrite it into a clearer equivalent question while preserving
   the original.
3. Stage 0 may attach recognized entity annotations.
4. Stage 1 emits one component per field concept, preserving filter/question
   roles and boolean hints.
5. Stage 2A translates input closed-set filter components against known
   vocabularies, enums, and booleans.
6. Stage 3 aggregates valid Stage 2A filters into the first API query and
   requests datapoints.
7. Stage 2B translates deferred open-set filters against unique values observed
   in those datapoints.
8. Stage 3 applies valid runtime post-filters and returns the final filtered
   datapoints plus audit metadata.

## Integration Surface
- Safety, PK, and RTB service families share the staged approach but differ in
  field maps, facets, invariants, entity routing, and output surface.
- Closed-set vocabularies come from the documented input taxonomies and inline
  enum/boolean domains.
- The per-field SME gold set and the per-step SME gold set are evaluation
  references.
- Optional entity-recognition and language-model integrations are used only when
  selected.

## Operational Model
- Every stage is selectable by name and can be run in isolation.
- Offline doubles keep local tests and offline evaluation hermetic.
- Live execution can call the PharmaPendium API. The documented target flow fetches
  rows for runtime closed-set post-filtering; the current v0.1 flow reads counts
  and uses isolated zero-count probes as the open-set guard.
- The interactive UI is a debug surface: it shows stage configuration, a gold-set
  question picker, each stage output, the final payload, and optional execution.

## Constraints and Non-Goals
- Closed-set filters must never emit values outside their closed set.
- Invalid closed-set or runtime-closed translations must be recorded and ignored
  downstream rather than applied as hard filters.
- Boolean intent must stay explicit both within a field and across fields.
- Stage 1 must segment and route; value normalization and grounding belong later.
- The product consumes vocabularies and gold sets; it does not curate them.
- The product produces machine queries and filtered datapoints; it is not a
  general conversational assistant or a record summarizer.
- Count metrics are tolerance-banded because live database counts can drift.

## Open Questions
None at product level after the documented clarification pass. The remaining gap
is implementation status: the row-level runtime closed-set path is the desired
product behavior, while the current package still uses count execution and
zero-count probes for open-set protection.
