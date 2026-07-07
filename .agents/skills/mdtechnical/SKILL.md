---
name: "mdtechnical"
description: "Ingest the human-facing docs under ./docs/, synthesise the product specification, then translate it into the full technical blueprint, all downstream planning artefacts, and the .Codex/settings.json permission allowlist. Finishes with a fresh-memory self-critique of specs/ that reflects any gap back into docs/ and, if so, requires restarting from scratch. The chain's entry point — use after a human edits ./docs/, before /mdimplement."
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
  "`./docs/` not found — the `mdtechnical` skill requires the human-facing
  documentation under `./docs/` as its sole product-design input." Then halt.

## Outline

You are the **`mdtechnical`** step — and the chain's **only entry point for human
input**:

```
technical → implement → evaluation
```

Humans never edit `specs/` by hand. They change the human-facing documentation
under `./docs/`, then ask the assistant to propagate. This skill is the single step
that *ingests* `./docs/`; every downstream skill works only from the `specs/`
artefacts it produces.

This skill does **three jobs in one run**, in order:
1. **Synthesise the product specification** (`specs/product.md`) from `./docs/` —
   *what* the system does and *why*, no implementation detail.
2. **Translate that product spec into a complete technical blueprint** and every
   artefact an implementer needs before writing a single line of code.
3. **Self-critique the generated `specs/` with a clear memory** — independently audit
   the `specs/` tree for gaps and missing parts; reflect any found gap **into `./docs/`
   only**, then **stop and require a from-scratch restart** (see *Self-critique pass*).

You produce **nine `specs/` files** (`product.md` first, then the eight technical
artefacts) **plus** the harness permission allowlist (`.Codex/settings.json`), and
finish with the self-critique pass.

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

**Running unattended.** This clarify loop is interactive. When `/mdtechnical` is run
without a human to answer — under `/mdflow`, in a dispatched subagent, or when told not to
stop — treat every ambiguity as if the human were unavailable: do **not** block, record
it as an `## Open Questions` entry, proceed from what `./docs/` unambiguously states, and
list all deferrals in the final report (`../CONVENTIONS.md` → Interactive vs autonomous
skills).

Only when a complete pass of `./docs/` needs no further change do you write
`specs/product.md` and proceed to the technical artefacts.

**You are also the chain's permission front-loader.** Everything downstream of you
— `/mdimplement`, `/mdevaluation`, `/mdgit` — must run **unattended**, never
pausing to ask the human to approve a tool call. (`/mdimplement` additionally dispatches
one subagent per WBS node to build the tree in parallel; those subagents **inherit this
allowlist**, so it must cover every command they run — including the package-manager /
resolver commands a summary node runs for convergent files.) That is only possible if *you*
work out, ahead of time, every command and file operation those skills will need
and pre-authorise them in `.Codex/settings.json`. Deriving the toolchain is
already your job (you choose the stack, the quality gates, the git workflow), so
you are the only step with the knowledge to set the permissions correctly before
any of them runs. Treat a downstream permission prompt as a defect in *this* step.

The eighth file, `specs/evaluation.md`, is the bridge to the downstream `/mdevaluation` skill: it defines **WHAT** must be evaluated (the concrete, checkable criteria derived from every other artefact). `/mdevaluation` owns **HOW** to evaluate (the audit mechanics and report format). WHAT + HOW must compose into a clean, unambiguous evaluation pass — so every criterion you write in `specs/evaluation.md` must be objectively decidable as PASS / PARTIAL / FAIL / N/A by an auditor who has only the codebase and that file (or BLOCKED — the evaluation-side escape hatch — if a criterion is itself defective; see `../CONVENTIONS.md`).

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
   Treat `./docs/research/**` as **derived evidence**, not ratified intent
   (`../CONVENTIONS.md` → `docs/` authority): it informs the product spec but does not
   by itself settle a product decision, and where it conflicts with human-authored docs
   the human-authored intent wins — record the conflict as an `## Open Questions` entry
   rather than resolving it in the derived file's favour.

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

The implementation roadmap. Presents the **Work Breakdown Structure** decomposition
(the top levels of the tree and the rationale for the cut) and the **fork-join
execution model** `/mdimplement` will run, records key decisions with rationale, and
includes a Constitution Check confirming no principle is violated.
→ template: `reference/output-formats.md` → File 5; model: `../CONVENTIONS.md` → Work
Breakdown Structure.

### File 6 — `specs/tasks.md`

The project's **Work Breakdown Structure** — the hierarchical tree of nodes
`/mdimplement` executes. Leaf nodes are atomic, file-disjoint units (the unit of parallel
execution); summary nodes block on their children, then aggregate, review, and report
upward; the root resolves last, bottom-up. Every node is self-contained: its kind, owned
files, dependencies, and a verifiable done-when are explicit on the node.
→ template & node grammar: `reference/output-formats.md` → File 6; model (node kinds,
ownership invariant, fork-join semantics, quality invariants): `../CONVENTIONS.md` → Work
Breakdown Structure.

