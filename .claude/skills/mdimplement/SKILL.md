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
technical → implement → evaluation → fix
```

Produce or update the codebase so it satisfies the technical specification, by **executing
the Work Breakdown Structure** in `specs/tasks.md`. The WBS is a hierarchical tree: leaf
nodes are atomic, file-disjoint units (the unit of parallel work); summary nodes block
until their children resolve, then aggregate, review, and report upward; the root resolves
last, bottom-up. The full model — node kinds, the file-ownership invariant, convergent-file
protocols, dependency edges, fork-join and failure semantics — is defined in
`../CONVENTIONS.md` → Work Breakdown Structure. Read it; it governs everything below.

### Steps

1. Read the technical specification from the path in $ARGUMENTS, or the default
   `specs/technical.md` (if the repo uses a different name for that artefact, e.g.
   `specs/technical_specification.md`, read that instead — see `../CONVENTIONS.md` → Artefact path resolution).
   Also read the other planning artefacts `/mdtechnical` produced for context:
   `constitution.md`, `requirements.md`, `plan.md`, `tasks.md`, `skeleton.md`,
   `evaluation.md`. (You do not need `git.md` — that is `/mdgit`'s input.)
   Stop with an error if the technical spec does not exist — run `/mdtechnical` first.

2. Explore the existing codebase to understand current structure before making any changes.

3. **Parse the WBS tree** from `tasks.md` and the file→owner map from `skeleton.md`: for
   every node, its `Type`, `Parent`, `Children`, `Owns`, `REQ`/`Structural`, `After`,
   `Done-when`, and (for summary/root) `Review` and `Contributors`; plus the `Cross-tree
   dependencies` list. **Validate the tree against the `../CONVENTIONS.md` invariants**
   (one root; one parent per node; references resolve; `Type` matches structure; `Owns`
   pairwise-disjoint and their union equals the skeleton file set; the `After` ∪ cross-tree
   graph is acyclic). If the tree violates an invariant — a file with two owners, a cycle,
   a `Type`/structure mismatch, an unowned skeleton file — **stop and surface it as a spec
   defect for `/mdtechnical`**; do not race, lock, guess an owner, or reach for a worktree.

4. Build the execution order: the topological sort of (parent-after-children) ∪ (`After`)
   ∪ (cross-tree edges). If a scope filter named a WBS node id, restrict execution to that
   node and its descendants (still reading the whole tree for context); a free-text filter
   restricts to matching leaves.

5. **Execute the tree bottom-up, fork-join** (`../CONVENTIONS.md` → Fork-join semantics):
   - **Leaf node** → dispatch a dedicated subagent that writes **only** the files in the
     node's `Owns`, to its `Done-when`, then self-verifies and returns a structured report
     (files written, public interfaces exposed, any deviation). Leaf nodes whose
     dependencies are all resolved form a wave that runs **concurrently** — they are
     file-disjoint by the ownership invariant, so no locking is needed.
   - **Summary node** → runs only after every child and `After`-predecessor has resolved.
     It then, in order: (a) writes any convergent file(s) it `Owns` from its children's
     reported contributions, per the protocol for that file class (registry/barrel =
     append entries; manifest/lockfile = declare the dependency set then run one resolver
     invocation; migration sequence = allocate the numbers and hand each to its
     contributor); (b) runs its `Review` integration check; (c) returns an aggregated
     status upward. A summary node never re-implements a child's work.
   - **Root** resolves last; the build is done when its review passes.
   - **Failure never hangs the join**: a node that fails reports `FAIL` upward, its parent
     reports a partial result naming the failed subtree, and nodes depending on a failed
     prerequisite are **skipped** (and reported) — not blocked.
   - **Mechanism**: author a Workflow that mirrors the tree (dispatch each ready wave with
     `parallel()`, join, then run summary/root nodes), or dispatch sibling leaf subagents
     directly with parallel Agent calls in one message and join on them. **Do not assume a
     worker can spawn sub-workers** — you (the main loop) own the fan-out. If no parallel
     substrate is usable, walk the tree **sequentially in bottom-up (post-order) order**;
     the result is identical. Workers **only write the files they own and never run git** —
     the index is shared single-writer state; staging is `/mdgit`'s job.

6. Within each node's work — leaf or summary:
   - After each change, verify it satisfies the node's `Done-when`/`Review` and does not break callers.
   - Check for security issues: no hardcoded secrets, no SQL string formatting, no command injection.

7. For any new configuration or secrets introduced:
   - Add them to the env template file specified in `specs/technical.md` → Configuration and Secrets, with a comment and safe default

8. For any new database changes:
   - Write an idempotent migration file following the naming convention defined in
     `specs/skeleton.md` → Conventions. Migration **sequence numbers are allocated by the
     owning convergent node** (`../CONVENTIONS.md` → Convergent files), not invented
     independently per leaf.

9. Do not:
   - Add comments explaining what code does
   - Add error handling for impossible conditions
   - Introduce abstractions not required by the spec
   - Add backwards-compatibility shims

10. Report: node-by-node resolution (which nodes resolved, which failed or were skipped and
    why), files created or modified, requirements satisfied, any requirements left
    unimplemented and why. The terminal handoff is the **root** node's responsibility — emit
    the single prose line `Next step: /mdevaluation` once (child/summary reports return status
    upward and emit no chain directive).
