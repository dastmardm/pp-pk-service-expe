---
name: "mdcritique"
description: "Audit human-facing documentation under ./docs/ for internal consistency — contradictions, gaps, and unstated assumptions — then ask the user to fill gaps and resolve conflicts and reflect the resolved answers back into ./docs/. Reads and writes nothing outside ./docs/."
argument-hint: "Optional scope: file(s) under ./docs/; leave empty to audit the entire ./docs/ tree"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

If `$ARGUMENTS` names specific files, audit only those files (they must be under
`./docs/`). Otherwise audit the entire `./docs/` tree.

## The one hard rule — `./docs/` only, read and write

This skill operates **entirely within `./docs/`**. It is the consistency checker
for the human source of truth, and it never leaves that tree.

- **You may ONLY read files under `./docs/`.** Do not read anything outside it.
- **You may ONLY create, edit, or delete files under `./docs/`.** Every write
  target's path MUST be inside `./docs/`. Treat any write outside `./docs/` as
  forbidden.
- If a coherent `./docs/` tree would require knowing something only a human can
  supply, **ask the user** (Phase 5).

---

## Execution Model

This skill uses a **parallel multi-agent architecture**. Work fans out across
independent subagents and rolls back up through summary agents. Each agent
operates only on its assigned scope — it reads only the files it owns and writes
only to those files.

```
                      ┌──────────────────────┐
                      │    Main Agent (you)  │
                      │  Phase A: map tree   │
                      │  Phase E: ask user   │
                      │  Phase F: dispatch   │
                      └──────────┬───────────┘
                                 │ dispatches
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
     ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
     │ Node Agent A │   │ Node Agent B │   │ Node Agent C │  (one per top-level
     │  subtree /a/ │   │  subtree /b/ │   │  subtree /c/ │   node, run in parallel)
     └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
            │                  │                  │
     ┌──────▼───────┐   ┌──────▼───────┐   ┌──────▼───────┐
     │ Sub-Agent A1 │   │ Sub-Agent B1 │   │ Sub-Agent C1 │  (one per file/subnode,
     │ Sub-Agent A2 │   │ Sub-Agent B2 │   │ Sub-Agent C2 │   run in parallel within
     │   …          │   │   …          │   │   …          │   their node agent)
     └──────────────┘   └──────────────┘   └──────────────┘
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 ▼
                      ┌──────────────────────┐
                      │    Main Agent (you)  │
                      │  Phase D: aggregate  │
                      │  Phase E: ask user   │
                      │  Phase F: dispatch   │
                      │  Phase G: verify     │
                      └──────────────────────┘
```

---

## Phase A — Map the Tree (Main Agent only)

You are the Main Agent. Before spawning anything, map the scope.

1. Run `find ./docs -type f -name "*.md" | sort` (or the equivalent for the
   given `$ARGUMENTS` scope) to enumerate every in-scope file.
2. Group files into **nodes** — one node per top-level subfolder directly under
   `./docs/`. Files at the root of `./docs/` itself form a special `_root` node.
3. For each node, list its files and identify any sub-nodes (second-level
   subfolders within it).
4. Read **only** `./docs/index.md` (if present) to understand the declared
   structure and intent of each node. Do not read any other file yet.

Output of Phase A (kept in your working memory — not written anywhere):

```
node_map:
  _root:   [file1.md, file2.md, …]
  service-a: [service-a/overview.md, service-a/ops.md, …]
    sub-nodes:
      service-a/sub1: [service-a/sub1/detail.md, …]
  service-b: [service-b/README.md, …]
  …
```

---

## Phase B — Parallel Node Audit (Node Agents, one per node)

Spawn one **Node Agent** per node, all in parallel. Pass each Node Agent:
- Its node name and the exact list of files it owns (from the node_map).
- The declared purpose of its node (from `./docs/index.md` if available).
- The hard rule: read and write only its own files.

Each Node Agent independently executes **Phases B1–B4** below for its subtree.

### Phase B1 — Collect

Read every file assigned to this node. For each file record:
- Its role and what it claims about the system (behaviour, names, paths, values,
  constraints, operations).
- Any cross-references to files **outside** this node (flag these — do not
  follow them, just note the target path and the claim that links to it).

Do not read any file outside your assigned list.

### Phase B2 — Structural Relocation

For every piece of information collected, determine: *Is this in the right file,
inside the right subfolder, for the service/sub-service it describes?*

If content is misplaced **within your node**:
- Move it to the correct file within your node.
- Remove the copy from the wrong location.
- Update every cross-reference and index entry **within your node** that pointed
  to the old location.

If content appears to belong to a **different node**, do not move it yourself —
record it as a cross-node relocation finding and leave the content in place for
the Main Agent to arbitrate.

### Phase B3 — Consistency Integration

For every block of content moved in Phase B2:
- Rewrite or reflow it so it reads as if it was always part of the destination
  file: correct heading levels, consistent noun usage, coherent narrative arc.
- Merge any overlap with content already in the destination file.
- Remove forward/backward references that pointed to the former location.

### Phase B4 — Detect Inconsistencies

Check every axis below. Record each problem as a **finding** with severity
(`BLOCKER` / `MAJOR` / `MINOR` / `QUESTION`) and the file path(s) involved.

#### B4a. Internal contradictions
- Do two files in this node (or two passages in one file) state conflicting
  facts — different behaviours, names, paths, values, or constraints?
- Does a later section contradict an earlier one?

#### B4b. Index & cross-reference integrity
- Does `./docs/index.md` (if visible in your file list) accurately describe
  your node's files?
