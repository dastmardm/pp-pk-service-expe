---
name: "mdtechnical"
description: "Ingest the human-facing docs under ./docs/, synthesise the product specification, then translate it into the full technical blueprint, all downstream planning artefacts, and the .sdd/settings.json permission allowlist. Finishes with a fresh-memory self-critique of specs/ that reflects any gap back into docs/ and, if so, requires restarting from scratch. The chain's entry point — use after a human edits ./docs/, before /mdimplement."
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
artefacts) **plus** the harness permission allowlist (`.sdd/settings.json`), and
finish with the self-critique pass.

---

## Execution Model

This skill uses a **parallel multi-agent architecture**. The Main Agent (you) owns
the sequential upstream work: reading `./docs/`, running the clarify-in-docs loop,
and writing the two upstream artefacts (`product.md` and `technical.md`). Once those
exist, work fans out to parallel Node Agents, each producing one output artefact from
its minimal input slice. A final aggregation and verification pass closes the run.

```
  Phase A — Main Agent
  ─────────────────────────────────────────────────
  read ./docs/ + clarify-in-docs loop → product.md
  read repo artefacts               → technical.md

  Phase B — Parallel (4 Node Agents, after technical.md)
  ─────────────────────────────────────────────────
  Node-B1: constitution.md    ← technical.md
  Node-B2: requirements.md    ← product.md + technical.md
  Node-B3: plan.md            ← product.md + technical.md
  Node-B4: git.md             ← technical.md + repo conventions

  Phase C — Sequential pair (after plan.md)
  ─────────────────────────────────────────────────
  Node-C1: tasks.md           ← plan.md + technical.md
  Node-C2: skeleton.md        ← tasks.md + technical.md

  Phase D — Parallel (2 Node Agents, after all of Phase B + C)
  ─────────────────────────────────────────────────
  Node-D1: evaluation.md      ← requirements.md + technical.md + constitution.md
                                 + plan.md + tasks.md + skeleton.md
  Node-D2: .sdd/settings.json ← constitution.md + git.md + tasks.md
                                 + skeleton.md + technical.md

  Phase E — Quality Check + Self-Critique (Main Agent + one subagent)
  ─────────────────────────────────────────────────
  Main Agent: aggregate Node Reports, run Quality Check
  Self-critique subagent: reads specs/ only, no memory of generation
```

Each Node Agent receives **only its declared input slice** — it reads no files
beyond what is listed for it above, and writes only its single output file.
Cross-node inconsistencies surface as findings in the Node Report and are arbitrated
by the Main Agent in Phase E.

---

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
and pre-authorise them in `.sdd/settings.json`. Deriving the toolchain is
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

---

## Phase A — Main Agent: map, ingest, and write upstream artefacts

You are the Main Agent. Execute Phase A entirely yourself — do not dispatch any
agent until Phase A is complete and both upstream artefacts exist.

### A1 — Map `./docs/`

Before reading any documentation content:

1. Run `find ./docs -type f -name "*.md" | sort` to enumerate every file.
2. Group files into **nodes** — one node per top-level subfolder directly under
   `./docs/`. Files at the root of `./docs/` form a special `_root` node.
3. Read **only** `./docs/index.md` (if present) to understand the declared purpose
   of each node. Do not read any other documentation file yet.
4. Record the node map in your working memory:

```
docs_node_map:
  _root:       [file1.md, file2.md, …]
  service-a:   [service-a/overview.md, …]
  service-b:   [service-b/README.md, …]
  …
```

This map governs the minimal-context discipline: each downstream Node Agent
receives only the files relevant to its output, not the whole tree.

### A2 — Synthesise `specs/product.md` (File 1)

Read every documentation file under `./docs/` (recurse into all subdirectories);
follow cross-references *within* `./docs/`, but never out of it. Record every
`./docs/` file read for the product spec's `## Sources`. Treat `./docs/research/**`
as **derived evidence**, not ratified intent (`../CONVENTIONS.md` → `docs/` authority):
it informs the product spec but does not by itself settle a product decision, and where
it conflicts with human-authored docs the human-authored intent wins — record the
conflict as an `## Open Questions` entry rather than resolving it in the derived file's
favour.

