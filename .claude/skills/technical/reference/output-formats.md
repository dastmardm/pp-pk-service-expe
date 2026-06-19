# `technical` — Output formats

The templates and per-file writing rules for the nine artefacts the `technical`
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

## Phases
<!-- Each phase has: name, goal, deliverable, success signal.
     Phases are ordered by dependency — earlier phases unblock later ones.
     Example phases: Foundation → Core → Integration → Hardening -->

### Phase N — [Name]
**Goal**: ...
**Deliverable**: ...
**Success signal**: ...

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

```
# Tasks

## Format
<!-- [ID] [P?] Description → file:path | done when: condition -->
<!-- [P] = can run in parallel (touches different files, no shared dependency) -->

## Phase 1 — [Name]
- [ ] T001 ...
- [ ] T002 [P] ...

## Phase 2 — [Name]
- [ ] T003 ...

## Dependencies
<!-- Which tasks block which. -->

## Parallel opportunities
<!-- Groups of tasks that can run concurrently. -->
```

Rules for writing tasks:
- Each task touches exactly one logical unit (one file, one migration, one config block)
- The done-when condition is verifiable without running the full system
- Tasks within a phase that touch different files are marked [P]
- No task says "implement X" without naming the exact file

---

## File 7 — `specs/skeleton.md`

```
# Project Skeleton

## Purpose
<!-- Why this skeleton exists: it is the agreed-upon file map that
     `/implement` must produce and `/evaluation` will verify. -->

## Directory Tree
<!-- Full annotated tree. Every leaf that will be created or modified is listed.
     Annotation format: path  ← one-line purpose -->

## File Inventory
<!-- Table: File | Layer | Purpose | Created by task -->

## Conventions
<!-- Naming rules, module boundaries, what goes where.
     Define here the migration-file naming convention and the env template file
     that /implement and /fix will consult. -->
```

Rules for writing the skeleton:
- Every file listed in `tasks.md` appears here
- Every file here has a corresponding task
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
     /evaluation assigns PASS / PARTIAL / FAIL / N/A per criterion and cites
     file:line evidence (BLOCKED if the criterion itself is defective).
     This file defines WHAT; /evaluation defines HOW. -->

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
     future phase). Prevents /evaluation from flagging intentional gaps. -->
```

Rules for writing the evaluation criteria:
- **Objectively decidable.** Each criterion must be answerable PASS/PARTIAL/FAIL by inspecting the codebase alone — no judgement calls, no "is this good?". If you cannot state the evidence that would make it PASS, rewrite it.
- **Traceable.** Every criterion cites its source artefact + item in the `Source ref` column; nothing is invented outside the six artefacts.
- **Complete.** The Coverage Map must show every MUST requirement, data contract, constitution principle, and promised skeleton file is covered by ≥1 criterion. Gaps go in Out of Scope with a reason, never silently dropped.
- **Self-contained.** `/evaluation` must be able to run using only `specs/evaluation.md` + the codebase; a criterion that requires reading another spec to interpret it is underspecified — inline what is needed.

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
- **Self-contained.** `/git` must be able to run using only `specs/git.md` + the working-tree diff.

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
