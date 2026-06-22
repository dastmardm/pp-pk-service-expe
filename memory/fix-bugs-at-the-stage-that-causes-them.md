---
name: fix-bugs-at-the-stage-that-causes-them
description: Fix a pipeline bug in the stage that produced it (e.g. decomposer prompt), not with a downstream patch
metadata:
  type: feedback
---

When a mis-routing originates in the LLM decomposer (Stage 1), fix it by editing the
**decomposer prompt** (`LLMDecomposer._build_prompt` in stages/decompose.py) — do NOT
add a downstream deterministic scrub (regex/`reconcile_*`) to undo what the LLM got
wrong. The user pushed back hard on a regex band-aid (`_demote_carrier_drug_filter`)
that stripped a spurious `drugs` filter after decomposition; the correct fix was a
prompt rule telling the decomposer not to emit it in the first place.

Concrete case: "adverse events for **drugs treating** non small cell lung cancer" — the
LLM emitted a `drugs` filter on the carrier phrase ("drugs treating ...") which
fuzz-grounded to 'Cytotoxic drugs' and returned 0. Fix = prompt rule: only emit a
`drugs` filter when a SPECIFIC drug/class is named; the bare head noun "drugs" in
"drugs treating/causing/for <condition>" is the reported output (a `question`), and the
<condition> routes to indications/effects. Verified -> 13559 (gold), and Sunitinib /
kinase-inhibitor drug filters still retained.

**Why:** patching symptoms downstream is brittle and hides the real defect; the stage
that makes the decision should make it correctly. **How to apply:** before writing a
post-hoc cleanup pass, ask "which stage *produced* this wrong output?" and fix that
stage. Reserve deterministic reconciliation for things the LLM genuinely cannot know
(e.g. honouring a TERMite preferred label), not for teaching it judgement a prompt can
convey. NOTE: this means the earlier `reconcile_with_annotations` rules are borderline —
prefer prompt fixes there too when the signal is judgement the LLM could learn.
See [[stage2-grounding-bug-classes]].