Run the **clarify-in-docs loop** (above) until a full pass reads cleanly. Write
`specs/product.md` only once no further `./docs/` change is needed.

→ template & writing rules: `reference/output-formats.md` → File 1.

### A3 — Write `specs/technical.md` (File 2)

Read any existing technical artefacts in the repository (architecture docs, schema
files, existing code) to avoid contradicting prior decisions. Discover these by
exploring the repo — do not assume fixed paths. Record every such artefact read in
the technical spec's `## Sources` (path + whether file or folder; for folders, the
concrete files read).

Derive and document, for each capability in the product spec:
- The architectural components that implement it
- The data contracts it depends on (schemas, path templates, field requirements)
- The infrastructure it requires
- The configuration and secrets it consumes

Write `specs/technical.md` once complete.

→ template & Sources rules: `reference/output-formats.md` → File 2.

---

## Phase B — Parallel Node Agents (after `technical.md` exists)

Spawn four **Node Agents** in parallel. Pass each Node Agent only its declared input
slice (listed below) and the hard scope rule: **read only your input files, write
only your output file**.

### Node-B1 — `specs/constitution.md` (File 3)

**Input:** `specs/technical.md` only. If `specs/constitution.md` already exists,
also read it (preserve ratified principles; amend only where the new technical spec
introduces changes).

**Task:** Produce the project's binding governance document. Answers one question:
*what rules must every contributor and every AI assistant follow, unconditionally?*
Not a description of how the system works — a set of non-negotiable constraints that
guard the architecture over time.

→ template: `reference/output-formats.md` → File 3.

**Return a Node Report** (structured, to the Main Agent):
```
node: constitution
file_written: specs/constitution.md
cross_node_findings: [any inconsistency spotted that involves another output file]
```

### Node-B2 — `specs/requirements.md` (File 4)

**Input:** `specs/product.md` + `specs/technical.md` only.

**Task:** Produce the single authoritative list of what the system must and must not
do, derived from the product spec and the technical spec. Written so any stakeholder
— technical or not — knows exactly what "done" means.

→ template: `reference/output-formats.md` → File 4.

**Return a Node Report:**
```
node: requirements
file_written: specs/requirements.md
cross_node_findings: […]
```

### Node-B3 — `specs/plan.md` (File 5)

**Input:** `specs/product.md` + `specs/technical.md` only.

**Task:** Produce the implementation roadmap. Present the **Work Breakdown Structure**
decomposition (the top levels of the tree and the rationale for the cut) and the
**fork-join execution model** `/mdimplement` will run, record key decisions with
rationale, and include a Constitution Check confirming no principle is violated.

→ template: `reference/output-formats.md` → File 5; model: `../CONVENTIONS.md` →
Work Breakdown Structure.

**Return a Node Report:**
```
node: plan
file_written: specs/plan.md
wbs_top_level_nodes: [list of top-level WBS node ids and names — passed to Phase C]
cross_node_findings: […]
```

### Node-B4 — `specs/git.md` (File 9)

**Input:** `specs/technical.md` only, plus repo root files that encode existing
conventions (CONTRIBUTING, commit log, CODEOWNERS, PR templates) — read only those,
not the full codebase.

