# Pipeline Conventions

The single, authoritative definition of the conventions shared across the
spec-driven skills in this directory. Individual `SKILL.md` files keep their own
concise, point-of-use reminders, but **this file is the source of truth** — when
a convention is ambiguous in a skill, this file wins. Skills that depend on a
convention cite it as `../CONVENTIONS.md`.

---

## `EXECUTE_COMMAND` — skill-to-skill dispatch

Some skills chain to the next skill automatically. They do this by emitting, as
the **last line of their output**, a directive of the form:

```
EXECUTE_COMMAND: <skill-name> [arguments]
```

The harness intercepts this literal line and invokes `/<skill-name>` with the
given arguments, as if the user had typed it. It is **not** narrative — write it
verbatim, on its own line, with no surrounding prose, so it is recognised.

Current uses:

| Emitting skill | Directive | Effect |
|----------------|-----------|--------|
| `fix` | `EXECUTE_COMMAND: evaluation` | re-audits after repairs (the only built-in loop) |
| `fix` | `EXECUTE_COMMAND: docs <change>` | reflects the applied repairs into the docs — emitted as the **last line** only when re-evaluation is *not* warranted (no competing directive); when re-evaluation runs, the docs hand-off happens after that loop converges so the docs describe the final fixed state |
| `critique` | `EXECUTE_COMMAND: fix specs/critique/report{NN}.md` | hands code-level findings to `/fix` |
| `modify` | `EXECUTE_COMMAND: docs <change>` | reflects an applied code change into the docs — emitted **only after** the user confirms the change (the confirmation is a human checkpoint; the directive fires on the turn after it passes) |

Skills that hand off to a **human checkpoint** (e.g. `/technical` after a docs
clarification, `/evaluation` before `/fix`) use prose (`Next step: …`) instead,
deliberately, so the chain pauses for review.

---

## Report numbering

Skills that emit numbered reports (`evaluation` → `specs/evaluation/report{NN}.md`,
`critique` → `specs/critique/report{NN}.md`) number them identically:

- List existing files matching `report*.md` in the target directory.
- **Next number = highest existing index + 1** (not a count — so deleting an
  interim report never causes a collision/overwrite).
- **Zero-padded to 2 digits**, starting at `01` (the first report is `report01.md`).
- `mkdir -p <dir>` if the directory does not exist.

---

## Verdict & severity vocabularies

**Evaluation verdicts** (one per `EVAL-NNN` criterion, assigned by `/evaluation`):

| Verdict | Meaning |
|---------|---------|
| `PASS` | the named evidence is present and satisfies the criterion |
| `PARTIAL` | partially satisfied; what is missing is described |
| `FAIL` | the criterion is not met |
| `N/A` | the criterion's Out-of-Scope condition applies |
| `BLOCKED` | the **criterion itself** is defective (ambiguous/unverifiable/contradictory) — the fix is in `specs/evaluation.md`, not the code. This is an evaluation-side escape hatch, not a verdict the criteria schema declares. |

**Finding severities** (`evaluation` and `critique` both order fixes by these):
`BLOCKER` → `MAJOR` → `MINOR`. `critique` adds `QUESTION` for findings that
cannot be resolved without information from the user.

---

## The `## Sources` lineage contract

Every produced spec opens with a `## Sources` section, and it must come **first**.
It names exactly what the artefact was derived from (paths, and for folders the
concrete files read), so any artefact traces back to the human source in `docs/`.
A producer lists only true upstream sources; it never lists its own output or
`$ARGUMENTS` free-text as a source.

---

## Artefact path resolution

Each skill states a **default** artefact path (e.g. `specs/product.md`,
`specs/technical.md`, `specs/evaluation.md`). If the repository already uses a
different name for that artefact (e.g. `specs/product_specification.md`), read /
overwrite **that existing file** rather than creating a duplicate. Pass the actual
path as the skill's argument when the default does not match.

---

