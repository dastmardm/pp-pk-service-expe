---
name: "technical"
description: "Ingest the human-facing docs under ./docs/, synthesise the product specification, then translate it into the full technical blueprint, all downstream planning artefacts, and the .claude/settings.json permission allowlist. The chain's entry point — use after a human edits ./docs/, before /implement."
argument-hint: "(no arguments — the sole product-design input is the ./docs/ directory)"
user-invocable: true
disable-model-invocation: false
---

## User Input

The **product-design input** to this skill is the **`./docs/` directory** at the
repository root — the human-facing documentation of the project.

- **Ignore `$ARGUMENTS` entirely.** Nothing passed on the command line is a source.
  There is no product-spec path to pass; the product-design source is always, and
  only, `./docs/`. (You still read existing code/architecture/schema artefacts as
  *context* to avoid contradicting prior decisions — but never as the product source.)
- **If `./docs/` does not exist (or is empty), raise an error and stop.** Report:
  "`./docs/` not found — the `technical` skill requires the human-facing
  documentation under `./docs/` as its sole product-design input." Then halt.

## Outline

You are the **`technical`** step — and the chain's **only entry point for human
input**:

```
technical → implement → evaluation → fix
```

Humans never edit `specs/` by hand. They change the human-facing documentation
under `./docs/`, then ask the assistant to propagate. This skill is the single step
that *ingests* `./docs/`; every downstream skill works only from the `specs/`
artefacts it produces.

This skill does **two jobs in one run**, in order:
1. **Synthesise the product specification** (`specs/product.md`) from `./docs/` —
   *what* the system does and *why*, no implementation detail.
2. **Translate that product spec into a complete technical blueprint** and every
   artefact an implementer needs before writing a single line of code.

You produce **nine `specs/` files** (`product.md` first, then the eight technical
artefacts) **plus** the harness permission allowlist (`.claude/settings.json`).

### The clarify-in-docs loop (this skill's defining behaviour)

Synthesising the product spec is **interactive**, and it is the **only** place
where ambiguity is resolved by talking to the human. The resolution is written back
into **`./docs/`, never into a spec**, because `./docs/` is the source of truth and
the specs must remain a faithful projection of it.

Whenever, while reading `./docs/`, you hit an **ambiguity, a gap, a contradiction,
or a decision the docs do not settle**:

1. **Surface it to the human** — state what is unclear or missing, why it matters,
   and give a **concrete recommendation** plus alternatives.
2. **Get a decision** (or your recommendation if they defer).
3. **Ask permission to record it in `./docs/`.** The answer is a product-design
   fact, so it belongs in the human documentation. Propose the exact `./docs/` file
   and edit. **Only edit `./docs/` with explicit permission. Never write the
   resolution into a spec.**
4. **Apply the approved edit to `./docs/`.**
5. **Restart the product synthesis from scratch.** Once `./docs/` has changed,
   discard everything from this pass and begin again against the now-current
   `./docs/`. Repeat until a full pass reads cleanly with no unresolved ambiguity
   requiring a docs change.

(If the human declines to record an answer in `./docs/`, do not bake it into a spec
either: leave it as an `## Open Questions` entry in `specs/product.md`. A spec must
never assert something `./docs/` does not.)

Only when a complete pass of `./docs/` needs no further change do you write
`specs/product.md` and proceed to the technical artefacts.

**You are also the chain's permission front-loader.** Everything downstream of you
— `/implement`, `/evaluation`, `/fix`, `/git` — must run **unattended**, never
pausing to ask the human to approve a tool call. That is only possible if *you*
work out, ahead of time, every command and file operation those skills will need
and pre-authorise them in `.claude/settings.json`. Deriving the toolchain is
already your job (you choose the stack, the quality gates, the git workflow), so
you are the only step with the knowledge to set the permissions correctly before
any of them runs. Treat a downstream permission prompt as a defect in *this* step.

The eighth file, `specs/evaluation.md`, is the bridge to the downstream `/evaluation` skill: it defines **WHAT** must be evaluated (the concrete, checkable criteria derived from every other artefact). `/evaluation` owns **HOW** to evaluate (the audit mechanics and report format). WHAT + HOW must compose into a clean, unambiguous evaluation pass — so every criterion you write in `specs/evaluation.md` must be objectively decidable as PASS / PARTIAL / FAIL / N/A by an auditor who has only the codebase and that file (or BLOCKED — the evaluation-side escape hatch — if a criterion is itself defective; see `../CONVENTIONS.md`).

### Output templates