- Do cross-references within your node resolve to real files/sections?
- Is terminology used consistently across your node's files?

#### B4c. Gaps & missing information
- Does your node describe a capability but omit how it is used, configured, or
  operated?
- Is a term, contract, or path template referenced but never defined within your
  node?
- Is there a described behaviour whose conditions or limits are never stated?

#### B4d. Unstated assumptions
- Does any document make an unjustified choice or claim?
- Is a statement only true under an unstated condition?

#### B4e. Open items that must not exist
- Does any file in your node contain `## Open Questions`, TODO, TBD, "to be
  confirmed", a watermark ("reverse-engineered / generated from source"), or any
  placeholder? Each is a `QUESTION` finding.

#### B4f. No migration or historical framing
- Flag as `BLOCKER` any passage using before/after, previously/now, "was"/"used
  to be", "will be", "going forward", "once complete", "legacy", "old approach",
  or similar temporal framing that implies a past or future state rather than the
  current settled design.

### Phase B4 Sub-Agent Option (for large nodes)

If your node has more than four files, spawn one **Sub-Agent** per file (all in
parallel). Pass each Sub-Agent:
- The single file it owns.
- The node's declared purpose (from `./docs/index.md` or the node-level
  description passed to you).
- Its scope: check only its own file for B4a–B4f findings; do not read other
  files.

Each Sub-Agent returns a list of findings for its file. The Node Agent collects
all Sub-Agent findings, deduplicates cross-file contradictions, and assembles a
single node-level finding list.

### Node Agent Output

Return to the Main Agent a structured **Node Report**:

```
node: <node-name>
files_audited: [list]
relocations_within_node: [list of moves made, with from/to paths]
cross_node_relocation_candidates: [list of {content_summary, from_file, suggested_target_node}]
findings:
  - id: <NODE>-<N>
    severity: BLOCKER|MAJOR|MINOR|QUESTION
    file: <path>
    description: <what is wrong>
    resolution_hint: <what would fix it, if obvious>
files_edited: [list of files this agent actually wrote to]
```

---

## Phase C — Cross-Node Relocation (Main Agent)

After all Node Agents report back:

1. Collect all `cross_node_relocation_candidates` from every Node Report.
2. For each candidate, determine which node it belongs in, then instruct the
   **source Node Agent** and **target Node Agent** (by spawning a pair of
   targeted micro-agents if needed) to execute the move: remove from source,
   add to target, update index.
3. After moves complete, trigger a re-integration pass on the affected files
   (spawn a targeted micro-agent for each edited destination file to run
   Phase B3 on just that file).

---

## Phase D — Aggregate Findings (Main Agent)

Merge all Node Reports into a single **Master Finding List**:
- Assign global IDs (`FIND-001`, `FIND-002`, …).
- Deduplicate findings that appear in multiple nodes but describe the same
  underlying problem.
- Sort by severity: `BLOCKER` first, then `MAJOR`, `MINOR`, `QUESTION`.
- Flag any finding that can be resolved by the docs alone (no user input
  needed) as `auto-resolvable` — these will be handled in Phase F without
  asking the user.

---

## Phase E — Ask the User (Main Agent)

Present the Master Finding List to the user, grouped by severity.

For every finding that is **not** auto-resolvable:
- State exactly what is missing or which two statements conflict.
- Name the `./docs/` file(s) that will change once it is answered.
- Offer concrete options where possible; accept free-form answers otherwise.

Rules:
- Do not ask about things that can be resolved by reading the docs more
  carefully — mark those auto-resolvable instead.
- Do not bundle multiple distinct questions into one.
- Wait for the user's answers before proceeding.

---

## Phase F — Reflect Resolutions (Parallel Dispatch)

Once the user has answered, group all resolutions (user-supplied answers +
auto-resolvable fixes) by the node they affect. Spawn one **Resolution Agent**
per affected node, all in parallel. Pass each Resolution Agent:
- The node's file list.
- The findings that target this node and their confirmed answers.

Each Resolution Agent:
- Applies each confirmed answer as settled fact in the right file(s).
- Resolves every contradiction so the node's files now agree; removes superseded
  text rather than annotating it as outdated.
- Deletes every `## Open Questions` / TODO / TBD / placeholder / watermark,
  replacing it with the resolved fact or removing the uncertain claim entirely.
- Rewrites all temporal/migration framing to present tense, settled fact only.
- Updates `./docs/index.md` if the index is affected (coordinate with the other
  Resolution Agents via the Main Agent if multiple nodes touch the index).
- Every write target's path must be inside `./docs/`.

---

## Phase G — Verification (Main Agent + parallel spot-checks)

Spawn one **Verification Agent** per node that was edited in Phase F (in
parallel). Pass each Verification Agent:
- The node's file list.
- The list of findings that targeted this node.

Each Verification Agent confirms:
- Every finding for its node is closed (contradiction gone, gap filled,
  placeholder removed).
- All content moved in Phase B2/C has been fully integrated — no seams,
  duplicates, or dangling references remain.
- `./docs/index.md` still lists every file accurately and all cross-references
  within the node resolve.
- No write touched anything outside `./docs/`.

Verification Agents return pass/fail per finding. The Main Agent collects
results; any finding that is still open is flagged as **unresolved** in the
final report.

---

## Report (Main Agent — in your response to the user, not as a file)

Summarise:
- Findings by severity (counts): total found, auto-resolved, user-resolved,
  still open.
- Findings closed in this session (ID + which `./docs/` file changed).
- Questions asked and how the answers were reflected into `./docs/`.
- Cross-node relocations performed (from → to).
- Findings still open (ID + what the user must decide), if any.