## Missing-input run order

Each skill stops with an error if its input artefact is missing and names the
earlier skill to run first. The canonical order:

| Skill | Required input | Run first |
|-------|----------------|-----------|
| `technical` | `./docs/` (the doc tree) | — (human edits `docs/`) |
| `implement` | `specs/technical.md` (+ planning files) | `/technical` |
| `evaluation` | `specs/evaluation.md` | `/technical` |
| `fix` | an evaluation or critique report | `/evaluation` (or `/critique`) |
| `critique` | `specs/` artefacts | — (audits whatever exists) |
| `git` | `specs/git.md` | `/technical` |
| `docs` | `./docs/` | — |
| `research` | data source(s) + the project | — (writes its insight under `./docs/`) |
| `flow` | a DAG-of-skills markdown file | — |

---

## `docs/` authority — ratified intent vs derived evidence

`docs/` holds two kinds of content, and consumers must not treat them as equal:

- **Ratified intent** — human-authored documentation (via `/docs`), anywhere under
  `docs/`. This is the source of truth the whole chain projects from.
- **Derived evidence** — machine-produced analysis written by `/research`, confined to
  **`docs/research/**`** and marked as derived. It *informs* design but does not by itself
  *ratify* intent.

When the two conflict, **human-authored intent wins.** `/technical` and `/critique` treat
`docs/research/**` as evidence, not as settled product decisions: a contradiction between
derived evidence and human-authored docs is surfaced (an `## Open Questions` entry /
`QUESTION` finding) for a human to reconcile in `docs/`, never silently resolved in the
derived file's favour.

---

## Interactive vs autonomous skills

Some skills are designed to **converse with the human** mid-run; others run to
completion **unattended**. The distinction matters because `/flow` — and any unattended
or parallel invocation — cannot relay a question to the user from inside a running skill.

- **Autonomous** (never need the human to proceed once started): `implement`,
  `evaluation`, `fix`, `git`, `flow`, `docs`, and `research`. They may ask **once, up
  front** if a required input is genuinely missing, but they do not block mid-run.
- **Interactive** (designed to clarify with the human as they work): `technical` (the
  clarify-in-docs loop) and `critique` (its `QUESTION` findings).

**Autonomous-mode contract.** When an interactive skill is run unattended — under
`/flow`, inside a dispatched subagent, or when the user says "don't stop to ask" — it
must **not block**. It records each unresolved ambiguity as a structured deferral
(`technical` → `specs/product.md` `## Open Questions`; `critique` → `QUESTION` findings),
continues with everything that *is* unambiguous, and surfaces the full deferral list in
its final report. It never invents an answer and bakes it into an artefact. (`technical`
already does this when the human declines to record a clarification; the contract
generalises that behaviour to every unattended run.)

**Write scopes (for `/flow` parallel-eligibility).** Two branches are write-disjoint —
hence safe to run concurrently — only if their write scopes below do not overlap. A
shared **index/registry file** (e.g. the `docs/` index) is a *convergent* file (see Work
Breakdown Structure → Convergent files): when parallel branches each need to register an
entry, that single write is **serialised** as a join step, not raced.

| Skill | Writes |
|-------|--------|
| `technical` | `specs/**` and `.claude/settings.json` (and `./docs/` during its interactive clarify loop) |
| `research` | `docs/research/**` only (plus its one entry in the `docs/` index) |
| `docs` | `docs/**` |
| `evaluation` | `specs/evaluation/report*.md` |
| `critique` | `specs/critique/report*.md` (and may edit `specs/**` during its resolution phase) |
| `implement` / `fix` | source code, the env template, migrations (never git) |
| `git` | git refs / index only — no working-tree file writes |
| `flow` | nothing of its own (it dispatches other skills) |

---

## Work Breakdown Structure (WBS) — decomposition & parallel-execution model

