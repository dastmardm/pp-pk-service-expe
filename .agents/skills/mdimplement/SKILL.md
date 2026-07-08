---
name: "mdimplement"
description: "Build or update the codebase to satisfy a technical specification and its planning artefacts. Use as the third pipeline step, after /mdtechnical and before /mdevaluation."
argument-hint: "Path to technical specification (default: specs/technical.md); optional scope filter"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

$ARGUMENTS may contain a path to the technical specification and/or a scope filter.
The scope filter may be a **WBS node id** (e.g. `W1.2`) — meaning *build that subtree only* —
or free text (e.g. "bronze only"). Default spec path: `specs/technical.md`.

## Outline

You are the **`mdimplement`** step:

```
technical → implement → evaluation
```

Produce or update the codebase so it satisfies the technical specification, by **executing
the Work Breakdown Structure** in `specs/tasks.md`. The WBS is a hierarchical tree: leaf
nodes are atomic, file-disjoint units (the unit of parallel work); summary nodes block
until their children resolve, then aggregate, review, and report upward; the root resolves
last, bottom-up. The full model — node kinds, the file-ownership invariant, convergent-file
protocols, dependency edges, fork-join and failure semantics — is defined in
`../CONVENTIONS.md` → Work Breakdown Structure. Read it; it governs everything below.

---

## Execution Model

This skill uses a **parallel multi-agent architecture** that mirrors the WBS tree.
The Main Agent (you) owns the mapping phase: parse the tree, validate it, build the
execution order, then fan out. Leaf nodes whose dependencies are resolved run
concurrently as **Leaf Agents**. Summary nodes run as **Summary Agents** only after
all their children have reported. The root resolves last. A final parallel
**Verification pass** confirms every node is closed before the report.

```
  Phase A — Main Agent
  ─────────────────────────────────────────────────
  Read tasks.md + skeleton.md ONLY → build node_map
  Validate WBS invariants
  Build topological execution order
  Apply scope filter if present

  Phase B — Parallel waves (Leaf Agents, one per ready leaf)
  ─────────────────────────────────────────────────
  Wave 1: all leaves with no unresolved After-deps → run concurrently
  Wave 2: leaves unblocked by Wave 1 completing → run concurrently
  … repeat until all leaves resolved

  Phase C — Summary Agents (one per summary node, bottom-up)
  ─────────────────────────────────────────────────
  Each Summary Agent runs only after ALL its children have reported
  Writes convergent files it Owns, runs Review, reports upward

  Phase D — Root Agent
  ─────────────────────────────────────────────────
  Runs after all summary nodes resolve; runs final Review; reports done

  Phase E — Parallel Verification (one Verification Agent per node)
  ─────────────────────────────────────────────────
  Spawned in parallel after Phase D
  Each confirms its node's Done-when is satisfied
  Reports pass/fail per node back to Main Agent
```

The Main Agent owns fan-out entirely. **No agent spawns sub-agents** — only the
Main Agent dispatches. If a parallel substrate is unavailable, walk the tree
**sequentially in bottom-up (post-order) order**; the result is identical but
slower. Treat sequential fallback as a last resort, not a default.

---

## Phase A — Map the WBS Tree (Main Agent only)

### A1 — Read minimal context first

Read **only** `specs/tasks.md` and `specs/skeleton.md` at this stage. Do not read
any other planning artefact or codebase file yet. The goal is to build the node map
and validate the tree before loading anything else into context.

If the scope filter in `$ARGUMENTS` names a WBS node id, note it — Phase A still
reads and validates the full tree, but execution in Phase B is restricted to the
named subtree and its descendants.

### A2 — Parse the WBS tree

From `tasks.md` and `skeleton.md`, extract for every node:
- `Type` (Leaf / Summary / Root)
- `Parent`, `Children`
- `Owns` (list of files)
- `REQ`/`Structural` tags
- `After` (intra-tree dependency edges)
- `Done-when` (for leaves)
- `Review` and `Contributors` (for summary/root)

Also extract the `Cross-tree dependencies` list and the `file→owner` map from
`skeleton.md`.

