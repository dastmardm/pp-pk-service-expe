# Misspelling handling (pluggable)

Users misspell things: "suntinib", "cabozantininb", "Columvi" for Glofitamab,
"non small lung cancer". The pipeline tolerates this through a **pluggable
normalizer** with a fixed interface. The default configuration provides a no-op
baseline and a fuzzy closed-set normalizer; field-specific normalizers can be
registered without changing Stage 1 or Stage 3.

## Where it plugs in

Normalization runs **inside Stage 2**, on the `nl_fragment`, before translation
against the field's closed set:

```text
nl_fragment -> [normalizer for this field] -> cleaned fragment -> closed-set translation
```

- **Input closed-set fields**: the normalizer bridges misspellings toward a real
  CSV, enum, or boolean entry.
- **Runtime closed-set fields**: normalization stays conservative before the API
  call; after datapoints are fetched, the runtime closed set anchors exact and
  fuzzy matching.

In v0.1, the implemented `fuzzy` normalizer only corrects CSV-backed closed-set
fields. Open-set fields pass through conservatively; their current protection is
surface cleanup in translation plus optional zero-count probing in live runs.

This keeps misspelling logic out of Stage 1 routing and Stage 3 assembly.

## The interface

One small contract is implemented by every strategy:

```text
normalize(fragment: str, field: str, bucket: "closed" | "open", context) -> {
  normalized: str,
  candidates?: [
    { value: str, id?: str, score: 0..1, source: "exact"|"fuzzy"|"phonetic"|"llm"|... }
  ],
  changed: bool,
  confidence: 0..1,
  note?: str
}
```

Strategies are registered per bucket and may be overridden per field:

```text
normalizers = {
  "closed": <ClosedSetNormalizer>,
  "open":   <ConservativeNormalizer>,
  "drugs":  <DrugNormalizer>,
}
```

A **no-op normalizer** (`changed=false`, `normalized==input`) is always
available, so a service can disable correction for a field without changing the
pipeline.

## Strategy families

| Strategy | Fits | Idea |
|----------|------|------|
| No-op | both | Pass through the fragment unchanged. |
| Fuzzy match | closed sets | Use edit-distance / token-set ratio against the field's CSV or runtime closed set. |
| Phonetic | input closed sets | Use Soundex/Metaphone keys over CSV names for sound-alike typos. |
| TERMite-first | input closed sets | Use TERMite's preferred label when it corresponds to the field fragment. |
| LLM pool enrichment | both | Ask the model for equivalent pool items, then ground them against the closed set. |
| Hybrid | both | Use fuzzy/phonetic shortlist, LLM disambiguation, then membership validation. |

For open-set fields before fetch, correction is limited to no-op or conservative
surface cleanup. After fetch, the runtime closed set supplies the validation
anchor.

## Confidence handling

- **High confidence**: use `normalized`.
- **Medium confidence**: use `normalized` and surface `note` for auditability.
- **Low or ambiguous confidence**: keep candidates in the pool and let the
  closed-set translator resolve them by exact/fuzzy/LLM selection. If no
  candidate grounds, the filter is invalid rather than guessed.

For every bucket, a correction is only valid if it lands on a real member of the
field's input or runtime closed set. This reuses the final grounding check in
[stage-3-aggregation.md](stage-3-aggregation.md), so a bad correction cannot slip
through as an invented value.

## Normalizer policy

- Closed-set fields use the configured field normalizer before translation. A
  correction is accepted only when the corrected value grounds to the field's
  closed set.
- Enum and boolean fields normalize through their inline value list.
- Open-set fields are conservative before the API call because no value set
  exists yet. After datapoints are fetched, the runtime closed set provides the
  anchor for exact/fuzzy matching and any correction must select from those
  fetched values.
- Normalization is iterative only inside the closed-set translator's resolution
  loop: normalize, exact search, fuzzy search, LLM pool enrichment, then exact and
  fuzzy search again.
