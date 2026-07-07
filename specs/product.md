# Product Specification

## Sources
- `docs/README.md`
- `docs/index.md`
- `docs/agent-dag.drawio`
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
The product converts a natural-language PharmaPendium question into the machine
query and filtered datapoints needed to answer it. It replaces the legacy
single-prompt translator with a fixed, auditable pipeline that separates
question expansion, entity recognition, decomposition, grounded translation,
aggregation, execution, and post-filtering.

The central product rule is: a filter value must be grounded before it can narrow
results. Input fields whose possible values are already known are translated
against their closed sets. Fields whose values are not known before retrieval are
deferred until datapoints have been fetched; the unique fetched values then become
runtime closed sets, and the same translation rules decide the post-filter.

## Core Capabilities
- Accept a natural-language question for Safety, PK, or RTB and produce the
  corresponding machine-query surface for that service.
- Preserve the original question while producing a faithful expansion that
  clarifies abbreviations and wording without adding or removing intent.
- Always run TERMite entity recognition before decomposition. TERMite supplies
  labels, entity types, and synonyms that seed later stages; it is not optional.
- Decompose the enhanced question into single-field components, each marked as a
  retrieval filter or a requested output/question.
- Translate closed-set filters by exact matching, fuzzy matching, LLM pool
  enrichment, exact/fuzzy retry, and final LLM selection from the closed set.
- Treat any empty, missing, or out-of-set translation as invalid. Invalid input
  closed-set filters are recorded but do not narrow the API query.
- Support domain grounding behavior for drug classes, species groups, effect
  families, route/source/parameter taxonomies, booleans, enums, and curated
  preclinical/non-clinical concepts.
- Aggregate valid input closed-set filters into a structurally valid first API
  query with service invariants, entity filters, facets, and display columns.
- Fetch datapoints, derive runtime closed sets for deferred open-set fields,
  translate those runtime fields, and apply valid post-filters.
- Keep stage outputs inspectable through fixed stage commands and the UI without
  exposing alternative stage methods or no-op bypasses.
- Evaluate quality per step, per field, and end to end against SME gold sets.

## Key Actors
| Actor | Role |
|-------|------|
| Analyst | Asks the natural-language question and consumes the filtered evidence. |
| Subject-matter expert | Provides gold questions, expected mappings, counts, and notes on legacy failures. |
| Developer / evaluator | Runs fixed stages, inspects traces, updates tests, and evaluates regressions. |
| PharmaPendium search service | Executes machine queries and returns counts or datapoints. |
| TERMite entity recognizer | Supplies required entity labels, types, and synonyms before decomposition. |
| Language model | Performs faithful expansion, vocab-free decomposition, translation enrichment/selection, aggregation planning, and semantic judging where needed. |

## Data Flow
1. The raw question enters the fixed pipeline.
2. Stage -1 expands the question faithfully and preserves the original.
3. Stage 0 runs TERMite and attaches recognized entity annotations.
4. Stage 1 emits one component per field concept, preserving filter/question
   roles and boolean hints without choosing taxonomy values.
5. Stage 2A translates input closed-set filter components against known
   vocabularies, inline enums, and booleans.
6. Stage 3 aggregates valid Stage 2A filters into the first API query and fetches
   datapoints.
7. Stage 2B translates deferred open-set filters against unique values observed
   in those datapoints.
8. Stage 3 applies valid runtime post-filters and returns the final filtered
   datapoints plus audit metadata.

## Integration Surface
- Safety, PK, and RTB share the same pipeline shape but differ in fields,
  buckets, facets, invariants, entity routing, and output serialization.
- Closed-set vocabularies come from the documented input CSV taxonomies, inline
  enum values, and boolean domains.
- Open-set fields become runtime closed sets only after datapoints are fetched.
- TERMite annotations help route and ground entities, but CSV and runtime closed
  sets remain the authority for emitted values.
- The per-field SME gold set and the per-step SME gold set are required
  evaluation references.

## Operational Model
- The production path has no user-selectable stage methods and no no-op bypass.
- TERMite credentials and model credentials are required for production runs that
  invoke the full pipeline.
- Stage commands remain available for inspection, but each command runs the fixed
  method for that stage.
- Local tests may use injected fakes or fixtures to stay deterministic, but those
  fakes are not product methods and must not be exposed as stage choices.
- Live execution can call the PharmaPendium API. Count retrieval remains useful
  for evaluation and debugging, while row retrieval is required for runtime
  closed-set post-filtering.
- The interactive UI is a debug surface for the same fixed pipeline: it shows
  expansion, TERMite annotations, decomposition, translations, aggregation,
  execution, runtime closed sets, post-filters, and issues.

## Constraints and Non-Goals
- Closed-set filters must never emit values outside their closed set.
- Runtime post-filters must never emit values outside the fetched runtime closed
  set.
- Invalid translations must be visible in the audit trail and ignored downstream.
- Boolean intent must stay explicit both within a field and across fields.
- Stage 1 must segment and route; value normalization and grounding belong later.
- The normalizer policy is fixed by field/bucket and is not a selectable stage.
- The product consumes vocabularies and gold sets; it does not curate them.
- The product produces machine queries and filtered datapoints; it is not a
  general conversational assistant or a record summarizer.
- Count metrics are tolerance-banded because live database counts can drift.

## Open Questions
None at product level after the documented clarification pass. The remaining work
is implementation alignment: the current package still exposes old stage options,
no-op paths, count-only execution, and probe-based open-field guards that must be
replaced or confined so the documented fixed pipeline is the product behavior.
