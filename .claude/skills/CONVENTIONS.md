# Pipeline Conventions

The single, authoritative definition of the conventions shared across the
spec-driven skills in this directory. Individual `SKILL.md` files keep their own
concise, point-of-use reminders, but **this file is the source of truth** — when
a convention is ambiguous in a skill, this file wins. Skills that depend on a
convention cite it as `../CONVENTIONS.md`.

---

## `EXECUTE_COMMAND` — skill-to-skill dispatch

Some skills chain to the next skill automatically. They do this by emitting, as
the **last line of their output**, a directive of the form:

```
EXECUTE_COMMAND: <skill-name> [arguments]
```

The harness intercepts this literal line and invokes `/<skill-name>` with the
given arguments, as if the user had typed it. It is **not** narrative — write it
verbatim, on its own line, with no surrounding prose, so it is recognised.

Current uses:

| Emitting skill | Directive | Effect |
|----------------|-----------|--------|
| `fix` | `EXECUTE_COMMAND: evaluation` | re-audits after repairs (the only built-in loop) |
| `critique` | `EXECUTE_COMMAND: fix specs/critique/report{NN}.md` | hands code-level findings to `/fix` |

Skills that hand off to a **human checkpoint** (e.g. `/technical` after a docs
clarification, `/evaluation` before `/fix`) use prose (`Next step: …`) instead,
deliberately, so the chain pauses for review.

---

## Report numbering

Skills that emit numbered reports (`evaluation` → `specs/evaluation/report{NN}.md`,
`critique` → `specs/critique/report{NN}.md`) number them identically:

- List existing files matching `report*.md` in the target directory.
- **Next number = highest existing index + 1** (not a count — so deleting an
  interim report never causes a collision/overwrite).
- **Zero-padded to 2 digits**, starting at `01` (the first report is `report01.md`).
- `mkdir -p <dir>` if the directory does not exist.

---

## Verdict & severity vocabularies

**Evaluation verdicts** (one per `EVAL-NNN` criterion, assigned by `/evaluation`):

| Verdict | Meaning |
|---------|---------|
| `PASS` | the named evidence is present and satisfies the criterion |
| `PARTIAL` | partially satisfied; what is missing is described |
| `FAIL` | the criterion is not met |
| `N/A` | the criterion's Out-of-Scope condition applies |
| `BLOCKED` | the **criterion itself** is defective (ambiguous/unverifiable/contradictory) — the fix is in `specs/evaluation.md`, not the code. This is an evaluation-side escape hatch, not a verdict the criteria schema declares. |

**Finding severities** (`evaluation` and `critique` both order fixes by these):
`BLOCKER` → `MAJOR` → `MINOR`. `critique` adds `QUESTION` for findings that
cannot be resolved without information from the user.

---

## The `## Sources` lineage contract

Every produced spec opens with a `## Sources` section, and it must come **first**.
It names exactly what the artefact was derived from (paths, and for folders the
concrete files read), so any artefact traces back to the human source in `docs/`.
A producer lists only true upstream sources; it never lists its own output or
`$ARGUMENTS` free-text as a source.

---

## Artefact path resolution

Each skill states a **default** artefact path (e.g. `specs/product.md`,
`specs/technical.md`, `specs/evaluation.md`). If the repository already uses a
different name for that artefact (e.g. `specs/product_specification.md`), read /
overwrite **that existing file** rather than creating a duplicate. Pass the actual
path as the skill's argument when the default does not match.

---

## Missing-input run order

Each skill stops with an error if its input artefact is missing and names the
earlier skill to run first. The canonical order:

| Skill | Required input | Run first |
|-------|----------------|-----------|
| `technical` | `./docs/` (the doc tree) | — (human edits `docs/`) |
| `implement` | `specs/technical.md` (+ planning files) | `/technical` |
| `evaluation` | `specs/evaluation.md` | `/technical` |
| `fix` | an evaluation or critique report | `/evaluation` (or `/critique`) |
| `critique` | `specs/` artefacts | — (audits whatever exists) |
| `git` | `specs/git.md` | `/technical` |
| `docs` | `./docs/` | — |
