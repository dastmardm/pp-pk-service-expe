---
name: stage2-grounding-bug-classes
description: Recurring Stage-2 grounding bug classes in oppp and their general fixes (from the eval sweep)
metadata:
  type: project
---

A parallel-subagent sweep of the `oppp eval` gold cases (docs/sme_stage_cases.csv)
surfaced 5 generalizable Stage-2 grounding bugs (all fixed in stages/translate.py +
stages/decompose.py, verified live against the API). Keep these in mind when a case
returns 0 / nonsense / HTTP 400:

- **A. Annotation bound by field-type, not fragment.** `_annotation_hit` returned the
  *first* same-typed TERMite annotation, so 'rats or mice' -> OR(Mouse,Mouse),
  'neutropenia or thrombocytopenia' -> both = first effect. Fix: `_annotation_corresponds`
  requires correspondence. CRITICAL SUBTLETY: a naive "surface must overlap fragment"
  guard RE-BREAKS abbreviation annotations (TERMite tags 'No Observed Adverse Effect
  Level' with surface/label 'NOAEL' — no textual overlap -> NOAEL bug returns, 0 results).
  Correct rule = textual overlap OR no-grounding-conflict: bind even when surfaces differ
  UNLESS the fragment itself self-grounds (exact/high-fuzzy) to a DIFFERENT vocab entry
  than the annotation label. 'Rat' self-grounds to Rat (conflict with lone 'Mouse' ann ->
  reject); 'No Observed Adverse Effect Level' self-grounds to nothing (no conflict ->
  NOAEL binds). Verify BOTH the multi-value case AND an abbreviation case after any change.
- **A2. Retrieval-defining entity left as a question.** 'What is the MTD of X' -> decomposer
  emits toxicityParameter as a QUESTION (column), dropping the filter -> overbroad (2292 vs
  4). Fix: `_reconcile_retrieval_defining_filters` promotes a recognized tox-parameter
  question to a FILTER on the TERMite label. General over `_RETRIEVAL_DEFINING_FIELDS`.
- **B. Trailing '*' on a multi-word drugsFuzzy value -> HTTP 400.** API rejects
  'CDk4 inhibitors*', 'Monoclonal antibodies*'. Fix: only append '*' to single-token values.
- **C. Class expansion inlined all children -> HTTP 400 / redundant.** Inlining 100+ members
  busts the API's ~49-value-per-MATCH-list cap. Fix: emit the class LABEL; the API resolves
  it server-side (verified species='Rodent' == 14 members == 344917; drugsFuzzy='Kinase
  inhibitors' resolves the class). Added index.class_label()/class_hit().
- **C2. Colloquial species plural not a taxonomy class.** 'Monkeys' has no own node (parent is
  'Primate'), so it fuzzy-matched only 'Monkey (unspecified)' (case 22: 14 vs 27). Fix:
  index.class_label() falls back to the common parent when the singularised term is a
  standalone word in >=2 entries sharing ONE parent (Monkeys->Primate->27). Guards: skip if the
  term is itself an exact leaf (Mouse/Rat must NOT widen), require a single shared parent (rats
  spans Rodent/Mollusc/Marsupial -> skip).
- **D. MedDRA family rollup replaced the term & weak anchors hijacked it.** 'Mutagenicity'
  -> narrow NEC family (32 vs 445); 'positive Ames Test' -> foetal family (shared 'positive'/
  'test' @86). Fixes: rollup is ADDITIVE (keep canonical + original fragment); gate non-exact
  anchors at fuzzy>=95; strip result-qualifier words (positive/negative/abnormal/...) before
  grounding so assay phrases key on the assay name ('Ames Test' -> Ames family). Case 19 -> 180.
- **Case 8 correction:** a TERMite TARGET must NOT unconditionally route to `targets`. When
  '<target> inhibitors' is a real drug-class node, prefer the drug class (Kinase inhibitors ->
  1851) over targets=Kinases (6980). `_drug_class_for_mechanism` in decompose.py.
- **E. OOV closed-vocab term emitted as a hard MATCH -> silent zero.** When a closed field
  grounds to NOTHING (no exact/fuzzy/LLM hit), the old fallback emitted `values=[term]` (the
  raw ungrounded phrase) as a MATCH -> an AND with a value in no record zeroes the WHOLE query
  ('non clinical species' killed case 15; ungrounded 'maternal toxicity' in effects killed case
  11). Fix (CONST-1, user-confirmed "drop it, don't contribute downstream"): mark the subquery
  `dropped=True` (translate.py unmatched branch); `_drop_ungroundable` in aggregate.py excludes
  it from the tree/entityFilters/budget and logs a warning. Query returns the valid superset, not 0.
- **F. Free-text field keeps the query's relational glue.** Decomposer copies surface words, so
  `parameterComment` arrived as 'related to maternal toxicity'; the API matches the substantive
  phrase ('maternal toxicity', and it's CASE-SENSITIVE lowercase here). `_strip_leading_connective`
  (translate.py) drops a leading connective (related to|associated with|due to|for|of|in|...) for
  plain (non-entity, non-regex) open fields. Case 11 -> 1 (SME gold; docs gold 2 is stale).
- **Field-routing prompt rules (decompose.py `_build_prompt`):** added a "route by MEANING not
  keyword" block: (a) an adverse event the drug CAUSES is `effects`; a phrase QUALIFYING the
  study/parameter context ('related to maternal toxicity') is free-text `parameterComment`. (b)
  'single/repeated administration|dose(s)' is `doseType`, not studyGroup/ages. (c) 'preclinical /
  non-clinical / non clinical species' is the boolean `isPreclinical=true` (NEVER a literal species
  value). `_translate_boolean` now parses preclinical phrasing -> True.
- **Preclinical modelling (user decision 2026-06-22):** route to `isPreclinical=true` (semantically
  correct) EVEN THOUGH the dev API underpopulates the flag (case 15: isPreclinical=true -> 6-10 vs
  the ~166 you'd get unconstrained). Honest modelling over chasing the gold count on quirky dev data.

**Method that worked:** dispatch one investigation subagent per failing case (read-only:
run `oppp run`, then probe the LIVE API with isolated MachineQuery+execute_count to find which
constraint zeroes/400s it), aggregate root causes in the main agent, fix the *classes* not the
cases. See [[enhancer-annotations-must-flow-downstream]].

**Gold/data caveats (NOT code bugs):** offline eval (gazetteer+deterministic, no LLM/TERMite)
can't ground synonyms/NOEL/MTD -> 0s that production fixes; some gold counts are stale
(row 13 'neutropenia or thrombo' gold 68809 but its own JSON returns 61874 live) or were
measured on a fuller dataset than the dev API. Re-baseline gold against the same API the eval
hits before trusting a "miss".
- **Case 21 (GI disorder + arrhythmia + Human + IV + single) is UNWINNABLE on dev:** there are
  1628 GI+Human rows, 32 are IV, 78 are single-dose, but ZERO are both IV AND single-dose. The
  SME-shaped query (full arrhythmia family + Human + Single + Intravenous) also returns 0 live.
  Pure data gap; the route value is already correctly grounded to 'intravenous'. Don't chase it.
- **Case 20 (CDk4 inhibitors / NOEL / mice) needs a TARGETS canonical spelling we can't reach:**
  'CDk4 inhibitors' is routed as drugsFuzzy (no such drug -> 0). SME-correct query routes via
  DrugsTargets with the EXACT label 'Cyclin-dependent kinase 4 (CDK4)' (any other spelling -> 0)
  AND toxicityParameter=NOEL + Mouse -> 2 live. Blockers: TERMite tags NO target for CDk4 (so
  `_reconcile_target_mechanism`, which is TERMite-TARGET-gated, never fires), and `targets` is an
  open field with no taxonomy CSV, so we can't normalise the spelling to the parenthesised canonical.
  Fixable only by (i) rerouting unmatched-drug-class '<X> inhibitor(s)' to targets WITHOUT requiring
  a TERMite tag, plus (ii) a targets vocab/LLM-map for the canonical label. Deferred.
