# Maine Adapter — Spec-Driven Skills

This directory holds seven **slash-command skills** that turn human-facing
documentation into a specification, then into code, then audit and repair that
code — and commit the result. They form a single linear pipeline with one
independent auditor (`critique`) that loops back into it, a `git` skill
that applies the project's version-control rules to any change, and a `docs`
skill for editing the human-facing documentation directly. Conventions shared
across the skills (report numbering, the `EXECUTE_COMMAND` dispatch directive,
verdict vocabularies, the `## Sources` contract) are defined once in
[`CONVENTIONS.md`](CONVENTIONS.md).

**The human entry point is `docs/`, never `specs/`.** Product design lives in the
human-facing documentation under `docs/` (indexed by `docs/index.md`). Humans never
hand-edit anything in `specs/`. To change the product, you change `docs/`, then
ask the assistant to propagate: `/technical` ingests the changed docs, and the rest
of the chain carries the change down into the specs and the code. This keeps a
single source of truth and makes the whole skill set **product-agnostic** — point
it at a different repo's `docs/` and the same pipeline applies.

> **Typical user request:** *"I changed something under `docs/`. Use
> `.claude/skills/README.md` to apply it to the specs and the code."* The answer
> is the full run below, starting at `/technical`.

```
technical → implement → evaluation → fix
                                       ▲          │
                                       └──────────┘   (fix re-runs evaluation)

git ── applies specs/git.md to whatever changed (run after any step)
```

Each skill is invoked with `/<name>` and reads the artefact the previous skill
produced. The contract between them is **file paths under `specs/`** — that is
the only coupling; a skill never calls the next one except where noted
(`fix` re-triggers `evaluation`; `critique` dispatches to `technical`/`fix`).

---

## The skills at a glance

| # | Skill | Reads (input) | Writes (output) | Hands off to |
|---|-------|---------------|-----------------|--------------|
| 1 | `technical` | `./docs/` (the entire tree) + existing code/architecture/schema artefacts | `specs/product.md` **plus 8 `specs/` files**: `specs/technical*.md`, `constitution.md`, `requirements.md`, `plan.md`, `tasks.md`, `skeleton.md`, `evaluation.md`, `git.md` — **plus `.claude/settings.json`** (the permission allowlist) | `implement` |
| 2 | `implement` | `specs/technical*.md` (+ the other 6 planning files for context) | source code across the repo | `evaluation` |
| 3 | `evaluation` | `specs/evaluation.md` (the `EVAL-NNN` criteria) + the codebase | `specs/evaluation/report{NN}.md` | `fix` |
| 4 | `fix` | latest `specs/evaluation/report{NN}.md` + the specs it cites | code edits, then a fresh report | re-runs `evaluation` |
| 5 | `critique` | all of `specs/` + the codebase | edits to specs; questions to the user | `technical` / `fix` |
| 6 | `git` | `specs/git.md` + the working-tree diff | branch, commit, push/PR via `git`/`gh` | — (run after any step that changed files) |
| 7 | `docs` | `$ARGUMENTS` (a docs-change request); may read any file to document it accurately | **edits to `docs/` only** — touches nothing outside `docs/` | `technical` (to propagate documented intent into specs/code) |

> Standalone note: `docs` is **not** part of the forward chain. It is the
> human-facing way to change documentation directly: it edits `docs/**` and
> nothing else (no specs, no code, no config). After a `docs` change, run
> `/technical` to propagate the new intent down the chain.

> Standalone note: `issue` is **not** part of the forward chain either. It is the
> human-in-the-loop bug-repair loop: when you find a defect by testing the running
> system yourself, `/issue <what broke>` diagnoses and fixes it in the code, verifies
> it (Quality Gates + reproduction), then **asks you to confirm it is truly fixed**.
> Only once you confirm does it hand off to `/docs` (`EXECUTE_COMMAND: docs …`) so the
> documentation reflects the corrected behaviour. It writes code/tests/env-template,
> never runs git, and never auto-runs `/docs` without your confirmation.

> Path note: the skills declare short default artefact paths
> (`specs/product.md`, `specs/technical.md`, `specs/evaluation.md`) in each skill's
> `argument-hint` and body — **not** in front-matter (which holds only
> `name`/`description`/`argument-hint`/`user-invocable`/`disable-model-invocation`).
> `technical`'s sole human input is `./docs/`. This repo
> uses the short names, so the defaults match as-is. If a repo renames an artefact
> (e.g. `specs/product_specification.md`), pass the actual path as the argument; see
> [`CONVENTIONS.md`](CONVENTIONS.md) → Artefact path resolution.

---

## Dependency flowchart

