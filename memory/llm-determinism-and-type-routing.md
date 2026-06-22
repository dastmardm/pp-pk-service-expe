---
name: llm-determinism-and-type-routing
description: oppp LLM reproducibility settings + the decomposer filter-vs-question routing rules
metadata:
  type: project
---

**Reproducibility:** all oppp LLM calls are built in ONE place — `llm.py:get_chat_model`
— with `temperature=0`, `top_p=0`, and a fixed `seed` (env `LLM_SEED`, default 7). A
test (`test_every_llm_call_is_built_for_reproducibility`) enforces all three. IMPORTANT:
temperature=0 alone is NOT deterministic for hosted models (batched-GPU float
non-associativity, MoE routing, provider load-balancing); seed+top_p+temp0 together are
the strongest knobs but still best-effort. Lesson learned the hard way: adding the seed
made a query STABLY return the WRONG answer (it froze a misclassification) — determinism
exposes correctness bugs rather than hiding them in run-to-run flapping. Always pair a
determinism change with a correctness check.

**Decomposer type-routing (filter vs question)** — fixed in the LLM prompt
(`LLMDecomposer._build_prompt`), per the "fix bugs at the stage that causes them"
principle [[fix-bugs-at-the-stage-that-causes-them]]:
- The interrogative HEAD NOUN being asked for is a QUESTION (reported column), not a
  filter: 'What are the <X> ...', 'which <X>', 'at which <X>' -> <X> head noun is a
  question. Modifying clauses on it ('causing <effect>', 'treating <disease>', 'of
  <drug>', 'in <species>') are FILTERS on their own fields.
- A bare field name with NO value (trailing 'at which dose, dosing regimen and route?')
  is a QUESTION per field — NEVER a filter like dose='dose'/route='route' (those junk
  filters zero the query). A field is a filter only with a concrete value.
- 'drugs treating/causing/for <condition>': 'drugs' is the generic head noun (a
  question/output), the <condition> routes to indications/effects — never a `drugs`
  filter on the carrier phrase (it fuzz-grounds to 'Cytotoxic drugs' -> 0). Only emit a
  `drugs` filter for a SPECIFIC named drug/class (Sunitinib, kinase inhibitors).

Verified live: C6 neutropenia 0/2.6M->37829, C14 NSCLC 91->13559, C1 4300, C8 1851 — all
stable across repeated runs after seed+prompt. Gold: docs/sme_stage_cases.csv.
