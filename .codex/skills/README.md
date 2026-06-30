# Maine Adapter — Spec-Driven Skills

This directory holds **slash-command skills** that turn human-facing
documentation into a specification, then into code, then audit that code — and
commit the result. They form a single linear pipeline, with a `docs/` consistency
auditor (`mdcritique`), a `mdgit` skill that applies the project's version-control
rules to any change, and `mddocs`/`mdrevdocs`/`mdresearch` skills that author the
human-facing documentation. Conventions shared across the skills (the docs-first
invariant, report numbering, the `EXECUTE_COMMAND` dispatch directive, verdict
vocabularies, the `## Sources` contract) are defined once in
[`CONVENTIONS.md`](CONVENTIONS.md).

**The human entry point is `docs/`, never `specs/` or code.** Product design lives in
the human-facing documentation under `docs/` (indexed by `docs/index.md`). Humans
never hand-edit anything in `specs/`, and **no change to project scope, behaviour,
features, or quality is ever made directly in source code.** To change the product —
including to fix a behavioural bug or add a new feature — you change `docs/`, then ask
the assistant to propagate: `/mdtechnical` ingests the changed docs, and the rest of
the chain carries the change down into the specs and the code. Source code and `specs/`
are **projections** of `docs/`, regenerated from it, never the origin of a change. This
keeps a single source of truth and makes the whole skill set **product-agnostic** —
point it at a different repo's `docs/` and the same pipeline applies. The full rule is
[`CONVENTIONS.md`](CONVENTIONS.md) → Docs-first.

> **Typical user request:** *"I changed something under `docs/`. Use
> `.claude/skills/README.md` to apply it to the specs and the code."* The answer
> is the full run below, starting at `/mdtechnical`.

```
technical → implement → evaluation
                            │
                            └─▶ gaps remediated by re-running the chain:
                                /mdimplement (conformance), or
                                edit docs/ → /mdtechnical (intent change)

git ── applies specs/git.md to whatever changed (run after any step)
```

Each skill is invoked with `/<name>` and reads the artefact the previous skill
produced. The contract between them is **file paths under `specs/`** — that is
the only coupling; a skill never calls the next one (every hand-off is a human
checkpoint, surfaced as a `Next step: …` line). `/mdevaluation` only *reports* gaps;
it never patches code — remediation flows forward from `docs/`.

---

## The skills at a glance

| # | Skill | Reads (input) | Writes (output) | Hands off to |
|---|-------|---------------|-----------------|--------------|
| 1 | `mdtechnical` | `./docs/` (the entire tree) + existing code/architecture/schema artefacts | `specs/product.md` **plus 8 `specs/` files**: `specs/technical*.md`, `constitution.md`, `requirements.md`, `plan.md`, `tasks.md`, `skeleton.md`, `evaluation.md`, `git.md` — **plus `.claude/settings.json`** (the permission allowlist) | `mdimplement` |
| 2 | `mdimplement` | `specs/technical*.md` (+ the other 6 planning files for context) | source code across the repo | `mdevaluation` |
| 3 | `mdevaluation` | `specs/evaluation.md` (the `EVAL-NNN` criteria) + the codebase | `specs/evaluation/report{NN}.md` (a gap report — no code edits) | — (remediate by re-running `/mdimplement`, or `docs/` → `/mdtechnical`) |
| 4 | `mdcritique` | all of `docs/` | questions to the user; edits to `docs/` only | — (re-run `/mdtechnical` to propagate the corrected docs) |
| 5 | `mdgit` | `specs/git.md` + the working-tree diff | branch, commit, push/PR via `git`/`gh` | — (run after any step that changed files) |
| 6 | `mddocs` | `$ARGUMENTS` (a docs-change request); may read any file to document it accurately | **edits to `docs/` only** — touches nothing outside `docs/` | `mdtechnical` (to propagate documented intent into specs/code) |
| 7 | `mdrevdocs` | the **source code** (+ optional scope hint in `$ARGUMENTS`) | **creates `docs/` only** — `index.md` + per-topic files, reverse-engineered from code | `mddocs` / `mdtechnical` (human ratifies, then the forward chain projects) |
| 8 | `mdresearch` | data source(s) + supplementary materials + a question | **writes `docs/research/**` only** — a derived-evidence insight artefact | `mdtechnical` (picks it up as a `docs/` source) |

> Standalone note: `mddocs` is **not** part of the forward chain. It is the
> human-facing way to change documentation directly: it edits `docs/**` and
> nothing else (no specs, no code, no config). After a `mddocs` change, run
> `/mdtechnical` to propagate the new intent down the chain.

> Standalone note: `mdrevdocs` runs the chain **in reverse**. The forward chain
> goes `docs/ → /mdtechnical → specs/ → /mdimplement → code`; `mdrevdocs` reads the
> **existing code** as the source of truth and reverse-engineers the human-facing
> `docs/` tree from it — *creating* `docs/`, its `index.md`, and the per-topic
> files. Use it to bootstrap `docs/` for a repo that has code but no docs, or to
> refresh `docs/` so it again reflects what the code does. Like `mddocs` it writes
> `docs/**` and nothing else; what it produces is *derived from code, awaiting human
> ratification*. After a human reviews/refines it (optionally via `/mddocs`), the
> forward chain can project it back down.

> Standalone note: `mdresearch` is a **leaf** input skill. It reads data source(s)
> read-only, reasons about them against supplementary materials, and writes a
> derived-evidence insight artefact under `docs/research/**` (and nothing else). It
> does not chain onward; its write-up simply becomes another `docs/` source the next
> `/mdtechnical` run reads — so even data-derived insight enters the system through
> `docs/`, never through code.