Record the node map in working memory:

```
node_map:
  root:
    type: Root
    children: [W1, W2, …]
    review: "…"
  W1:
    type: Summary
    parent: root
    children: [W1.1, W1.2]
    owns: [path/to/convergent-file.ext]
    contributors: [W1.1, W1.2]
    review: "…"
  W1.1:
    type: Leaf
    parent: W1
    owns: [src/foo.py, src/bar.py]
    req: [REQ-001, REQ-003]
    after: []
    done_when: "…"
  …
```

### A3 — Validate the WBS invariants

Before dispatching anything, validate the tree against `../CONVENTIONS.md` invariants:
- Exactly one Root node
- Every non-root has exactly one Parent
- All node references resolve
- Declared `Type` matches structure (Root has no Parent; Leaf has no Children)
- `Owns` lists are pairwise-disjoint across all nodes
- Union of all `Owns` lists equals exactly the `skeleton.md` file set (one owner per
  file, every file owned)
- The `After` ∪ cross-tree edge graph is acyclic
- Every convergent-file owner is the nearest common ancestor of its declared
  `Contributors`
- Every summary/root `Review` is objectively checkable and references no `EVAL-NNN`

If any invariant is violated — a file with two owners, a cycle, a `Type`/structure
mismatch, an unowned skeleton file — **stop and surface it as a spec defect for
`/mdtechnical`**. Do not proceed.

### A4 — Build execution order

Apply the topological sort of (parent-after-children) ∪ (`After`) ∪ (cross-tree
edges). Group leaves into **waves**: Wave 1 is all leaves with no unresolved
dependencies; subsequent waves are unlocked as prior waves complete. Record the
waves in the node map.

If a scope filter was given, restrict execution waves to the named subtree and its
descendants. Read the remaining planning artefacts now (technical.md, constitution.md,
requirements.md, plan.md, evaluation.md) to give dispatched agents necessary context
about the overall design.

---

## Phase B — Leaf Agents (parallel waves)

Dispatch each wave of Leaf Agents in parallel. All agents in a wave run concurrently
— they are file-disjoint by the ownership invariant, so no locking is needed.

### What to pass each Leaf Agent

Pass each Leaf Agent only its minimal slice:
- Its WBS node entry (id, `Owns`, `REQ`/`Structural`, `After`, `Done-when`)
- The spec sections that describe its owned files (from `technical.md`,
  `requirements.md`, and `skeleton.md` — the relevant sections only, not the whole
  files)
- The hard scope rule: **read only the files in your `Owns` list and the spec
  sections passed to you; write only the files in your `Owns` list; never run git**

Do not pass the Leaf Agent the full planning artefact set or the codebase at large.

### What each Leaf Agent does

Each Leaf Agent:
1. Reads the existing state of each file in its `Owns` list (if present).
2. Implements or updates each owned file to satisfy its `Done-when` and the REQ
   requirements assigned to it.
3. Self-verifies: confirms each owned file satisfies `Done-when` and does not break
   callers visible from its own file set.
4. Checks for security issues within its owned files: no hardcoded secrets, no SQL
   string formatting, no command injection.
5. For any new configuration or secrets introduced: adds them to the env template
   file specified in `specs/technical.md` → Configuration and Secrets, with a comment
   and safe default.
6. For any new database changes: records the migration content and the naming
   convention from `specs/skeleton.md` → Conventions; the **sequence number is
   allocated by the owning convergent summary node** (`../CONVENTIONS.md` →
   Convergent files), not invented independently here.
7. Does not: add comments explaining what code does; add error handling for impossible
   conditions; introduce abstractions not required by the spec; add
   backwards-compatibility shims.

### Leaf Agent return contract

Each Leaf Agent returns a structured **Leaf Report** to the Main Agent:

```
node: <id>
status: DONE | FAIL
files_written: [list of paths actually written]
public_interfaces: [list of exported symbols/endpoints/schemas exposed]
deviations: [any departure from the spec, with reason]
cross_node_concerns: [anything this agent observed that affects a sibling or parent node]
```