```
                         ┌──────────────────────────────────────────────┐
                         │            HUMAN-FACING SOURCES               │
                         │        ./docs/  (the entire doc tree)         │
                         └───────────────────────┬──────────────────────┘
                                                 │ (technical reads all of ./docs/)
                                                 ▼
        ┌──────────────┐
        │  technical   │ writes specs/product.md + 8 specs files:
        └──────┬───────┘  product.md, technical.md, constitution.md,
        ▲      │            requirements.md, plan.md,
        │      │            tasks.md, skeleton.md,
        │      │            evaluation.md, git.md
        │      │            + .claude/settings.json
        │      │              (pre-authorise downstream)
        │      ▼
        │                                ┌──────────────┐  specs/technical.md
        │                                │  implement   │ ◀── (+ planning files)
        │                                └──────┬───────┘
        │                                       │ produces / updates code
        │                                       ▼
        │                                ┌──────────────┐  reads specs/evaluation.md
        │                                │  evaluation  │  + codebase
        │                                └──────┬───────┘
        │                                       │ writes report{NN}.md
        │                                       │ (PASS/PARTIAL/FAIL/N/A)
        │                                       ▼
        │                                ┌──────────────┐
        │        re-runs evaluation ◀────│     fix      │ fixes FAIL/PARTIAL
        │                                └──────────────┘
        │
        │   ┌──────────────────────────────────────────────────────────┐
        │   │                        critique                           │
        └───┤  independent auditor of ALL specs; dispatches resolution: │
            │   • missing info ........ ask the user                    │
            │   • product design ...... edit docs/, then /technical    │
            │   • architecture ........ /technical                     │
            │   • internal spec drift . edit the spec files directly   │
            │   • spec-vs-code ........ /fix                            │
            └──────────────────────────────────────────────────────────┘
```

**Reading the arrows**

- **Solid forward chain** (`technical → implement → evaluation → fix`)
  is the happy path: each consumes the previous step's `specs/` artefact.
- **`fix → evaluation`** is the only built-in loop: after repairing findings,
  `fix` re-triggers `evaluation` to confirm the fixes hold. Iterate until the
  report is clean.
- **`critique`** stands outside the chain. It reads everything, then *routes*
  each problem to the layer that **owns** it rather than patching the symptom —
  product-design changes go to `docs/` (then re-run `/technical`), `/technical` for
  architecture/criteria changes, `/fix` for code-vs-spec drift, direct edits for
  purely-internal spec inconsistencies, and direct questions to you for the rest.

---

## How to use them

### Full run, from scratch or after a `docs/` change
```text
/technical   docs/ changed, adapt the specs          # → specs/product.md + 8 planning files (incl. git.md)
/implement                                           # → code
/evaluation                                          # → specs/evaluation/report01.md
/fix                                                 # repairs findings, re-evaluates
/git                                                 # branch + commit + PR per specs/git.md
```

### Just keep the spec in sync with changed `docs/`
Run `/technical`. It ingests `docs/` and updates `specs/product.md` plus all eight
planning files (including `evaluation.md` and `git.md`) so the criteria stay aligned
with the new intent — exactly what the downstream audit checks against.

### Audit code against the spec without changing intent
Run `/evaluation` (produces a numbered gap report) then `/fix` (closes the
gaps and re-audits). Repeat until `report{NN}.md` shows no FAIL/PARTIAL.

### Sanity-check the specs themselves
Run `/critique` whenever the documents may have drifted apart (e.g. several
edits across files). It finds contradictions and missing information, then
either asks you or dispatches the right upstream skill to fix them.

---

## Key rules that hold the chain together

- **Lineage is explicit.** Every produced spec opens with a `## Sources`
  section naming exactly what it was derived from, so any artefact can be
  traced back to the human source in `docs/`.
- **Design changes start in `docs/`.** No skill edits product intent into
  `specs/` directly; the human edits `docs/`, then `/technical` propagates. This is
  what keeps the specs faithful to the source of truth and the skill set reusable
  across projects.
- **`technical` is the interactive entry point, and it clarifies *into `docs/`*.**
  When the docs are ambiguous or incomplete, `/technical` asks the human (with a
  recommendation), writes the agreed answer back into `docs/` **with permission**,
  then **restarts from the corrected `docs/` with a clean slate** — so the specs it
  finally emits have no fact that isn't in `docs/`.
- **`technical` front-loads permissions so the rest of the chain is unattended.**
  It writes `.claude/settings.json` pre-authorising every command the Quality
  Gates, git policy, and tasks will run, so `/implement` → `/evaluation` → `/fix`
  → `/git` never stop to ask the human to approve a tool call.
- **`technical` owns WHAT, `evaluation` owns HOW.** `specs/evaluation.md`
  lists the objectively-decidable `EVAL-NNN` criteria; the `evaluation` skill
  only *applies* them and never invents checks.
- **Run steps in order.** Each skill stops with an error if its input artefact
  is missing and tells you which earlier skill to run first.
- **Loop on `fix`/`evaluation`** until clean; reach for `critique` when the
  specs — not the code — are the thing in doubt.