> Path note: the skills declare short default artefact paths
> (`specs/product.md`, `specs/technical.md`, `specs/evaluation.md`) in each skill's
> `argument-hint` and body — **not** in front-matter (which holds only
> `name`/`description`/`argument-hint`/`user-invocable`/`disable-model-invocation`).
> `mdtechnical`'s sole human input is `./docs/`. This repo
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
        │                                       │ (PASS/PARTIAL/FAIL/N/A) — no code edits
        │                                       │
        │   gap remediation (no direct fix step):│
        └───────────────────────────────────────┤  • code ≠ intent ... re-run /mdimplement
            edit docs/ → re-run /mdtechnical ◀───┘  • intent wrong/missing ... edit docs/

        ┌──────────────────────────────────────────────────────────┐
        │                        critique                           │
        │  consistency auditor of docs/ ONLY (reads/writes docs/):  │
        │   • contradictions / gaps .. ask the user, fix in docs/   │
        │   • then propagate .......... re-run /mdtechnical          │
        └──────────────────────────────────────────────────────────┘
```

**Reading the arrows**

- **Solid forward chain** (`technical → implement → evaluation`)
  is the happy path: each consumes the previous step's `specs/` artefact.
- **Gap remediation is the only loop**, and it flows **forward**, not back:
  `/mdevaluation` reports gaps but never edits code. A `FAIL`/`PARTIAL` where the code
  just fails to satisfy already-documented intent is closed by re-running
  `/mdimplement`; a gap that shows the **intent** is wrong or missing is closed by
  editing `docs/` and re-running `/mdtechnical`. Iterate until the report is clean.
- **`mdcritique`** stands outside the chain and stays entirely within `docs/`. It
  audits the documentation for internal contradictions and gaps, asks you to resolve
  what it cannot settle, and reflects the answers back into `docs/`. To carry those
  corrections into the specs and code, re-run `/mdtechnical`.

---

## How to use them

### Full run, from scratch or after a `docs/` change
```text
/mdtechnical   docs/ changed, adapt the specs          # → specs/product.md + 8 planning files (incl. git.md)
/mdimplement                                           # → code
/mdevaluation                                          # → specs/evaluation/report01.md (gap report)
/mdgit                                                 # branch + commit + PR per specs/git.md
```
To add a feature or fix a behavioural bug, **edit `docs/` first**, then run the same
sequence — the change is implemented by re-projecting `docs/`, never patched into code.

### Just keep the spec in sync with changed `docs/`
Run `/mdtechnical`. It ingests `docs/` and updates `specs/product.md` plus all eight
planning files (including `evaluation.md` and `git.md`) so the criteria stay aligned
with the new intent — exactly what the downstream audit checks against.

### Audit code against the spec, then remediate
Run `/mdevaluation` to produce a numbered gap report. `/mdevaluation` never edits code:
close `FAIL`/`PARTIAL` findings by re-running `/mdimplement` (when the code merely fails
to satisfy already-documented intent) or by editing `docs/` and re-running
`/mdtechnical` (when a finding shows the intent itself is wrong or missing). Re-run
`/mdevaluation` until `report{NN}.md` shows no FAIL/PARTIAL.

### Sanity-check the documentation itself
Run `/mdcritique` whenever the `docs/` files may have drifted apart (e.g. several
edits across files). It finds contradictions and gaps **within `docs/`**, asks you to
resolve them, and reflects the answers back into `docs/`; re-run `/mdtechnical` to
propagate. It reads and writes nothing outside `docs/`.

---

## Key rules that hold the chain together

- **Lineage is explicit.** Every produced spec opens with a `## Sources`
  section naming exactly what it was derived from, so any artefact can be
  traced back to the human source in `docs/`.
- **Every change starts in `docs/`.** No skill originates a change to project scope,
  behaviour, features, or quality anywhere but `docs/` — not in `specs/`, not in source
  code. The human edits `docs/`, then `/mdtechnical` propagates. Source code and
  `specs/` are projections of `docs/`, regenerated from it. This keeps the specs
  faithful to the source of truth and the skill set reusable across projects. (Full
  rule: [`CONVENTIONS.md`](CONVENTIONS.md) → Docs-first.)
- **There is no direct code-repair step.** `/mdevaluation` only reports gaps;
  remediation flows forward — re-run `/mdimplement` for conformance, or edit `docs/`
  and re-run `/mdtechnical` for an intent change. Nothing patches code out of band.
- **`mdtechnical` is the interactive entry point, and it clarifies *into `docs/`*.**
  When the docs are ambiguous or incomplete, `/mdtechnical` asks the human (with a
  recommendation), writes the agreed answer back into `docs/` **with permission**,
  then **restarts from the corrected `docs/` with a clean slate** — so the specs it
  finally emits have no fact that isn't in `docs/`.
- **`mdtechnical` front-loads permissions so the rest of the chain is unattended.**
  It writes `.claude/settings.json` pre-authorising every command the Quality
  Gates, git policy, and tasks will run, so `/mdimplement` → `/mdevaluation`
  → `/mdgit` never stop to ask the human to approve a tool call.
- **`mdtechnical` owns WHAT, `mdevaluation` owns HOW.** `specs/evaluation.md`
  lists the objectively-decidable `EVAL-NNN` criteria; the `mdevaluation` skill
  only *applies* them and never invents checks.
- **Run steps in order.** Each skill stops with an error if its input artefact
  is missing and tells you which earlier skill to run first.
- **Loop `mdimplement` → `mdevaluation`** (re-implementing to close gaps) until the
  report is clean; reach for `mdcritique` when the `docs/` — the source of truth —
  are the thing in doubt.
