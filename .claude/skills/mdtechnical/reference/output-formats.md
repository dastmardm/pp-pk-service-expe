# `mdtechnical` — Output formats

The templates and per-file writing rules for the nine artefacts the `mdtechnical`
skill produces. `SKILL.md` describes the role of each file and the derivation
logic; this file holds the skeletons and checklists, loaded on demand when you
emit a given file. Each section corresponds to a "File N" in `SKILL.md`.

---

## File 1 — `specs/product.md`

The product specification — *what* the system does and *why*, in business
language, with **no implementation details**. It is synthesised exclusively from
the human-facing documentation under `./docs/` (the skill's sole product-design
input). Default path `specs/product.md`; if the repo already uses a different name
for this artefact (e.g. `specs/product_specification.md`), overwrite that file
rather than creating a duplicate.

```
# Product Specification
## Sources
## Purpose
## Core Capabilities
## Key Actors
## Data Flow
## Integration Surface
## Operational Model
## Constraints and Non-Goals
## Open Questions
```

The `## Sources` section is **mandatory and must come first**. It lists **only
files under `./docs/`** — every documentation file actually read, each as a path —
so the whole chain traces back to the human source of truth. Do **not** list any
file outside `./docs/`, and never list `$ARGUMENTS` text.

Writing rules:
- No implementation details (no language names, no framework names, no config syntax).
- Every statement traceable to a `./docs/` file listed in `## Sources`.
- No product-design fact may exist here that is absent from `./docs/`. Anything the
  docs do not settle (and the human declined to record in `./docs/`) stays an
  `## Open Questions` entry — never an asserted fact.
- On a revision, the spec reflects the *current* `./docs/`, with no stale claims.

---

## File 2 — `specs/technical.md`

```
# Technical Specification
## Sources
## Architecture Overview
## Data Contracts
## Schema
## Component Interfaces
## Infrastructure
## Configuration and Secrets
## Technology Decisions
## Open Questions
```

