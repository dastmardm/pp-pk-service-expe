# Stage 2 — Per-field translation

**Input:** one single-field NL subquery from Stage 1.
**Output:** one machine subquery — a filter `(operator, field, value)` (possibly
a small boolean group when one field carries multiple concepts).

This stage runs **independently per subquery** (naturally parallel), and it is
where the closed-vs-open distinction does its work.

## The branch

```
subquery for field F
        │
        ├─ F is CLOSED-VOCAB ─────────────────────────────────────────────┐
        │     1. tool-call: lookup F's CSV with the nl_fragment            │
        │        (exact → fuzzy → TERMite-preferred-label)                 │
        │     2. if the user named a class/rollup, expand via              │
        │        parent_id/parent_name to the member set                   │
        │     3. choose operator: MATCH (single/list), or NOT, or RANGE    │
        │        (documentYear), honouring the boolean hint                │
        │     4. emit MATCH F = [preferred labels]                         │
        │                                                                  │
        └─ F is OPEN ─────────────────────────────────────────────────────┤
              1. LLM produces the value directly                           │
              2. text → REGEX pattern (with synonym expansion)             │
                 numeric → RANGE (after unit normalization)                │
                 short qualifier → MATCH                                   │
              3. emit the filter                                           │
                                                                           ▼
                                                              machine subquery
```

## Closed-vocabulary fields

The value **must** come from the CSV. The generic algorithm:

0. **Normalize (misspellings).** Run the pluggable normalizer for this field
   over `nl_fragment` first (see
   [misspelling-strategy.md](misspelling-strategy.md)). For closed-vocab fields
   this bridges typos to a real taxonomy entry before lookup. Defaults to a
   no-op until a strategy is chosen.
1. **Lookup.** Resolve the (normalized) `nl_fragment` against the field's CSV
   ([drugs.csv](../../inputs/drugs.csv), [species.csv](../../inputs/species.csv),
   …) in priority order:
   1. TERMite preferred label, if the subquery came from an annotation;
   2. exact (case-insensitive) name match;
   3. fuzzy / synonym / wildcard match (with `count` as a tie-breaker where the
      CSV has it).
2. **Expand (hierarchy).** If the fragment denotes a class or rollup rather than a
   leaf, walk `parent_id`/`parent_name`:
   - drug class → member drugs (Q8 "kinase inhibitors", Q23 "monoclonal
     antibodies", Q24 "ADC");
   - species class → member species (Q23 "Monkeys" → all monkey species);
   - effect category → preferred terms (Q1-driven MedDRA rollups);
   - "non-clinical / preclinical species" → the curated preclinical set (Q7/Q16).
   Expansion direction (up vs down) is driven by the user's intent: a *class*
   name expands **down** to members; a specific term used as a *filter* may stay
   as-is or roll **up** per service rules.
3. **Operator.** Default `MATCH` with a value array of the resolved preferred
   labels. Use `NOT` for exclusions, `RANGE`/`DATE_RANGE` for `documentYear`
   thresholds. Honour the Stage-1 boolean hint within the field.
4. **Drug fuzzy nuance.** Per the legacy prompts, drug filters typically use
   `drugsFuzzy` with a conservative trailing wildcard on the base name
   (`Sunitinib*`, `Imatinib*`) so salts/forms are captured, while `drugs` is for
   strict exact matching. The CSV's `parent_name` gives the class label for
   class queries.

Output example (closed):

```json
{ "MATCH": { "field": "species", "value": ["African green monkey", "Cynomolgus monkey", "Rhesus monkey", "..."] } }
```

## Open fields

The LLM decides, because there is nothing to look up. The same pluggable
normalizer step applies first (see
[misspelling-strategy.md](misspelling-strategy.md)), but for open fields it must
be conservative — there is no vocabulary to validate a correction against, so we
risk "fixing" a deliberate term. Guidance carried over from the legacy prompts,
now scoped to just this field:

- **Free text → `REGEX`, with synonym expansion.** `studyGroup` for "hepatic
  impairment" → `.*(cirrhosis|liver disease|hepatic insufficiency|Child-Pugh
  B|Child-Pugh C|…).*`.
- **Numeric → `RANGE`, after unit normalization.** "clearance over 100 L/h" →
  convert to a supported unit, then bound `valueMaxNormalized` with `min`
  (PK threshold rules).
- **Short qualifier → `MATCH`.** `parameterComment = "Maternal toxicity"`.
- **`ages`** → substring/`REGEX` (gold set: "substring search adult").

Output example (open):

```json
{ "REGEX": { "field": "studyGroup", "pattern": ".*(cirrhosis|hepatic impairment|Child-Pugh B|Child-Pugh C).*" } }
```

## Per-field contract

Whatever the implementation, each field translator should expose a uniform
contract so Stage 3 and the evaluator can treat them uniformly:

```
translate(nl_fragment, context) -> {
  field:    str,
  operator: "MATCH" | "REGEX" | "RANGE" | "NOT" | "DATE_RANGE" | "EMPTY",
  value:    str | [str] | {min,max},
  boolean_group?: { id, op: "AND" | "OR" },   # for multi-concept fields
  grounding?: { matched_ids: [...], expanded_from: "class"|"term"|null, confidence: 0..1 },
  notes?:   str
}
```

The `grounding` block is what makes the system auditable: for every closed-vocab
value we can show *which* CSV rows it came from and whether it was expanded.

## Failure handling

- **No CSV match** for a closed-vocab fragment → do not fall back to a hallucinated
  value. Either (a) return a low-confidence fuzzy candidate flagged for review, or
  (b) surface "term not found in vocabulary" so the orchestrator can ask the user
  or drop the constraint deliberately. This directly addresses the legacy
  "invented value" failures.
- **Ambiguous field** (class vs target) → attempt both lookups; keep the higher-
  confidence one, record the alternative.
