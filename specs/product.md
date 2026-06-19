# Product Specification

## Sources

Synthesised exclusively from the human-facing documentation under `./docs/`:

- `docs/README.md`
- `docs/00-overview/problem-statement.md`
- `docs/00-overview/glossary.md`
- `docs/01-current-system/legacy-architecture.md`
- `docs/01-current-system/pain-points.md`
- `docs/02-domain-inputs/machine-query-schema.md`
- `docs/02-domain-inputs/field-taxonomy.md`
- `docs/02-domain-inputs/csv-catalog.md`
- `docs/03-proposed-design/architecture.md`
- `docs/03-proposed-design/stage-1-decomposition.md`
- `docs/03-proposed-design/stage-2-subquery-translation.md`
- `docs/03-proposed-design/stage-3-aggregation.md`
- `docs/03-proposed-design/grounding-and-tool-calling.md`
- `docs/03-proposed-design/misspelling-strategy.md`
- `docs/04-examples/worked-examples.md`
- `docs/05-evaluation/gold-set-and-metrics.md`
- `docs/06-implementation/tech-stack.md`
- `docs/06-implementation/build-status.md`
- `docs/06-implementation/streamlit-ui.md`
- `docs/sme_stage_cases.csv` (per-step SME gold set; preliminary)
- `docs/agent-dag.png` (component diagram asset, referenced by `docs/README.md`)

## Purpose

Turn a user's natural-language question about drug safety and pharmacology into a
structured **machine query** that the PharmaPendium search service can execute.

The system replaces a single monolithic prompt — which read a whole question and
emitted the entire machine query in one model call — with a **chain of small,
independently-testable steps**. The monolith relied entirely on model judgement,
invented field values that did not exist in the controlled vocabularies,
mishandled hierarchical concepts (drug classes, species classes, effect
roll-ups), bundled every rule into one unmaintainable body of text, and could not
be improved or measured one field at a time. The decomposed design exists to fix
exactly those failures, each of which is documented against subject-matter-expert
(SME) review of real questions.

The guiding principle is **ground, don't generate**: when a field's complete set
of legal values is already known (it exists as a controlled vocabulary), the
system must *select* the value from that vocabulary rather than let the model
*invent* one. Only fields whose value space cannot be enumerated are left to free
model judgement.

## Core Capabilities

- **CAP-1 — Question to machine query.** Accept a natural-language question and
  produce the structured machine query (a boolean tree of filters, plus optional
  grouped-count facets, display columns, and entity-linked filters) that the
  search service accepts.
- **CAP-2 — Optional entity enhancement (pre-step).** Before anything else,
  optionally recognise the entities in the raw question and attach their preferred
  labels and types. This step is **optional and off by default**; it is a booster
  that improves later steps, not a required safeguard.
- **CAP-3 — Decomposition.** Split the question into many single-field fragments,
  routing each fragment to the field it concerns and classifying it as either a
  **filter** (it narrows which records are retrieved) or a **question** (it states
  something to report from the retrieved records, e.g. "at which dose"). This step
  only segments and routes using the user's own words; it does not resolve,
  normalise, or consult any vocabulary.
- **CAP-4 — Per-field translation with grounding.** Translate each filter fragment
  independently into a single machine filter. For **closed-vocabulary fields**
  (those backed by a controlled vocabulary), the value is grounded against that
  vocabulary and, where the user named a class or roll-up, expanded along the
  vocabulary's hierarchy to the intended member/term set. For **open fields**
  (those whose values cannot be enumerated), the model decides the value directly
  (typically a free-text pattern or a numeric range).
- **CAP-5 — Misspelling tolerance.** Tolerate user misspellings via a swappable
  normalisation step that runs before a field's value is produced — aggressive for
  closed-vocabulary fields (the vocabulary anchors the correction), conservative
  for open fields (no vocabulary to validate against). The concrete strategy is a
  configuration choice with a no-op baseline.
- **CAP-6 — Aggregation.** Assemble the per-field filters into the final machine
  query: combine them with the correct boolean structure (both within a field and
  across fields), route fields that must go through a linked entity, attach the
  appropriate grouped-count facets and display columns, apply the service-specific
  rules that are always required but never stated by the user, and validate the
  result before returning it.
- **CAP-7 — Step isolation & pluggability.** Every step is selectable by name and
  runnable on its own, so any single step can be exercised, measured, and improved
  without standing up the rest of the chain. Offline stand-ins exist for every
  model-backed step so the system can run end-to-end with no external model or
  network call.
- **CAP-8 — Per-step, per-field and end-to-end evaluation.** Measure quality at
  three granularities against SME gold sets: each step's output in isolation, each
  field's resolved value, and the end-to-end result count. Some steps emit
  free-text outputs with no single correct form and are therefore scored by an
  **LLM-as-judge** rather than exact match.
- **CAP-9 — Interactive inspection.** Offer an interactive way to run a question
  (typed, or picked from the gold set) and inspect every step's intermediate
  output, while selecting each step's backend, so a reviewer can see exactly where
  a wrong result originated.

## Key Actors

| Actor | Role |
|-------|------|
| **End user / analyst** | Asks a natural-language question; ultimately consumes the records the machine query retrieves. |
| **Subject-matter expert (SME)** | Curates the gold sets — the expected per-field values and the expected per-step outputs — and records where the legacy system failed. |
| **Developer / data scientist** | Runs the chain, isolates and evaluates individual steps, tunes the model-backed steps, and extends the system to new services. |
| **PharmaPendium search service** *(external)* | Executes the machine query and returns matching records and counts. |
| **Entity-recognition service** *(external)* | Recognises entities in the raw question and returns preferred labels/types for the optional enhancement step. |
| **Language-model provider** *(external)* | Backs the decomposition, open-field translation, term selection, aggregation-structure, and judge steps. |