### File 7 — `specs/skeleton.md`

The complete map of every file and directory the implementation will create or
significantly modify, with a one-line purpose for each — the blueprint of the codebase
shape, written before any code. It is also the **authoritative file→owner map** for the
WBS: its File Inventory carries an `Owner (WBS node)` column that each node's `Owns` list
in `tasks.md` must agree with (one owner per file, every file owned). Its `## Conventions`
section is where you define the migration-naming and env-template conventions that
`/mdimplement` consults.
→ template & skeleton-writing rules: `reference/output-formats.md` → File 7; ownership
invariant: `../CONVENTIONS.md` → Work Breakdown Structure.

### File 8 — `specs/evaluation.md`

The **evaluation criteria** — the authoritative, machine-checkable list of *what*
the `/mdevaluation` skill must verify in the codebase. This is the WHAT half of the
WHAT+HOW contract: `/mdevaluation` reads this file and applies its own audit
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
the bridge to `/mdgit`: `/mdgit` reads this file and *applies* the rules with
`git`/`gh`. `specs/git.md` defines **WHAT the git workflow is**; `/mdgit` owns
**executing it**. If a rule is not written here, `/mdgit` will not enforce it.

You **decide** what these rules should be — derive them from what makes engineering
sense for *this* project (repository layout, the kinds of artefacts it holds, and
any conventions already visible: branch names, `CONTRIBUTING`, commit history,
`CODEOWNERS`, PR templates). The rules must be **deterministic and
machine-applicable** — `/mdgit` must be able to look at a set of changed paths and
unambiguously decide the branch name, commit message, and whether to open a PR.
Cover at minimum: change-classification → branch; branch base & protection; commit
message convention (incl. the mandated `Co-Authored-By` trailer); push/PR policy;
pre-commit gates (mirror the constitution's Quality Gates); what must NOT be
committed; and idempotency/safety (branch exists / nothing to commit / PR already
open).
→ template & git-writing rules: `reference/output-formats.md` → File 9.

### File 10 — `.Codex/settings.json` (permission allowlist)

The harness permission file that lets every downstream skill run **without a single
permission prompt** — the WHAT→HOW bridge for *execution rights*. Enumerate every
tool call the downstream skills will make and pre-approve it, so `/mdimplement`,
`/mdevaluation` and `/mdgit` are never blocked waiting on the human.

Derive the allow list **from the artefacts you just wrote**, not from guesswork:
- From **`constitution.md` → Quality Gates** and **`git.md` → Pre-Commit Gates**:
  every checker/test/build command → `Bash(...)` allow rules.
- From **`git.md` → Push & PR Policy**: `git`/`gh` → `Bash(git:*)`, `Bash(gh:*)`.
- From **`tasks.md` (the WBS) / `skeleton.md`**: the directories implementation writes
  under, and any build/run/migration commands → matching `Bash(...)` and `Edit`/`Write`
  rules. Include the **package-manager / resolver commands summary nodes run for
  convergent manifest/lockfile files** (`../CONVENTIONS.md` → Convergent files). The
  subagents `/mdimplement` dispatches inherit this allowlist; add **no** rules for
  orchestration tool names (`Agent`, `Workflow`) and **none** for worktree isolation.
- From **`technical.md` → Configuration and Secrets**: writing the env template file
  → covered by `Edit`/`Write`.

→ template & allowlist rules: `reference/output-formats.md` → Harness permissions.

---

### Quality check (all ten outputs)

- `specs/product.md` exists, has `## Sources` first listing **only** `./docs/` files, contains no implementation detail, and asserts no product-design fact absent from `./docs/`
- Every requirement in `requirements.md` is addressed by at least one WBS leaf in `tasks.md` (each leaf names ≥1 `REQ`, or is tagged `Structural:`)
- The WBS in `tasks.md` satisfies every invariant in `../CONVENTIONS.md` → Work Breakdown Structure: exactly one root; every non-root has one parent; all node references resolve; declared `Type` agrees with structure; `Owns` lists are pairwise disjoint and their union equals exactly the `skeleton.md` file set (one owner per file, every file owned); the `After` ∪ cross-tree edge set is acyclic; every convergent-file owner is the nearest common ancestor of its declared `Contributors`; every summary/root `Review` is objectively checkable and references no `EVAL-NNN`
- Every technology choice in `technical.md` appears in the Technology Stack table of `constitution.md`
- No orphaned decisions (every choice has a rationale)
- Data contracts are expressed as named templates, not prose
- Every constitution principle states: the rule, the rationale, what breaks if violated
- `specs/technical.md` has `## Sources` present, first, and recording `specs/product.md` + `./docs/` plus every artefact read
- `specs/evaluation.md` exists and its Coverage Map accounts for every MUST requirement, every data contract, every constitution principle, and every promised skeleton file — each covered by ≥1 EVAL-NNN, or listed in Out of Scope with a reason
- Every criterion in `specs/evaluation.md` is objectively decidable (states the evidence that makes it PASS) and cites its source artefact in the `Source ref` column
- `specs/git.md` exists; its branch-naming rules are path-keyed and deterministic, and its pre-commit gates and "never commit" rules are consistent with `constitution.md`
- `.Codex/settings.json` exists and pre-authorises **every** command named in the Quality Gates, Pre-Commit Gates, git policy, and tasks — including the package-manager/resolver commands summary nodes run for convergent files — so no downstream skill (`/mdimplement` **and the per-node subagents it dispatches**, `/mdevaluation`, `/mdgit`) will hit a permission prompt; it adds no orphan orchestration-tool rules and does not enable worktree isolation, while withholding destructive/secret-exposing actions and preserving any pre-existing settings

---

### Self-critique pass (clear memory, `specs/`-only audit)

Once all ten outputs exist and pass the Quality check, you are **not done**. Turn
your own critique ability on what you just produced — but as an *independent* judge,
not the author who is attached to the result.

1. **Critique with a clear memory.** Run the audit in a **fresh context that has no
   memory of how you generated the specs** — dispatch a subagent (e.g. via the Agent
   tool, agent type `Explore` or `general-purpose`) whose sole job is to audit the
   specs. A clear memory is mandatory: it prevents you from "filling in" gaps from
   what you *meant*, so the audit sees only what the specs actually state.

2. **Audit ONLY `specs/`.** The critic may read **only files under `specs/`** — not
   `docs/`, not the code, not `.Codex/`, not anything else. It checks the spec set
   for **gaps and missing parts**: an artefact that references something never
   defined, a requirement with no plan/task coverage, a contract used but never
   specified, a capability with no requirement, an evaluation criterion with no
   source, internal contradictions, and unstated assumptions — judged purely from
   what `specs/` says about itself.

3. **No gap → finish.** If the `specs/`-only audit surfaces no gap or missing part,
   proceed to the Report; the run is complete.

4. **Any gap → reflect into `./docs/` ONLY, then restart from scratch.** A gap in the
   specs means the **human source of truth (`./docs/`) was missing the fact** the
   specs needed — so the fix belongs upstream, in `./docs/`, never in `specs/`:
   - **Do not patch `specs/`.** Do not edit code, `.Codex/settings.json`, or anything
     outside `./docs/`. The only write target for a detected gap is `./docs/`.
   - Determine the smallest `./docs/` change that supplies the missing fact. Ask the
     user for the decision where the answer is a genuine product choice (per the
     clarify-in-docs rules), then apply the approved edit to `./docs/` only.
   - **Stop and alert the user:** because `./docs/` has now changed, the specs just
     generated are stale and **`/mdtechnical` must be re-run from scratch** against
     the updated `./docs/`. State clearly that you are not continuing the chain — the
     user (or `/mdflow`) must restart `/mdtechnical`, which will regenerate every
     `specs/` artefact and the allowlist from the corrected docs.

   **Running unattended** (under `/mdflow`, a dispatched subagent, or "do not stop"):
   do not block — record each detected gap and the exact `./docs/` change it implies
   in the final report, apply only docs edits that need no human decision, and flag
   prominently that a from-scratch `/mdtechnical` re-run is required. Do not pretend
   the run is clean when the self-critique found gaps.

---

### Report

List all nine `specs/` files (`product.md` first, then the eight technical artefacts) plus `.Codex/settings.json` written; any `./docs/` edits made during the clarify loop (file + what changed) and how many clean-restart passes the product synthesis took; any open questions captured; confirm `specs/evaluation.md` is complete (Coverage Map has no uncovered MUST items); confirm the `tasks.md` WBS satisfies the `../CONVENTIONS.md` invariants (one owner per file, every file owned, acyclic dependency graph); confirm the permission allowlist covers every downstream command — including those the per-node subagents run — so the rest of the chain runs unattended; and report the **self-critique pass** outcome — that it audited `specs/` only with a clear memory, and either (a) found no gap, so the chain may proceed to `/mdimplement` (then `/mdgit` to commit per `specs/git.md`), or (b) found gaps, listing each, the `./docs/`-only edit it triggered, and the explicit alert that `./docs/` changed and **`/mdtechnical` must be restarted from scratch** before any downstream step runs.
