# Misspelling handling (pluggable)

Users misspell things — "suntinib", "cabozantininb", "Columvi" for Glofitamab,
"non small lung cancer". The pipeline must tolerate this **without** baking one
correction approach into the core. So misspelling handling is defined here as a
**pluggable strategy** with a fixed interface; *which* concrete strategy we use
is a later decision.

> **Status:** interface only. The concrete normalizers are deliberately left
> open — see [Open decisions](#open-decisions). The point now is that Stage 2 has
> a single, swappable seam to hang them on.

## Where it plugs in

Normalization runs **inside Stage 2**, on the `nl_fragment`, *before* the field's
value is produced — for both field buckets, but with different defaults:

```
nl_fragment ─▶ [ Normalizer for this field ] ─▶ cleaned fragment ─▶ value production
                                                                     (CSV lookup | LLM)
```

- **Closed-vocab fields** — the normalizer's job is to bridge the misspelling to a
  real taxonomy entry (the CSV is the ground truth, so we can be aggressive).
- **Open fields** — there is no vocabulary to anchor to, so correction is
  necessarily lighter / more conservative (we must not "correct" a deliberate
  free-text term into the wrong thing).

This keeps misspelling logic out of Stage 1 (routing) and Stage 3 (assembly).

## The interface

One small contract, implemented by any strategy:

```
normalize(fragment: str, field: str, bucket: "closed" | "open", context) -> {
  normalized: str,            # the fragment to use downstream (may == input)
  candidates?: [              # optional ranked alternatives (esp. closed-vocab)
    { value: str, id?: str, score: 0..1, source: "exact"|"fuzzy"|"phonetic"|"llm"|... }
  ],
  changed: bool,              # did we alter the fragment?
  confidence: 0..1,           # how sure we are the correction is right
  note?: str                  # human-readable explanation (audit trail)
}
```

Strategies are **registered per bucket** (and optionally overridden per field), so
swapping one in/out is a config change, not a code change:

```
normalizers = {
  "closed": <ClosedVocabNormalizer>,   # default for all closed-vocab fields
  "open":   <OpenFieldNormalizer>,     # default for all open fields
  "drugs":  <DrugNormalizer>,          # optional per-field override
}
```

A **no-op normalizer** (`changed=false`, `normalized==input`) is the baseline, so
the pipeline works end-to-end before any real strategy is chosen.

## Candidate strategies (to choose from later)

These are options to evaluate, **not** decisions:

| Strategy | Fits | Idea |
|----------|------|------|
| No-op | both | passthrough; baseline / disable |
| Fuzzy match | closed | edit-distance / token-set ratio against the field's CSV; reuses the Stage-2 lookup index |
| Phonetic | closed | Soundex/Metaphone keys over CSV names for sound-alike typos |
| TERMite-first | closed | trust TERMite's preferred label when it already resolved the (mis)spelled surface |
| LLM correction | both | ask the model for the most likely intended term, optionally constrained to candidate values |
| Hybrid | both | fuzzy/phonetic to shortlist from CSV, LLM to disambiguate the shortlist |

For **open** fields the realistic choices are no-op, a generic spell-checker, or
light LLM correction — there is no CSV to validate against.

## Confidence handling (deferred)

How we *act* on `confidence` is part of the later decision. Sketch of the options
the interface already supports:

- **high** → silently use `normalized`;
- **medium** → use it but surface the correction (`note`) for transparency;
- **low / ambiguous** → keep candidates and let the orchestrator decide (ask the
  user, try top-N, or drop the constraint) rather than guess.

Crucially, for closed-vocab fields a correction is only "valid" if it lands on a
real CSV entry — this reuses the final grounding check in
[stage-3-aggregation.md](stage-3-aggregation.md), so a bad correction can't slip
through as an invented value.

## Open decisions

- Which concrete normalizer per bucket (and which per-field overrides)?
- The confidence thresholds and the medium/low actions above.
- Whether open-field correction is worth the risk of "fixing" intentional terms.
- Whether normalization is one pass or iterative (correct → lookup → re-correct on
  miss).

These are intentionally unresolved; this doc only fixes the **seam** so any of the
above can be dropped in later without touching Stage 1 or Stage 3.
