---
name: "mdcritique"
description: "Audit the human-facing documentation under docs/ for internal consistency — contradictions, gaps, and unstated assumptions — then ask the user to fill gaps and resolve conflicts and reflect the resolved answers back into docs/. Reads and writes nothing outside docs/. Use to sanity-check the docs/ set when documents may have drifted apart."
argument-hint: "Optional scope: path(s) to specific docs/ files, or leave empty to audit all of docs/"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

If `$ARGUMENTS` names specific files, audit only those (they must be under `docs/`).
Otherwise audit everything under `docs/`.

## The one hard rule — `docs/**` only, read and write

This skill operates **entirely within `docs/`**. It is the consistency checker for
the human source of truth, and it never leaves that tree.

- **You may ONLY read files under `docs/`.** Do **not** read anything else outside
  `docs/`. The audit is about whether the documentation is internally coherent.
- **You may ONLY create, edit, or delete files under `docs/`.** Every write target's
  path MUST begin with `docs/`. Treat any write outside `docs/` as forbidden.
- If a coherent `docs/` would require knowing something only a human can
  supply, **ask the user** (Phase 3).

## Outline

You are an independent critic of the documentation. Your job is not to implement or
fix code — it is to find every place where the `docs/` files contradict each other,
make assumptions without stating them, or leave questions unanswered. You then drive
resolution **within `docs/`**: ask the user what you cannot resolve alone, and edit
the `docs/` files to reflect the confirmed answers.

```
                    ┌─────────────────┐
                    │   mdcritique    │  ← you are here (docs/ only)
                    └────────┬────────┘
                ┌────────────┴────────────┐
                ▼                          ▼
            ask user                 edit docs/ files
        (gaps & conflicts)       (reflect resolutions)
```

---

### Phase 1 — Collect all `docs/` artefacts

Read every in-scope file under `docs/` (start from `docs/index.md` and follow its
index table so you cover the whole tree). For each file note its role and what it
claims. Build a model of what the documentation, taken as a whole, says the system
is, does, and how it is operated — so you can spot where parts disagree.

Read nothing outside `docs/`.

---

### Phase 2 — Detect inconsistencies (within `docs/` only)

Check every axis below. For each problem found, record a **finding** with a severity
(`BLOCKER` / `MAJOR` / `MINOR` / `QUESTION`).

#### 2a. Internal contradictions
- Do two `docs/` files (or two passages in one file) state conflicting facts —
  different behaviours, names, paths, values, or constraints for the same thing?
- Does a later section contradict an earlier one (e.g. an overview that disagrees
  with the detailed page)?

#### 2b. Index & cross-reference integrity
- Does `docs/index.md` list every `docs/` file, and does every `docs/` file appear in
  the index with an accurate one-line description?
- Do in-`docs/` cross-references resolve to real files/sections, and is terminology
  (names, contract labels, command names, path templates) used consistently across
  files?

#### 2c. Gaps & missing information
- Does the documentation describe a capability or component but omit how it is used,
  configured, or operated?
- Is a term, contract, or path template referenced but never defined?
- Is there a described behaviour whose conditions or limits are never stated?

#### 2d. Unstated assumptions
- Does any document make a choice or claim that is not justified and not self-evident?
- Is a statement only true under a condition that the docs never state?

#### 2e. Open items that must not exist
- Does any `docs/` file contain an `## Open Questions` section, a TODO, a TBD, a
  "to be confirmed", a watermark ("reverse-engineered / generated from source"), or
  any placeholder? These are themselves findings — the docs must contain none. Each
  becomes a `QUESTION` to resolve with the user and then remove.

---

### Phase 3 — Ask the user to fill gaps and resolve conflicts

Present the findings to the user clearly and concisely, grouped by severity. For
every gap, contradiction, and `QUESTION` you cannot settle by reading `docs/` more
carefully, **ask the user** a focused question. For each:
- State exactly what is missing or which two statements conflict.
- Say which `docs/` file(s) will change once it is answered.
- Offer concrete options where possible; accept free-form answers otherwise.

Do not ask about things you can resolve by reading the docs carefully. Do not bundle
multiple distinct questions into one. The goal is to reach a single, consistent
answer for every conflict and gap.

**Running unattended.** This phase is interactive. When `/mdcritique` runs with no
human to answer — under `/mdflow`, in a dispatched subagent, or when told not to
stop — do **not** block: list the unresolved questions in your final report for a
human to answer later, and apply only the resolutions you can make safely from the
docs alone (e.g. fixing a broken cross-reference, aligning terminology). Leave
genuine design conflicts for the human rather than guessing.

---

### Phase 4 — Reflect resolutions into `docs/`

Once the user has answered, edit the `docs/` files to make them consistent:
- Apply each confirmed answer as settled fact in the right file(s), and update
  `docs/index.md` if the index is affected.
- Resolve every contradiction so the docs now agree; remove superseded text in place
  rather than annotating it as outdated.
- Delete any `## Open Questions` / TODO / TBD / placeholder / watermark you found,
  replacing it with the resolved fact (or removing the uncertain claim entirely if it
  cannot be settled even after asking).
- Keep the prose describing the **current state only** — no "previously/now",
  before/after, or migration framing.

Every write target's path must begin with `docs/`.

---

### Phase 5 — Verification

After all edits:
- Re-read every changed `docs/` file.
- Confirm each finding is closed (the contradiction is gone, the gap is filled, the
  placeholder is removed).
- Confirm `docs/index.md` still lists every file accurately and all in-`docs/`
  cross-references resolve.
- Confirm **no** write touched anything outside `docs/`; if one did, revert it.

---

### Report

Summarise (in your response to the user — not as a file outside `docs/`):
- Findings by severity (counts).
- Findings closed in this session (list by ID + which `docs/` file changed).
- Questions you asked and how the answers were reflected into `docs/`.
- Findings still open (list by ID + what the user must decide), if any.