The project's work is decomposed into a **hierarchical tree** (a Work Breakdown
Structure). `/technical` *produces* the tree (in `specs/tasks.md`, with the file-owner
map in `specs/skeleton.md`); `/implement` *executes* it. This section is the single
source of truth for the model; both skills cite it.

**The tree is an authoritative decomposition + ordering contract, not a promise about
runtime concurrency.** Its preferred realization is parallel — one subagent per node,
leaves running concurrently, summary nodes joining their children — but the same tree
walked **sequentially in bottom-up (post-order) order produces an identical result**.
Correctness never depends on concurrency, and no part of the model assumes a worker can
spawn further workers (nested spawning is not guaranteed). `/implement` chooses the
realization; the contract below holds either way.

### Node kinds

Every node declares its kind explicitly — it is **never inferred** from shape.

- **Leaf** — one logical unit of implementation. It **owns ≥ 1 file** (all of which
  must be written *together* by one worker — a unit that cannot be split across workers,
  e.g. a base class plus its companion). It maps to **≥ 1 `REQ-NNN`**, *or* is tagged
  `Structural: <reason>` for files that trace to no functional requirement (package
  markers, fixtures — mirrors the `Skeleton/Structure` category in `evaluation.md`).
- **Summary** — an intermediate node. It **blocks until every child resolves**, then, in
  this order: (1) writes any **convergent file(s)** it owns from its children's reported
  contributions; (2) runs its **`Review`** (an integration check); (3) reports a
  structured status to its parent. A summary node *may author code* (its convergent
  files) — a deliberate extension of "summary = review only", and the only reason it can
  is the file-ownership invariant below.
- **Root** — the whole project; the **last** node to resolve. It is a summary node
  (same blocking semantics). For a genuinely single-task project the root **may instead
  be a leaf** (no children, owns files directly); its `Done-when` then doubles as the
  project's final review.

### Node identity

IDs are **stable opaque keys**, assigned hierarchically at creation (`W1`, `W1.1`,
`W1.1.2`, …) and **never renumbered** when the tree is reshaped — a node keeps its ID
even if its position changes. Every reference (`Parent`, `Children`, `After`,
`Contributors`, cross-tree edges) names a node by this key. The dotted form reflects the
*initial* assignment only; the explicit `Parent`/`Children` fields are authoritative for
structure (the dotted path is a redundant checksum, see invariants).

### Node fields

Each node carries: `Type` (root|summary|leaf), `Parent`, `Children`, `Owns` (file
list), `REQ` (or `Structural:`), `After`, `Done-when`, and for summary/root a `Review`
field plus, per convergent file it owns, a `Contributors` list. The **exact page layout**
of these fields is fixed in `technical/reference/output-formats.md` → File 6; this
section defines their meaning.

### File-ownership invariant (the sole parallel-safety guarantee)

**Every file is owned by exactly one WBS node, and the union of all `Owns` lists equals
exactly the file set in `specs/skeleton.md`** (disjoint *and* complete — no file owned
twice, no skeleton file left unowned). `skeleton.md`'s `Owner (WBS node)` column is the
authoritative file→owner map; each node's `Owns` list must agree with it. Because no two
nodes ever write the same file, any set of concurrently-active nodes is automatically
file-disjoint — so parallel execution needs **no locking and no worktree isolation**. A
would-be shared write anywhere else is a **spec defect**: the fix is to give the file a
single owner (push it up to a common ancestor), never to add a lock or a worktree.

### Convergent files

Where many nodes must each contribute to one file (a registry/barrel, a package manifest
or lockfile, a migration sequence), that file is owned by the **nearest common ancestor**
of its contributors, written during that summary node's aggregate step. The owning node
lists `Contributors: <child IDs>` so the NCA relationship is verifiable from the tree
alone. Each class has a defined protocol:

- **Registry / barrel / `__init__`** — append-only entries collected from child reports
  (commutative; safe to assemble in any order).
