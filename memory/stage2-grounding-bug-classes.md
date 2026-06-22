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
- **D. MedDRA family rollup replaced the term & weak anchors hijacked it.** 'Mutagenicity'
  -> narrow NEC family (32 vs 445); 'positive Ames Test' -> foetal family (shared 'positive'/
  'test' @86). Fixes: rollup is ADDITIVE (keep canonical + original fragment); gate non-exact
  anchors at fuzzy>=95; strip result-qualifier words (positive/negative/abnormal/...) before
  grounding so assay phrases key on the assay name ('Ames Test' -> Ames family). Case 19 -> 180.
- **Case 8 correction:** a TERMite TARGET must NOT unconditionally route to `targets`. When
  '<target> inhibitors' is a real drug-class node, prefer the drug class (Kinase inhibitors ->
  1851) over targets=Kinases (6980). `_drug_class_for_mechanism` in decompose.py.

**Method that worked:** dispatch one investigation subagent per failing case (read-only:
run `oppp run`, then probe the LIVE API with isolated MachineQuery+execute_count to find which
constraint zeroes/400s it), aggregate root causes in the main agent, fix the *classes* not the
cases. See [[enhancer-annotations-must-flow-downstream]].

**Gold/data caveats (NOT code bugs):** offline eval (gazetteer+deterministic, no LLM/TERMite)
can't ground synonyms/NOEL/MTD -> 0s that production fixes; some gold counts are stale
(row 13 'neutropenia or thrombo' gold 68809 but its own JSON returns 61874 live) or were
measured on a fuller dataset than the dev API (case 21 GI/arrhythmia has no Human records on
dev). Re-baseline gold against the same API the eval hits before trusting a "miss".
