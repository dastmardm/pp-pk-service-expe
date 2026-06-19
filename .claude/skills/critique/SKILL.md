---
name: "critique"
description: "Audit the specs against each other for contradictions, gaps, and unstated assumptions (does not touch code), then drive resolution. Use to sanity-check the spec set when documents may have drifted apart."
argument-hint: "Optional scope: path(s) to specific spec files, or leave empty to audit all specs/"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

If $ARGUMENTS names specific files, audit only those. Otherwise audit everything under `specs/`.

## Outline

You are an independent critic. Your job is not to implement or fix — it is to find every place where the specs contradict each other, make assumptions without stating them, leave questions unanswered, or diverge from the codebase. You then drive resolution: ask the user what you cannot resolve alone, and invoke other skills to propagate confirmed answers into the right documents.

```
                    ┌─────────────────┐
                    │    critique     │  ← you are here
                    └────────┬────────┘
           ┌─────────────────┼──────────────────┐
           ▼                 ▼                  ▼
     ask user            /fix          edit spec files
   (missing info)   (code conflicts)   (spec conflicts)
```

---

### Phase 1 — Collect all spec artefacts

Read every file in scope. For each file note its role in the chain:

| File | Role |
|------|------|
| `docs/…` (indexed by `docs/index.md`) | Human source of truth — product design lives here, not in `specs/` |
| `specs/product.md` (or repo's product-spec file) | Source of truth for *what* and *why* |
| `specs/technical.md` (or repo's technical-spec file) | Source of truth for *how* |
| `specs/constitution.md` | Non-negotiable constraints — overrides everything |
| `specs/requirements.md` | Numbered, testable statements of done |
| `specs/plan.md` | WBS decomposition + fork-join execution model, and key decisions |
| `specs/tasks.md` | Work Breakdown Structure — the hierarchical tree of typed nodes `/implement` executes |
| `specs/skeleton.md` | Agreed file map + authoritative file→owner (WBS node) map |
| `specs/evaluation.md` | The `EVAL-NNN` criteria (WHAT `/evaluation` checks) |
| `specs/git.md` | The version-control contract (WHAT `/git` applies) |
| `specs/evaluation/report*.md` | Prior audit findings |
| Codebase (if exists) | Ground truth of what is actually implemented |

Also read `specs/constitution.md` first — every finding is measured against it.

---

### Phase 2 — Detect inconsistencies

Check every axis below. For each problem found, record a **finding**.

#### 2a. Docs-to-spec fidelity (the human source of truth)
- Does `specs/product.md` claim a capability, constraint, or behaviour that the
  `docs/` source documents do not actually state? (Spec invented design — must be
  fixed in `docs/` first, then re-propagated, never patched into the spec.)
- Has a `docs/` document changed in a way the product spec has not yet absorbed?
  (Stale spec — re-run `/technical`.)
- Does `specs/product.md`'s `## Sources` list match what the product spec actually
  draws on (the `docs/…` files it was derived from — the whole tree, indexed by `docs/index.md`)?

#### 2b. Cross-spec contradictions
- Does a requirement in `requirements.md` conflict with a decision in `technical.md`?
- Does `plan.md` reference a component or subtree not described in `technical.md`?
- Does the `tasks.md` Work Breakdown Structure satisfy the invariants in
  `../CONVENTIONS.md` → Work Breakdown Structure? In particular: does every `skeleton.md`
  file have exactly one owning WBS node; are the nodes' `Owns` lists disjoint and do they
  cover the whole skeleton file set (no file owned twice, none unowned); does each node's
  `Owns` agree with `skeleton.md`'s authoritative `Owner (WBS node)` column; do all node
  references (`Parent`/`Children`/`After`/`Contributors`/cross-tree) resolve; and is the
  `After` ∪ cross-tree dependency graph acyclic?
- Does any summary/root node's `Review` cite an `EVAL-NNN` id? (It must not — the WHAT/HOW
  boundary keeps `evaluation.md` the sole owner of criteria; `tasks.md` never cites it.)
- Does `skeleton.md` describe a file whose purpose contradicts the architecture in `technical.md`?
- Does `product.md` list a capability with no corresponding requirement in `requirements.md`?

#### 2c. Constitution violations
- Does any spec permit a technology, pattern, or practice the constitution prohibits?
- Does any spec omit a requirement the constitution mandates (e.g. observability, idempotency)?

#### 2d. Missing information
- Does any requirement lack an acceptance criterion?
- Does any task lack a concrete file path or done-when condition?
- Does any technology decision lack a rationale?
- Does any architecture component lack a defined interface?
- Does any data contract use prose where a named template is required?

#### 2e. Unstated assumptions
- Does any spec make a choice that is not justified and not self-evident?
- Is there a statement that is only true under a condition that is never stated?

#### 2f. Spec-to-code divergence (if codebase exists)
- Does the codebase implement something that contradicts a spec?
- Does the codebase use a pattern the constitution prohibits?
- Does a spec describe behaviour that the code does not implement?

---

### Phase 3 — Write `specs/critique/report{NN}.md`

Determine the next report number (see `../CONVENTIONS.md` → Report numbering):
list files matching `specs/critique/report*.md`; next number = highest existing
index + 1, zero-padded to 2 digits (so the first report is `report01.md`);
`mkdir -p specs/critique` if needed.

Write the report using the structure in [report-template.md](report-template.md)
— `BLOCKER`/`MAJOR`/`MINOR`/`QUESTION` findings (with a `Type` per finding), a
Summary count table, and a `## Recommended Resolution Order`. The code-level subset
(`Type: code divergence` / `constitution violation`) is the part `/fix` consumes
when this report is handed to it in Phase 5. Type every code-touching finding
exactly `code divergence` or `constitution violation` — `/fix` keys on those
labels, so a code finding Typed otherwise (e.g. `contradiction`) is silently skipped.

---

### Phase 4 — Ask the user about QUESTION findings

Present every QUESTION finding to the user clearly and concisely. Wait for answers before proceeding to Phase 5.

For each question:
- State exactly what information is missing
- Explain which spec(s) need updating once answered
- Offer concrete options where possible
- Accept free-form answers when options are too constraining

Do not ask about things you can resolve by reading the specs carefully. Do not bundle multiple distinct questions into one.

---

### Phase 5 — Drive resolution

Once the user has answered all QUESTIONs, resolve findings as follows:

Route every finding to the **highest** applicable level — never patch a symptom
at a lower level than its cause. The chain's source of truth flows
`docs/ → technical → implement`, so a fix must be applied at the layer
that *owns* the fact, then propagated downward by re-running the skills below it.

**For findings that are genuine product-design / intent changes** (a capability,
constraint, or behaviour the human documentation does not actually say, or now
says differently):
- Do **not** edit `specs/product.md` (or any downstream spec) directly — that
  would let the specs drift from the human source of truth.
- State exactly which `docs/` file (and `docs/index.md`, if the index is affected) the human
  must change, and what to change. Product design lives in `docs/`; the human
  edits it, then re-runs `/technical` to propagate.
- Once `docs/` is corrected, the propagation is: `/technical` →
  `/implement` → `/evaluation` → `/fix`.

**For findings where architecture/technical decisions are invalidated** (the
`docs/` intent is fine, but the technical spec or its planning artefacts derive it
wrongly): re-run `/technical`, then continue downstream.

**For findings that are purely internal spec inconsistencies** (one `specs/`
artefact contradicts another, a missing cross-reference, an unstated assumption —
with no change to product intent or architecture): edit the affected spec files
directly and note which finding each edit closes. If you are unsure whether a
finding is "internal" or a real design change, treat it as a design change and
route it to `docs/` — do not guess on the user's behalf.

**For findings where the code conflicts with the specs** (spec-to-code divergence,
constitution violations in code) — hand them to `/fix` by emitting the dispatch
directive as the last line of your output (see `../CONVENTIONS.md` → EXECUTE_COMMAND):
  ```
  EXECUTE_COMMAND: fix specs/critique/report{NN}.md
  ```
  `/fix` consumes this report's **code-level** findings only — those with
  `Type: code divergence` or `constitution violation`, ordered by the report's
  `## Recommended Resolution Order` — repairs the codebase, and triggers a new
  `/evaluation` run. It deliberately ignores `QUESTION` and spec-only findings, so
  only the code-conflict subset is acted on here; route the rest via the branches above.

---

### Phase 6 — Verification

After all resolutions:
- Re-read every edited spec file
- Confirm each finding is closed (no longer present)
- If any finding is still open, explain why and what the user must decide

---

### Report

Summarise:
- Findings by severity (counts)
- Findings closed in this session (list by ID)
- Findings handed to `/fix` (list by ID)
- Findings routed to `docs/` for a product-design change (list by ID + which doc)
- Findings requiring upstream skill re-run (list by ID + which skill)
- Findings still open (list by ID + blocker reason)