- **Manifest / lockfile** — the owner declares the *dependency set* from child reports,
  then runs **one** resolver invocation (resolution is not commutative — it is a single
  serialized step, and it is real implementation work, so the owning summary node is
  permitted to run the package-manager/resolver command).
- **Migration / ordered sequence** — the owning node **allocates all sequence numbers up
  front** and hands each contributing leaf its assigned number as an input (numbers are
  not child-reported, to avoid collisions).

A convergent file whose contributors span subtrees (NCA = root) is a **decomposition
smell** — prefer reshaping the tree so contributors share a lower ancestor.

### Dependencies & execution order

- The tree itself encodes **parent-after-children**.
- **`After: <id,…>`** serialises siblings within one parent (e.g. a dependent waits on
  shared scaffolding). It encodes a producer/consumer **interface** dependency, so the
  prerequisite's `Done-when` must name the interface it exposes. Referenced IDs must
  exist and share the same parent.
- A dependency whose endpoints live in **different subtrees** is forbidden inline; it
  goes in the top-level **`Cross-tree dependencies`** list naming both endpoint IDs and
  the exposed interface (discouraged — reshape the tree to avoid it where possible).
- The **effective execution order is the topological sort** of (parent-after-children) ∪
  (`After`) ∪ (cross-tree edges). This combined graph **must be acyclic** (the tree alone
  is trivially acyclic; the real check is over the full edge set). Sibling leaves with no
  unmet dependency form a wave that may run concurrently.

### Fork-join semantics

A node becomes runnable once all its dependencies (children + `After` + cross-tree
predecessors) have resolved. Leaves in a wave run concurrently; a summary node runs only
after all its children resolve, then aggregates → reviews → reports; the root resolves
last. **Failure does not hang the join**: a node that fails reports a `FAIL` status
upward, its parent reports a partial result naming the failed subtree, and nodes that
depend on a failed prerequisite are **skipped** (also reported), never blocked
indefinitely.

### Worker discipline

Workers **only write the files they own**; they **never run git**. The working-tree index
is shared single-writer state, so all staging/committing is left to the separate `/git`
stage after the tree resolves. Only the **root** node's final report emits the prose
chain handoff (`Next step: /evaluation`); child and summary reports return structured
status upward and emit no chain directive.

### WHAT / HOW boundary

A summary node's `Review` is a **self-contained, objectively-checkable integration
assertion phrased in `tasks.md`'s own terms** (e.g. "every child-reported interface
resolves; the convergent file lists every contribution; the subtree imports/builds/tests
clean"). It **must not reference `EVAL-NNN`**: `specs/evaluation.md` remains the sole
owner of *what* gets checked, asserted only by `/evaluation`, and lineage stays
one-directional (`evaluation.md` may cite `tasks.md`, never the reverse). A green subtree
is an early-warning signal, not a substitute for the final `/evaluation` pass.

### Quality invariants (machine-checkable over the parsed tree)

1. Exactly one node has `Type: root`, and it has no `Parent`.
2. Every non-root node has exactly one `Parent` (it is a tree, not a forest).
3. Every `Parent`/`Children`/`After`/`Contributors`/cross-tree reference resolves to an
   existing node ID, and each node's dotted ID is consistent with its declared `Parent`.
4. `Type` agrees with structure: a `leaf` has no children and (≥ 1 `REQ` **or**
   `Structural:`); a `summary` has ≥ 1 child and a non-empty `Review`; `root` per the
   single-task carve-out above.
5. A summary node with **exactly one child** must own ≥ 1 convergent file *or* carry a
   `Review` asserting something beyond that child's `Done-when` — otherwise collapse it
   into the child.
6. `Owns` lists are pairwise disjoint **and** their union equals exactly the
   `skeleton.md` file set (globs expanded against the skeleton tree).
7. The dependency graph (`After` ∪ cross-tree edges) is acyclic.
8. Every owning node of a convergent file is the nearest common ancestor of its declared
   `Contributors`.
