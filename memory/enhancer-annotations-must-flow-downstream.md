---
name: enhancer-annotations-must-flow-downstream
description: Stage-0 TERMite annotations must be authoritative inputs to later stages, not just prompt hints
metadata:
  type: project
---

In opt-pp (oppp pipeline), the Stage-0 enhancer (TERMite) recognizes entities and
resolves them to preferred labels/types, but the vocab-free LLM decomposer and the
grounding translator historically ignored those annotations except as a text hint
block. This caused zero-result queries twice:

- NOAEL bug: "No Observed Adverse Effect Level" enhanced to `NOAEL`, but Stage 2
  grounded the raw phrase (0.00 confidence). Fix: thread `enhanced.annotations` into
  the translator; ground the matching preferred label first (verified against the
  CSV) — the documented but unimplemented "resolution-order step 1".
- "inhibitors of kinases" bug — needed THREE fixes (verified live: 0 -> 6980 records;
  gold sheet says 1851 but it's marked preliminary, the 6980 shape is correct):
  1. routing: decomposer put the phrase on `drugs` (fuzzy garbage). Fix:
     `reconcile_with_annotations` in [stages/decompose.py] reroutes to `targets` when a
     TARGET annotation's surface appears in the fragment.
  2. targets value: the `DrugsTargets` entityFilter matches the TERMite preferred label
     `Kinases` (213673 records), NOT the raw `inhibitors of kinases` (0). `targets` is an
     *open* field (no CSV); fix in `_translate_open` emits the matching-type annotation's
     label for entity-routed open fields.
  3. route flakiness: `IV administration` has NO ROUTE annotation and no fuzzy match in
     route.csv (IV->intravenous is unbridgeable by fuzz). The empty-pool LLM map
     (`_llm_map_to_vocab`) resolves it but is ~50% flaky per call even at temp 0, so
     route intermittently emitted raw `IV administration` (0 records). Fix: retry+union
     over `attempts=3`. General, no hard-coded "IV".

**Why:** the LLM stages route/copy by intuition and won't reliably honour the hint
block; and single LLM fallback calls are non-deterministic. **How to apply:** when a
query returns 0 (or nonsense) datapoints, PROBE THE LIVE API with isolated constraints
(build MachineQuery + execute_count) to find which constraint zeroes it — don't trust
the simulation. Then check whether TERMite already had the right answer in
`enhanced.annotations`. Prefer deterministic annotation-driven fixes + LLM-call
resilience (retry/union) over prompt tweaks or per-phrase special cases.
Gold set: docs/sme_stage_cases.csv (row 9 = kinase target case, row 21 = CDk4 drug case).
Caveat from `llm_select=False` simulations: they pass raw unmatched values through, which
can *look* like the gold value but actually return 0 — always verify against the API.