The skeleton and per-file writing rules for **all ten outputs** live in
[reference/output-formats.md](reference/output-formats.md). The "File N" sections
below give each file's role and how to derive it; read the matching section of
`reference/output-formats.md` for the exact structure when you emit it. The
`## Sources`, report-numbering, verdict, and path-resolution conventions are
defined once in [../CONVENTIONS.md](../CONVENTIONS.md).

### Steps

1. **Verify and read `./docs/` in full.** If it is missing or empty, stop with the
   error above. Otherwise read every documentation file under `./docs/` (recurse
   into all subdirectories); follow cross-references *within* `./docs/`, but never
   out of it. Record every `./docs/` file read for the product spec's `## Sources`.

2. **Synthesise the product specification** (File 1, `specs/product.md`), running
   the **clarify-in-docs loop** above until a full pass of `./docs/` reads cleanly.
   Write it only once no further `./docs/` change is needed. By then every fact in
   it traces to `./docs/`. Then proceed — `specs/product.md` is the upstream
   source-of-truth for *what* and *why* that the technical artefacts derive from.

3. Read any existing technical artefacts in the repository (architecture docs, schema files, existing code) to avoid contradicting prior decisions. Discover these by exploring the repo — do not assume fixed paths. Record every such artefact you read in the technical spec's `## Sources` (path + whether file or folder; for folders, the concrete files read), so the lineage is fully traceable.

4. For each capability in the product spec, derive and document:
   - The architectural components that implement it
   - The data contracts it depends on (schemas, path templates, field requirements)
   - The infrastructure it requires
   - The configuration and secrets it consumes

---

### File 1 — `specs/product.md`

The product specification — *what* the system does and *why*, in business language,
**no implementation detail** — synthesised exclusively from `./docs/` via the
clarify-in-docs loop. (Default path `specs/product.md`; if the repo already uses a
different name for this artefact, e.g. `specs/product_specification.md`, overwrite
that file rather than creating a duplicate.) Its `## Sources` lists **only** files
under `./docs/`, and must come first.
→ template & writing rules: `reference/output-formats.md` → File 1.

### File 2 — `specs/technical.md`

The authoritative technical blueprint, derived from the File 1 product spec.
(Default path `specs/technical.md`; if the repo already uses a different name for
this artefact, e.g. `specs/technical_specification.md`, overwrite that file rather
than creating a duplicate. The other seven files use their literal names.) Every
technology choice must include a rationale. Precise enough that an engineer can
implement without follow-up questions. Its `## Sources` section is mandatory, must
come first, and records `specs/product.md` + `./docs/` + every technical artefact read.
→ template & Sources rules: `reference/output-formats.md` → File 2.

### File 3 — `specs/constitution.md`

The project's binding governance document. Answers one question: **what rules must
every contributor and every AI assistant follow, unconditionally?** Not a
description of how the system works — a set of non-negotiable constraints that
guard the architecture over time. If it already exists, update it (preserve
ratified principles; amend only where the new technical spec introduces changes).
→ template: `reference/output-formats.md` → File 3.

### File 4 — `specs/requirements.md`

The single authoritative list of what the system must and must not do, derived
from the product spec and the technical spec. Written so any stakeholder —
technical or not — knows exactly what "done" means.
→ template: `reference/output-formats.md` → File 4.

### File 5 — `specs/plan.md`

The implementation roadmap. Translates requirements into dependency-ordered phases
of work, records key decisions with rationale, and defines a success signal per
phase. Includes a Constitution Check confirming no principle is violated.
→ template: `reference/output-formats.md` → File 5.

### File 6 — `specs/tasks.md`

The full, ordered, actionable work list. Every task is self-contained: an
implementer picks it up and knows the exact file to create or modify and how to
verify it is done.
→ template & task-writing rules: `reference/output-formats.md` → File 6.

### File 7 — `specs/skeleton.md`

The complete map of every file and directory the implementation will create or
significantly modify, with a one-line purpose for each — the blueprint of the
codebase shape, written before any code. Its `## Conventions` section is where you
define the migration-naming and env-template conventions that `/implement` and
`/fix` consult.
→ template & skeleton-writing rules: `reference/output-formats.md` → File 7.

### File 8 — `specs/evaluation.md`

The **evaluation criteria** — the authoritative, machine-checkable list of *what*
the `/evaluation` skill must verify in the codebase. This is the WHAT half of the
WHAT+HOW contract: `/evaluation` reads this file and applies its own audit
mechanics (the HOW) against it. If a property is not written here as a criterion,
it will not be evaluated — so this file must cover every requirement, contract, and
constitution principle the implementation is expected to honour.