## Data Flow

1. A natural-language question enters the system.
2. *(Optional)* The **enhancement** step annotates recognised entities with
   preferred labels/types.
3. **Decomposition** splits the (optionally enhanced) question into single-field
   fragments, each routed to a field and classified filter-vs-question.
4. **Per-field translation** turns each filter fragment into one machine filter —
   grounding closed-vocabulary values against the controlled vocabulary (with
   hierarchy expansion) and letting the model decide open-field values.
5. **Aggregation** combines the filters into the final boolean machine query,
   routes entity-linked fields, attaches facets/display columns, applies
   service-specific always-on rules, and validates.
6. The machine query is returned, and may be executed against the search service
   to obtain a result count.

Every intermediate artefact (annotations, components, filters with their grounding
provenance, the final query, validation issues) is retained so a run is auditable
end to end.

## Integration Surface

- **PharmaPendium search service** — receives the machine query and returns
  matching records / a total result count. Three target collections are in scope
  as a family: **Safety** (adverse effects / toxicity), **PK** (pharmacokinetics),
  and **RTB** (Reaxys bioactivity / CrossFire). Safety and PK exchange the same
  structured shape; RTB uses a different surface form expressing the same
  underlying set of filters.
- **Entity-recognition service** — supplies preferred labels and entity types for
  the optional enhancement step.
- **Language-model provider** — backs the model-driven steps and the judge.
- **Controlled vocabularies** — the on-disk taxonomies of legal values for
  closed-vocabulary fields (drugs, effects, indications, species, route, sources,
  toxicity parameters, dose type, document year), several of which are
  hierarchical (a parent class and its members/terms).
- **SME gold sets** — the per-field expected-values set and the preliminary
  per-step expected-outputs set, used as the evaluation references.

## Operational Model

- The system is operated by developers and reviewers, not end users directly: it
  is exercised through a command-line surface (full run, single-step isolation,
  vocabulary lookup, evaluation) and an interactive inspection surface.
- It runs locally. A **deterministic core** (vocabulary lookup, aggregation
  assembly, validation, evaluation bookkeeping) runs with no external model or
  network dependency, using offline stand-ins for the model-backed steps. The
  **production configuration** uses the model-backed steps and the live search
  service.
- Evaluation defaults to the offline stand-ins (cheap, no model calls) but, by
  default, still executes the resulting query against the live service to obtain a
  count; a fully offline, validity-only mode is available.
- External-model and entity-recognition backends require their own credentials and
  are only invoked when explicitly selected; the deterministic core never needs
  them.

## Constraints and Non-Goals

- **Ground, don't generate.** For a closed-vocabulary field, the system must not
  emit a value that does not exist in the controlled vocabulary; on no match it
  surfaces the gap rather than inventing a value.
- **Steps stay independent and isolatable.** No step may become un-testable in
  isolation; the offline stand-ins must keep the test suite and per-step evaluation
  runnable without external services.
- **Faithful boolean intent.** Boolean structure (within a field and across
  fields) must be explicit and auditable, never implicit in prose.
- **Not a general chatbot.** The system answers only by producing a machine query
  for the search service; it does not converse, summarise records, or answer
  outside the search domain.
- **Not a vocabulary editor.** The system consumes the controlled vocabularies and
  gold sets; it does not curate or author them.
- **Current realised scope is the Safety service** with the documented offline and
  model-backed paths; PK and RTB are designed-for but not yet realised.

## Open Questions

These are recorded as **open in `./docs/`** (the human source of truth has not
settled them); they are carried here as open questions, not asserted facts.

- **`targets` vocabulary.** The gold set uses drug targets, and targets are listed
  among the resolvable vocabularies, but no `targets` vocabulary table is shipped.
  Should one be exported, or should targets be resolved via the search service's
  fuzzy-lookup at run time? (`docs/03-proposed-design/architecture.md` → Open
  questions; `docs/02-domain-inputs/field-taxonomy.md`.)
- **Effect roll-ups (MedDRA).** Is the parent/child structure already present in
  the effects vocabulary sufficient, or is the full MedDRA hierarchy required?
  (`docs/03-proposed-design/architecture.md`; `docs/01-current-system/pain-points.md`.)
- **Class-vs-target disambiguation.** When a term could be a drug class or a
  target, does decomposition disambiguate, or does translation attempt both
  look-ups and let confidence decide? (`docs/03-proposed-design/architecture.md`,
  `docs/03-proposed-design/stage-1-decomposition.md`.)
- **Enhancement vs grounding boundary.** Where does the entity-recognition step
  stop and the vocabulary look-up begin, given both can resolve preferred labels?
  (`docs/03-proposed-design/grounding-and-tool-calling.md`.)
- **Decomposition granularity.** One fragment per field, or one per concept
  (recombined later)? (`docs/03-proposed-design/stage-1-decomposition.md`.)
- **Misspelling strategy choice.** Which concrete normalisation strategy per
  bucket, the confidence thresholds, whether open-field correction is worth the
  risk, and one-pass vs iterative correction. (`docs/03-proposed-design/misspelling-strategy.md`
  → Open decisions.)
- **Per-step gold set maturity.** The per-step gold set is explicitly preliminary:
  its shorthand notation and exact expansions will change as the per-step
  evaluators are built. (`docs/05-evaluation/gold-set-and-metrics.md` → Status &
  next steps.)