**Task:** Produce the project's **version-control contract** — the authoritative rules
for how any change is committed and proposed. Rules must be deterministic and
machine-applicable. Cover at minimum: change-classification → branch; branch base &
protection; commit message convention (incl. the mandated `Co-Authored-By` trailer);
push/PR policy; pre-commit gates (mirror the constitution's Quality Gates); what must
NOT be committed; and idempotency/safety.

→ template & git-writing rules: `reference/output-formats.md` → File 9.

**Return a Node Report:**
```
node: git
file_written: specs/git.md
pre_commit_gates: [list of gate commands — passed to Phase D for settings.json]
cross_node_findings: […]
```

---

## Phase C — Sequential pair (after `plan.md` exists)

Phase C has two nodes that must run sequentially (Node-C2 depends on Node-C1's
output). Dispatch Node-C1; when it returns, dispatch Node-C2.

### Node-C1 — `specs/tasks.md` (File 6)

**Input:** `specs/plan.md` + `specs/technical.md` only.

**Task:** Produce the project's **Work Breakdown Structure** — the hierarchical tree
of nodes `/mdimplement` executes. Leaf nodes are atomic, file-disjoint units (the
unit of parallel execution); summary nodes block on their children, then aggregate,
review, and report upward; the root resolves last, bottom-up. Every node is
self-contained: its kind, owned files, dependencies, and a verifiable done-when are
explicit on the node.

→ template & node grammar: `reference/output-formats.md` → File 6; model:
`../CONVENTIONS.md` → Work Breakdown Structure.

**Return a Node Report:**
```
node: tasks
file_written: specs/tasks.md
wbs_leaf_nodes: [list of all leaf node ids, their Owns lists, and Done-when]
convergent_files: [list of convergent files with their owning summary nodes]
cross_node_findings: […]
```

### Node-C2 — `specs/skeleton.md` (File 7)

**Input:** `specs/tasks.md` + `specs/technical.md` only.

**Task:** Produce the complete map of every file and directory the implementation
will create or significantly modify, with a one-line purpose for each — the blueprint
of the codebase shape, written before any code. The `Owner (WBS node)` column in its
File Inventory must agree with the `Owns` lists in `tasks.md` (one owner per file,
every file owned). Its `## Conventions` section defines the migration-naming and
env-template conventions `/mdimplement` consults.

→ template & skeleton-writing rules: `reference/output-formats.md` → File 7;
ownership invariant: `../CONVENTIONS.md` → Work Breakdown Structure.

**Return a Node Report:**
```
node: skeleton
file_written: specs/skeleton.md
file_inventory: [complete list of {path, purpose, owner_node}]
cross_node_findings: […]
```

---

## Phase D — Parallel Node Agents (after all of Phase B + C)

Spawn two **Node Agents** in parallel. Each receives its declared input slice only.

### Node-D1 — `specs/evaluation.md` (File 8)

**Input:** `specs/requirements.md` + `specs/technical.md` + `specs/constitution.md`
+ `specs/plan.md` + `specs/tasks.md` + `specs/skeleton.md` only.

**Task:** Produce the **evaluation criteria** — the authoritative, machine-checkable
list of *what* the `/mdevaluation` skill must verify in the codebase. Derive criteria
**from the input artefacts**, not from imagination: one criterion per MUST requirement
in `requirements.md` (and SHOULD where verifiable); one per data contract / path
template in `technical.md`; one per non-negotiable principle in `constitution.md`;
one per file the skeleton promises that must exist and serve its stated purpose.
Every criterion must be objectively decidable as PASS / PARTIAL / FAIL / N/A.

→ template & criteria-writing rules: `reference/output-formats.md` → File 8.

**Return a Node Report:**
```
node: evaluation
file_written: specs/evaluation.md
coverage_map_summary: {must_reqs: N, covered: N, uncovered: [list]}
cross_node_findings: […]
```

### Node-D2 — `.sdd/settings.json` (File 10)

**Input:** `specs/constitution.md` + `specs/git.md` + `specs/tasks.md`
+ `specs/skeleton.md` + `specs/technical.md` only.

**Task:** Produce the harness permission file that lets every downstream skill run
**without a single permission prompt**. Enumerate every tool call the downstream
skills will make and pre-approve it, so `/mdimplement`, `/mdevaluation`, and
`/mdgit` are never blocked. Derive the allow list **from the input artefacts**:
- From **`constitution.md` → Quality Gates** and **`git.md` → Pre-Commit Gates**:
  every checker/test/build command → `Bash(...)` allow rules.
- From **`git.md` → Push & PR Policy**: `git`/`gh` → `Bash(git:*)`, `Bash(gh:*)`.
- From **`tasks.md` / `skeleton.md`**: directories implementation writes under, and
  any build/run/migration commands. Include the **package-manager / resolver commands
  summary nodes run for convergent manifest/lockfile files** (`../CONVENTIONS.md` →
  Convergent files). The subagents `/mdimplement` dispatches inherit this allowlist;
  add **no** rules for orchestration tool names and **none** for worktree isolation.
- From **`technical.md` → Configuration and Secrets**: writing the env template file
  → covered by `Edit`/`Write`.

→ template & allowlist rules: `reference/output-formats.md` → Harness permissions.

**Return a Node Report:**
```
node: settings
file_written: .sdd/settings.json
allow_rules_count: N
cross_node_findings: […]
```

---

## Phase E — Aggregate, Quality Check, and Self-Critique (Main Agent)

### E1 — Aggregate Node Reports

Collect all Node Reports from Phases B, C, and D. For each `cross_node_findings`
entry: determine whether it is auto-resolvable by the Main Agent (e.g. a
terminology inconsistency between two specs files) or requires human input. Assign
a global finding ID (`FIND-001`, …) to each.

Auto-resolve what you can by editing the affected `specs/` file(s) directly. For
findings that require human input, surface them to the user (one focused question
per finding, naming the files that will change).

### E2 — Quality Check

Verify the full output set satisfies every invariant:

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
- `.sdd/settings.json` exists and pre-authorises **every** command named in the Quality Gates, Pre-Commit Gates, git policy, and tasks — including the package-manager/resolver commands summary nodes run for convergent files — so no downstream skill (`/mdimplement` **and the per-node subagents it dispatches**, `/mdevaluation`, `/mdgit`) will hit a permission prompt; it adds no orphan orchestration-tool rules and does not enable worktree isolation, while withholding destructive/secret-exposing actions and preserving any pre-existing settings

### E3 — Self-Critique Pass (clear-memory subagent)

Dispatch a **self-critique subagent** (agent type `Explore` or `general-purpose`)
whose sole job is to audit the specs. Pass it:
- The list of all `specs/` files.
- This instruction: **read only files under `specs/`, nothing else**. No `./docs/`,
  no code, no `.sdd/`. Check the spec set for gaps and missing parts — an artefact
  that references something never defined, a requirement with no plan/task coverage,
  a contract used but never specified, a capability with no requirement, an evaluation
  criterion with no source, internal contradictions, unstated assumptions — judged
  purely from what `specs/` says about itself. Return a structured finding list.

A clear memory is mandatory: it prevents filling in gaps from what was *meant*, so
the audit sees only what the specs actually state.

**No gap → finish.** If the subagent surfaces no gap or missing part, proceed to
the Report; the run is complete.

**Any gap → reflect into `./docs/` ONLY, then restart from scratch.** A gap in the
specs means the **human source of truth (`./docs/`) was missing the fact** the specs
needed — so the fix belongs upstream, in `./docs/`, never in `specs/`:
- **Do not patch `specs/`.** The only write target for a detected gap is `./docs/`.
- Determine the smallest `./docs/` change that supplies the missing fact. Ask the
  user for the decision where the answer is a genuine product choice, then apply the
  approved edit to `./docs/` only.
- **Stop and alert the user:** because `./docs/` has now changed, the specs just
  generated are stale and **`/mdtechnical` must be re-run from scratch** against
  the updated `./docs/`. State clearly that you are not continuing the chain — the
  user (or `/mdflow`) must restart `/mdtechnical`.

**Running unattended:** do not block — record each detected gap and the exact
`./docs/` change it implies in the final report, apply only docs edits that need no
human decision, and flag prominently that a from-scratch `/mdtechnical` re-run is
required. Do not pretend the run is clean when the self-critique found gaps.

---

## Report

List all nine `specs/` files (`product.md` first, then the eight technical artefacts)
plus `.sdd/settings.json` written; any `./docs/` edits made during the clarify loop
(file + what changed) and how many clean-restart passes the product synthesis took;
any open questions captured; confirm `specs/evaluation.md` is complete (Coverage Map
has no uncovered MUST items); confirm the `tasks.md` WBS satisfies the
`../CONVENTIONS.md` invariants (one owner per file, every file owned, acyclic
dependency graph); confirm the permission allowlist covers every downstream command —
including those the per-node subagents run — so the rest of the chain runs unattended;
and report the **self-critique pass** outcome — that it audited `specs/` only with a
clear memory, and either (a) found no gap, so the chain may proceed to `/mdimplement`
(then `/mdgit` to commit per `specs/git.md`), or (b) found gaps, listing each, the
`./docs/`-only edit it triggered, and the explicit alert that `./docs/` changed and
**`/mdtechnical` must be restarted from scratch** before any downstream step runs.
