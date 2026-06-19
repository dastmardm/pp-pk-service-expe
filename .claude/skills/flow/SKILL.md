---
name: "flow"
description: "Execute a DAG of skills described in a markdown file. Takes a single argument — a path to a markdown file — and runs the skills it specifies in the order (and with the dependencies) the file lays out. Use when the user types /flow <file.md> to drive a chained, multi-skill workflow declared as a DAG."
argument-hint: "Path to a markdown file describing the DAG (e.g. dag.md)"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` is a **single path to a markdown file** describing a DAG of skills to
run. Nothing else is passed. If it is empty, or names a file that does not exist or
is not readable, stop and tell the user exactly what is missing — do not guess a
default file.

## Outline

You are the **flow** step — a DAG executor. You do **not** decide what work to do;
the markdown file does. Your only job is to read that file, understand the graph of
skills it describes, and invoke each skill in a valid execution order. The file is
the **WHAT**; you are the **HOW**.

```
           /flow dag.md
                 │
                 ▼
        ┌─────────────────┐
        │  read dag.md    │  ← parse nodes (skills) + edges (dependencies)
        └────────┬────────┘
                 ▼
        ┌─────────────────┐
        │ topo-order DAG  │  ← resolve a valid order; detect cycles
        └────────┬────────┘
                 ▼
        ┌─────────────────┐
        │ run each skill  │  ← Skill tool; safe independent branches concurrently
        └────────┬────────┘
                 ▼
        ┌─────────────────┐
        │ report results  │  ← what ran, in what order, outcomes
        └─────────────────┘
```

> **Naming note.** `flow` is distinct from the built-in `/run` (which launches the
> app). `/flow <file.md>` means *execute the DAG of skills described in that file*.

---

### Phase 1 — Read and parse the DAG file

1. Read the file named by `$ARGUMENTS` in full. If it is missing/empty/unreadable,
   stop with a clear error naming the expected argument (a path to a markdown file).
2. Extract from it:
   - **Nodes** — the skills to run. A node names a skill (e.g. `critique`,
     `technical`, `implement`) and may carry **arguments** to pass to that skill.
   - **Edges / dependencies** — which skills must complete before which others.
     Honour whatever the file uses to express order: an explicit dependency list,
     a numbered/ordered sequence, an arrow notation (`a -> b`), a Mermaid graph, a
     nested checklist, or plain prose ("run X after Y"). Read it the way it is
     written; do not impose a format on the author.
3. Resolve each node to a real, available skill. If a node names a skill that is
   **not** in the available-skills list, stop and report it — never invent or guess
   a skill name.

### Phase 2 — Resolve an execution order

- Compute a **topological order** of the nodes from the edges: every skill runs
  only after all of its declared dependencies have completed.
- Where the DAG allows independent branches (no dependency between them), they are
  candidates to run **concurrently** — identify these independent sets; Phase 3
  decides which are *safe* to actually parallelise.
- **Detect cycles.** If the dependencies form a cycle (no valid order exists), stop
  and report the cycle — do not run a partial, ambiguous order. (The `fix`↔`evaluation`
  loop is a deliberate cycle handled *inside* those skills via `EXECUTE_COMMAND`, not a
  DAG edge — do not encode it as one.)
- If the file is ambiguous about ordering in a way you cannot resolve from its
  content, ask the user rather than guessing.

### Phase 3 — Execute

`/flow` runs **unattended**, so every skill it invokes runs in **autonomous mode**
(`../CONVENTIONS.md` → Interactive vs autonomous skills): an interactive skill
(`technical`, `critique`) must not block asking the user — it defers each unresolved
ambiguity to its structured output (`## Open Questions` / `QUESTION` findings) and
continues. Collect every deferral and surface it in the Phase 4 report.

Run the DAG in dependency order, **fanning out independent branches that are safe to
run together**:

1. A set of nodes is **parallel-eligible** when they have no dependency between them
   **and** are safe to run concurrently — i.e. every skill in the set is **autonomous**
   **and** their **write scopes are disjoint**. Determine both mechanically from
   `../CONVENTIONS.md` → Interactive vs autonomous skills (the autonomous list and the
   skill→write-scope table); it is the same file-disjointness reasoning as
   `../CONVENTIONS.md` → Work Breakdown Structure. For example, two `research` runs over
   different sources are eligible — each writes a different `docs/research/` file — but
   their shared touch on the `docs/` **index is a convergent write**, so that one
   registration is **serialised** as a join step, not raced (WBS → Convergent files).
   Skills with overlapping scopes (e.g. `technical` and `evaluation`/`critique`, which
   all write under `specs/`) are **not** eligible. Dispatch a parallel-eligible set
   **concurrently** — you own the fan-out (author a Workflow, or dispatch parallel
   subagents; do **not** assume a worker can spawn further workers). If concurrent
   execution is not feasible, run the set sequentially — the result is identical.
   Anything **interactive**, or whose writes **overlap** another node's, runs
   **sequentially**.
2. Invoke each node with the **Skill tool** (or, for a parallel branch, inside its
   dispatched worker), passing the arguments the DAG file specifies for that node
   (empty if none). A skill never starts before every skill it depends on has finished.
3. If a skill **emits an `EXECUTE_COMMAND` directive** (see `../CONVENTIONS.md`),
   that chained invocation is part of that skill's own run — let it complete, then
   continue with the DAG. Do not double-run a skill the DAG already scheduled and a
   predecessor also dispatched; treat it as already satisfied.
4. **On failure of a skill:** stop the dependent branch. Report what failed and
   why. Continue only with branches that do **not** depend on the failed node,
   unless the DAG file says otherwise (e.g. "stop on first failure"). When unsure,
   stop and ask.

### Phase 4 — Report

Summarise:
- The skills that ran, in the order they ran.
- Any independent branches and how they were ordered (run **concurrently** or sequentially, and why).
- Each skill's outcome (succeeded / failed / skipped-because-dependency-failed).
- The **consolidated list of questions / Open Questions** the interactive skills deferred
  (they could not ask mid-run) — so the human can resolve them in `docs/` and re-run.
- Anything the DAG file asked for that could not be done, and why.

---

### Rules

- **The file is authoritative.** Do not add, drop, or reorder skills beyond what the
  DAG and its dependencies require. You execute the graph; you do not redesign it.
- **One argument only.** `/flow` takes exactly one thing: the path to the markdown
  file. Per-skill arguments come from *inside* that file, not from the `/flow` call.
- **Never invent skills.** Only invoke skills that appear in the available-skills
  list. An unknown node name is an error to report, not a name to guess.
- **Respect dependencies strictly.** A skill never starts before every skill it
  depends on has finished.
- **Parallelise only when safe.** Independent branches run concurrently only when every
  skill in them is autonomous and their write targets are disjoint; anything interactive
  or write-overlapping runs sequentially. Concurrency is an optimisation — the sequential
  order always produces the same result.
- **Run unattended; defer, don't block.** Skills run in autonomous mode; interactive
  skills defer clarifications to their structured outputs and `/flow` surfaces them in the
  final report (`../CONVENTIONS.md` → Interactive vs autonomous skills).