Derive criteria **from the other six artefacts**, not from imagination:
- one criterion per MUST requirement in `requirements.md` (and SHOULD where verifiable),
- one per data contract / path template in `technical.md`,
- one per non-negotiable principle in `constitution.md`,
- one per file the skeleton promises (`skeleton.md`) that must exist and serve its stated purpose.

→ template & criteria-writing rules: `reference/output-formats.md` → File 8.

### File 9 — `specs/git.md`

The project's **version-control contract** — the authoritative rules for how any
change (to specs, docs, code, infra, or schema) is committed and proposed. It is
the bridge to `/git`: `/git` reads this file and *applies* the rules with
`git`/`gh`. `specs/git.md` defines **WHAT the git workflow is**; `/git` owns
**executing it**. If a rule is not written here, `/git` will not enforce it.

You **decide** what these rules should be — derive them from what makes engineering
sense for *this* project (repository layout, the kinds of artefacts it holds, and
any conventions already visible: branch names, `CONTRIBUTING`, commit history,
`CODEOWNERS`, PR templates). The rules must be **deterministic and
machine-applicable** — `/git` must be able to look at a set of changed paths and
unambiguously decide the branch name, commit message, and whether to open a PR.
Cover at minimum: change-classification → branch; branch base & protection; commit
message convention (incl. the mandated `Co-Authored-By` trailer); push/PR policy;
pre-commit gates (mirror the constitution's Quality Gates); what must NOT be
committed; and idempotency/safety (branch exists / nothing to commit / PR already
open).
→ template & git-writing rules: `reference/output-formats.md` → File 9.

### File 10 — `.claude/settings.json` (permission allowlist)

The harness permission file that lets every downstream skill run **without a single
permission prompt** — the WHAT→HOW bridge for *execution rights*. Enumerate every
tool call the downstream skills will make and pre-approve it, so `/implement`,
`/evaluation`, `/fix`, and `/git` are never blocked waiting on the human.

Derive the allow list **from the artefacts you just wrote**, not from guesswork:
- From **`constitution.md` → Quality Gates** and **`git.md` → Pre-Commit Gates**:
  every checker/test/build command → `Bash(...)` allow rules.
- From **`git.md` → Push & PR Policy**: `git`/`gh` → `Bash(git:*)`, `Bash(gh:*)`.
- From **`tasks.md` / `skeleton.md`**: the directories implementation writes under,
  and any build/run/migration commands → matching `Bash(...)` and `Edit`/`Write` rules.
- From **`technical.md` → Configuration and Secrets**: writing the env template file
  → covered by `Edit`/`Write`.

→ template & allowlist rules: `reference/output-formats.md` → Harness permissions.

---

### Quality check (all ten outputs)

- `specs/product.md` exists, has `## Sources` first listing **only** `./docs/` files, contains no implementation detail, and asserts no product-design fact absent from `./docs/`
- Every requirement in `requirements.md` is addressed by at least one task in `tasks.md`
- Every task in `tasks.md` maps to at least one file in `skeleton.md`
- Every technology choice in `technical.md` appears in the Technology Stack table of `constitution.md`
- No orphaned decisions (every choice has a rationale)
- Data contracts are expressed as named templates, not prose
- Every constitution principle states: the rule, the rationale, what breaks if violated
- `specs/technical.md` has `## Sources` present, first, and recording `specs/product.md` + `./docs/` plus every artefact read
- `specs/evaluation.md` exists and its Coverage Map accounts for every MUST requirement, every data contract, every constitution principle, and every promised skeleton file — each covered by ≥1 EVAL-NNN, or listed in Out of Scope with a reason
- Every criterion in `specs/evaluation.md` is objectively decidable (states the evidence that makes it PASS) and cites its source artefact in the `Source ref` column
- `specs/git.md` exists; its branch-naming rules are path-keyed and deterministic, and its pre-commit gates and "never commit" rules are consistent with `constitution.md`
- `.claude/settings.json` exists and pre-authorises **every** command named in the Quality Gates, Pre-Commit Gates, git policy, and tasks — so no downstream skill (`/implement`, `/evaluation`, `/fix`, `/git`) will hit a permission prompt — while withholding destructive/secret-exposing actions and preserving any pre-existing settings

---

### Report

List all nine `specs/` files (`product.md` first, then the eight technical artefacts) plus `.claude/settings.json` written; any `./docs/` edits made during the clarify loop (file + what changed) and how many clean-restart passes the product synthesis took; any open questions captured; confirm `specs/evaluation.md` is complete (Coverage Map has no uncovered MUST items); confirm the permission allowlist covers every downstream command so the rest of the chain runs unattended; and next steps: `/implement` to build, and `/git` to commit changes per `specs/git.md`.