A failed Leaf Agent returns `status: FAIL` with a description. Its parent Summary
Agent will receive a `FAIL` signal for that child and report `PARTIAL` upward. Nodes
depending on a failed leaf are **skipped** (not blocked) and reported as `SKIPPED`.

---

## Phase C — Summary Agents (bottom-up, after children resolve)

Dispatch each Summary Agent only after **every child and `After`-predecessor has
reported**. Summary Agents are dispatched individually as their children complete —
not all at once.

### What to pass each Summary Agent

Pass each Summary Agent:
- Its WBS node entry (id, `Owns`, `Contributors`, `Review`, children ids)
- The Leaf Reports from all its children
- The spec sections for its convergent files (from `technical.md` and `skeleton.md`)
- The hard scope rule: **read the files in your `Owns` list and your children's
  reported `files_written`; write only the files in your `Owns` list; never run git**

### What each Summary Agent does

Each Summary Agent, in order:

**(a) Write convergent files.** For each convergent file in its `Owns` list, assemble
it from the contributions reported by its children, per the protocol for that file
class (`../CONVENTIONS.md` → Convergent files):
- Registry/barrel: append entries from each child's `public_interfaces`
- Manifest/lockfile: declare the full dependency set from children's reports, then
  run **one resolver invocation** (e.g. `pip install -r requirements.txt` or
  `npm install`) to lock it
- Migration sequence: allocate sequence numbers and apply them to each child's
  migration content in dependency order

**(b) Run the Review integration check.** Execute the `Review` criterion for this
node against the assembled state of its owned and children's files. The Review must
be objectively checkable — it is a gate, not an inspection. If the Review fails,
report `FAIL`.

**(c) Never re-implement a child's work.** A Summary Agent reads children's output
to assemble convergent files; it does not rewrite the children's owned files.

### Summary Agent return contract

```
node: <id>
status: DONE | PARTIAL | FAIL
files_written: [list of paths actually written]
child_statuses: {child_id: DONE|FAIL|SKIPPED, …}
review_result: PASS | FAIL
deviations: […]
cross_node_concerns: […]
```

---

## Phase D — Root Agent

Dispatch the Root Agent after all Summary Agents report. Pass it the Summary Reports
from all direct children of Root plus the Root's `Review` criterion.

The Root Agent runs the final `Review` integration check against the assembled
codebase state. It returns:

```
node: root
status: DONE | PARTIAL | FAIL
review_result: PASS | FAIL
child_statuses: {…}
deviations: […]
```

The build is done when the Root Agent's `review_result` is `PASS`.

---

## Phase E — Parallel Verification

After Phase D, spawn one **Verification Agent** per node that was executed (all in
parallel). Pass each Verification Agent:
- Its node id, `Done-when` (or `Review` for summary/root), and the list of files it
  wrote (from its agent report)
- The hard scope rule: **read only the files listed; write nothing**

Each Verification Agent independently confirms:
- Every `Done-when` criterion for its node is satisfied by the actual file content.
- No owned file has a seam, stub, or unresolved placeholder.
- No owned file contains hardcoded secrets, SQL string formatting, or command
  injection.
- For summary/root: the `Review` criterion passes against the actual assembled state.

Each Verification Agent returns:

```
node: <id>
verified: PASS | FAIL
failed_criteria: [list of Done-when/Review criteria that did not pass]
```

The Main Agent collects all Verification Reports. Any node with `verified: FAIL` is
flagged as **unresolved** in the final report.

---

## Report

Node-by-node resolution: which nodes reached `DONE`, which `PARTIAL`, which `FAIL`,
which `SKIPPED`, and why for any non-`DONE` outcome. Files created or modified.
Requirements satisfied (by REQ id). Any requirements left unimplemented and why.
Verification pass summary: nodes confirmed `PASS`, nodes flagged `FAIL` with their
failed criteria.

The terminal handoff is the **Root Agent's** responsibility — emit the single prose
line `Next step: /mdevaluation` once (child/summary reports return status upward and
emit no chain directive).