The `## Sources` section is **mandatory and must come first** (see
`../../CONVENTIONS.md` → Sources contract). It records the inputs this spec was
derived from, so downstream skills (implement → evaluation → fix) can trace lineage
upstream. Record:
- `specs/product.md` (or the repo's product-spec file) — the File 1 product spec
  this same run produced, the upstream source-of-truth for *what* and *why*.
- `./docs/` — the human-facing documentation tree the product spec was synthesised
  from (so technical lineage reaches the human source); the concrete files read.
- Every existing technical artefact read (architecture docs, schema files, existing
  code): each path, whether it is a file or folder, and for folders the concrete
  files read.

---

## File 3 — `specs/constitution.md`

```
# Project Constitution
## Core Principles
<!-- Each principle is NON-NEGOTIABLE unless amended.
     Cover: isolation rules, data flow invariants, schema contracts,
     compute model, toolchain mandates, observability requirements.
     Each principle states: the rule, why it exists, what violating it breaks. -->
## Technology Stack
<!-- Table: Layer | Technology | Version/Notes | Prohibited alternatives -->
## Development Workflow
### Quality Gates
<!-- Ordered checks that MUST pass before any change is merged. -->
### Adding a New Component
<!-- Steps for the most common extension pattern. -->
### Schema / Data Contract Changes
## Governance
<!-- Amendment procedure, versioning policy (MAJOR/MINOR/PATCH), compliance expectation. -->
```

If `specs/constitution.md` already exists, update it — preserve ratified
principles, only add or amend where the new technical spec introduces changes.

---

## File 4 — `specs/requirements.md`

```
# Requirements

## Functional Requirements
<!-- Numbered list. Each requirement is one testable statement of behaviour.
     Format: REQ-NNN | Priority (MUST/SHOULD/COULD) | Statement -->

## Non-Functional Requirements
<!-- Performance, reliability, security, scalability, operability.
     Each must be measurable: not "fast" but "p95 latency < 500ms". -->

## Constraints
<!-- Hard limits that are given, not chosen: compliance rules, existing systems,
     budget ceilings, platform restrictions. -->

## Non-Goals
<!-- Explicit list of what this system does NOT do — prevents scope creep. -->

## Acceptance Criteria
<!-- One criterion per MUST requirement. How will we know REQ-NNN is satisfied?
     Technology-agnostic — describes observable outcomes, not implementation. -->
```

---

## File 5 — `specs/plan.md`

```
# Implementation Plan

## Summary
<!-- One paragraph: goal, approach, key constraints. -->

## Work Breakdown
<!-- How the project decomposes into the WBS tree (../../CONVENTIONS.md → Work Breakdown
     Structure): the top 1–2 levels of the tree and the rationale for the cut — why these
     subtrees, what each is responsible for, where the convergent/integration files live.
     This replaces flat sequential "phases": ordering is carried by the tree structure and
     dependency edges, not by phase bands. -->

## Execution Model
<!-- State the fork-join model so a reader knows how tasks.md will be run: leaves run
     concurrently within a dependency wave; each summary node blocks until its children
     resolve, then aggregates (writing any convergent files it owns) → reviews → reports
     upward; the root resolves last. Note that the file-ownership invariant is what makes
     parallel leaves safe, and that the same tree walked sequentially in bottom-up order is
     equivalent — concurrency is an optimisation, not a correctness requirement. -->

## Key Decisions
<!-- Table: Decision | Options considered | Choice | Rationale -->

## Risks and Mitigations
<!-- Table: Risk | Likelihood | Impact | Mitigation -->

## Constitution Check
<!-- Confirm no principle from specs/constitution.md is violated.
     List any tensions and how they are resolved. -->
```

---

## File 6 — `specs/tasks.md`

`specs/tasks.md` is the project's **Work Breakdown Structure** — the hierarchical tree of
nodes `/mdimplement` executes. The full model (node kinds, the file-ownership invariant,
convergent-file protocols, dependency edges, fork-join semantics, and the machine-checkable
quality invariants) is defined once in `../../CONVENTIONS.md` → Work Breakdown Structure.
This template fixes the **on-page encoding** so the tree is recoverable unambiguously.

```
# Tasks

## Overview
<!-- One short paragraph, then the tree as an indented ID outline, e.g.
     W1 (root)    — <project>
       W1.1 (summary) — <name>
         W1.1.1 (leaf) — <name>
         W1.1.2 (leaf) — <name>
       W1.2 (summary) — <name>
     The outline is a reading aid only; the per-node Parent/Children fields below are
     authoritative for structure. -->

## Nodes
<!-- One block per node (order is free — structure comes from the fields, not position).
     Every field is required unless marked optional. -->

### W1 — [title]
- **Type**: root              <!-- root | summary | leaf — declared, never inferred -->
- **Parent**: none
- **Children**: W1.1, W1.2
- **Owns**: <files this node writes, comma-separated, or `none`>
- **Contributors**: <child IDs contributing to each convergent file this node owns — required per convergent file, omitted otherwise>
- **After**: none             <!-- same-parent sibling IDs this node waits on, or `none` -->
- **Review**: <objectively-checkable integration assertion — REQUIRED for summary/root>
- **Done-when**: <objectively-checkable completion condition>

### W1.1.1 — [title]
- **Type**: leaf
- **Parent**: W1.1
- **Children**: none
- **Owns**: src/oppp/foo.py
- **REQ**: REQ-007             <!-- ≥1 REQ id, OR `Structural: <reason>` for non-functional files -->
- **After**: none
- **Done-when**: <verifiable without running the full system>

## Cross-tree dependencies
<!-- The ONLY place a dependency between two DIFFERENT subtrees may appear.
     One row each: <consumer-id> after <producer-id> — interface: <what the producer exposes>.
     Leave empty when the tree is a clean fork-join (preferred). -->
```

Rules for writing the WBS:
- **Declare, don't infer.** `Type`, `Parent`, `Children` are explicit on every node. A
  node whose `Type` contradicts its `Children` (a `leaf` with children, a `summary` with
  none) is a spec defect (`../../CONVENTIONS.md` → invariant 4).
- **One owner per file, complete coverage.** The union of all `Owns` lists equals exactly
  the `skeleton.md` file set, no file owned twice (invariant 6). A leaf owns the file(s)
  that must be written *together* by one worker; a summary owns only convergent files and
  lists their `Contributors`.
- **Every leaf is verifiable and traceable.** Its `Done-when` is checkable without running
  the full system, and it names ≥1 `REQ` (or is tagged `Structural:`). No node says
  "implement X" without naming the exact file in `Owns`.
- **Summary `Review` is self-contained** — an integration assertion in this file's own
  terms (child interfaces resolve, convergent file lists every contribution, subtree
  imports/builds/tests). It MUST NOT reference `EVAL-NNN` (`../../CONVENTIONS.md` →
  WHAT/HOW boundary).
- **Dependencies are explicit and acyclic.** `After` references existing same-parent
  siblings; cross-subtree edges live only under `Cross-tree dependencies`; the combined
  edge set is acyclic (invariant 7).

---

## File 7 — `specs/skeleton.md`

```
# Project Skeleton

## Purpose
<!-- Why this skeleton exists: it is the agreed-upon file map that `/mdimplement` must
     produce and `/mdevaluation` will verify, AND the authoritative file→owner map for the
     WBS (../../CONVENTIONS.md → File-ownership invariant). -->

## Directory Tree
<!-- Full annotated tree. Every leaf that will be created or modified is listed.
     Annotation format: path  ← one-line purpose  [owner: W-id] -->

## File Inventory
<!-- Table: File | Layer | Purpose | Owner (WBS node) -->
<!-- "Owner" is the AUTHORITATIVE file→node map: exactly one WBS node id per file.
     Each node's `Owns` list in tasks.md must agree with this column. -->

## Conventions
<!-- Naming rules, module boundaries, what goes where.
     Define here the migration-file naming convention and the env template file
     that /mdimplement and /mdfix will consult. -->
```

Rules for writing the skeleton:
- Every file listed in `tasks.md` appears here, and every file here has exactly one owning
  WBS node — the union of all owners covers every file, none owned twice
  (`../../CONVENTIONS.md` → invariant 6). The `Owner` column is the source of truth; a
  conflict with a node's `Owns` list in `tasks.md` is a spec defect.
- A glob or directory row may carry an `Owner` only if **every** file it expands to has
  that same owner; otherwise expand it into concrete per-file rows so each gets its owner.
- No implementation detail — purpose descriptions say *what* the file is for, not *how* it works

---

## File 8 — `specs/evaluation.md`

```
# Evaluation Criteria

## Sources
<!-- The six artefacts these criteria are derived from, by path. Mirrors the
     lineage in technical.md so the evaluation is traceable. -->

## How to read this file
<!-- One paragraph: each criterion is a single objectively-decidable check.
     /mdevaluation assigns PASS / PARTIAL / FAIL / N/A per criterion and cites
     file:line evidence (BLOCKED if the criterion itself is defective).
     This file defines WHAT; /mdevaluation defines HOW. -->

## Criteria
<!-- Table, one row per check:
     | ID | Source ref | Category | Criterion (objectively decidable) | Evidence to look for | Severity |
     - ID            : EVAL-NNN, stable across reports
     - Source ref    : the artefact + item it traces to (e.g. REQ-012, CONST-Principle-3, CONTRACT-BRONZE-PATH)
     - Category      : Requirement | Data contract | Constitution | Skeleton/Structure | Non-functional
     - Criterion     : a single check, phrased so PASS/FAIL is unambiguous —
                       NOT "auth works" but "every Spark job sets fs.s3a creds on the
                       builder before getOrCreate (pipeline/.../*.py)"
     - Evidence      : the concrete artefact an auditor should find (file, symbol,
                       config key, path string) to decide the verdict
     - Severity      : BLOCKER | MAJOR | MINOR — drives fix ordering downstream -->

## Coverage Map
<!-- Table proving completeness: every MUST requirement, every data contract,
     every constitution principle, and every promised skeleton file appears as
     at least one EVAL-NNN. | Source item | Covered by | -->

## Out of Scope
<!-- Items deliberately NOT evaluated, with the reason (e.g. external service,
     future phase). Prevents /mdevaluation from flagging intentional gaps. -->
```

Rules for writing the evaluation criteria:
- **Objectively decidable.** Each criterion must be answerable PASS/PARTIAL/FAIL by inspecting the codebase alone — no judgement calls, no "is this good?". If you cannot state the evidence that would make it PASS, rewrite it.
- **Traceable.** Every criterion cites its source artefact + item in the `Source ref` column; nothing is invented outside the six artefacts.
- **Complete.** The Coverage Map must show every MUST requirement, data contract, constitution principle, and promised skeleton file is covered by ≥1 criterion. Gaps go in Out of Scope with a reason, never silently dropped.
- **Self-contained.** `/mdevaluation` must be able to run using only `specs/evaluation.md` + the codebase; a criterion that requires reading another spec to interpret it is underspecified — inline what is needed.
- **WBS-agnostic.** Criteria trace to requirements, data contracts, constitution principles, and skeleton files — **never to WBS node ids**. The WBS (`tasks.md`) is an implementation-process structure that `/mdevaluation` does not consume, and `evaluation.md` is the sole owner of *what* gets checked; keep the lineage one-directional (`evaluation.md` may cite `tasks.md`, never the reverse). Do not add an owning-node column.

---

## File 9 — `specs/git.md`

```
# Git Workflow

## Sources
<!-- Mirrors the lineage: derived from constitution.md (Quality Gates, constraints),
     the repo layout, and any existing VCS conventions you found. -->

## Branch Naming
<!-- Table: Change class | Path globs that trigger it | Branch pattern | Base branch -->

## Mixed-Change Rule
<!-- How to handle a changeset spanning multiple classes (split / precedence). -->

## Commit Convention
<!-- Message format, allowed types, scope rule, mandatory trailers. -->

## Push & PR Policy
<!-- When to push; when to open a PR; PR title/body format; target branch; trailers. -->

## Pre-Commit Gates
<!-- Ordered checks that must pass before a commit is allowed. -->

## Never Commit
<!-- Secrets, credential files, generated/large artefacts — project-specific. -->

## Safety & Idempotency
<!-- Behaviour when branch exists / nothing to commit / PR already open. -->
```

Rules for writing `specs/git.md`:
- **Deterministic.** Given a set of changed paths, the branch name, commit message shape, and PR decision must be derivable with no judgement call.
- **Path-keyed.** Every branch class is triggered by concrete path globs an automated reader can match.
- **Consistent with the constitution.** Pre-commit gates and "never commit" rules must not contradict `constitution.md`; reuse its Quality Gates and constraints.
- **Self-contained.** `/mdgit` must be able to run using only `specs/git.md` + the working-tree diff.

---

## Harness permissions — `.claude/settings.json`

```jsonc
// .claude/settings.json  — illustrative; derive the real rules from the specs above.
{
  "permissions": {
    "allow": [
      "Edit",
      "Write",
      "Bash(git:*)",
      "Bash(gh:*)",
      "Bash(ruff:*)",
      "Bash(pytest:*)",
      "Bash(make:*)"
      // ...every other command the downstream gates/tasks need
    ]
  }
}
```

Rules for writing `.claude/settings.json`:
- **Complete.** Every command named in any Quality Gate, Pre-Commit Gate, task, or
  the git policy has a matching allow rule. If a downstream skill would have to ask,
  the rule is missing.
- **Covers parallel execution.** `/mdimplement` runs the WBS by dispatching subagents from
  the main session, and **subagents inherit this project allowlist** — so the unattended
  guarantee holds transitively only if every `Bash`/`Edit`/`Write` command any **leaf or
  summary** node runs is allowed here. That includes the package-manager / resolver
  commands a summary node runs to assemble convergent manifest or lockfile files
  (`../../CONVENTIONS.md` → Convergent files). Do **not** add allow rules for orchestration
  tool *names* (e.g. `Agent`, `Workflow`) — they are not `Bash`-gated and would be orphan
  rules; and do **not** rely on this file to enable worktree isolation — the file-ownership
  invariant removes the need for it (workers also never run `git`; staging is `/mdgit`'s job).
- **Least-privilege.** Scope `Bash` rules to specific commands/prefixes (e.g.
  `Bash(ruff:*)`), not a blanket `Bash(*)`. Pre-authorise what the chain needs and
  no more.
- **Never auto-approve the dangerous.** Do **not** add rules that would let a
  downstream skill commit a secret, force-push, delete history, or run destructive
  shell — those must still surface. The "Never Commit" list in `git.md` and this
  allowlist must be consistent.
- **Merge, don't clobber.** If `.claude/settings.json` already exists, add the
  missing rules and keep existing ones; do not remove the user's settings.
- **Self-consistent.** Every command pre-approved here is one that actually appears
  in `constitution.md`, `git.md`, or `tasks.md` — no orphan permissions.
