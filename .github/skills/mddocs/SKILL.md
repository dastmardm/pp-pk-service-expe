---
name: "mddocs"
description: "Author or edit a requested change to human-facing documentation under ./docs/ only; touches nothing outside ./docs/. Use when the user wants to change project docs directly — not to propagate changes into specs or code (use /mdtechnical → /mdimplement for that)."
argument-hint: "Description of the documentation change, e.g. `document Vault bootstrap`"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` is a free-text description of a change to the project's human-facing
documentation. It is the request — what the docs should now say, or what new
capability/behaviour they should describe.

## The one hard rule — only `./docs/` may be written

This skill exists to edit the human-facing documentation and **nothing else**.

- **The ONLY files you may create, edit, or delete are under `./docs/`.** Every
  write target's path MUST be inside `./docs/`. Treat any write outside `./docs/`
  as forbidden — do not do it, even if it seems helpful or "while you're here".
- **Specifically off-limits (non-exhaustive):** `specs/**`, `README.md`, source
  code (`adapters/**`, `pipeline/**`, `schema/**`), `Makefile`,
  `*.sql`, `migrations/**`, `k8s/**`, `scripts/**`, `pyproject.toml`,
  `.env*`, `.sdd/**`, and anything else not under `./docs/`.
- **No code changes. No spec changes. No config changes.** If the requested
  documentation describes a feature that does not yet exist in the code, you still
  only write the docs that describe it — you do **not** implement it. (The
  `./docs/` → `mdtechnical` → `mdimplement` chain is how documented intent becomes
  code; this skill is strictly the first, docs-only step.)
- **You MAY read anything** (code, specs, config) to understand the system well
  enough to document it accurately. Reading is unrestricted; **writing is restricted
  to `./docs/`**.
- If the request cannot be satisfied without touching a non-`./docs/` file, **stop
  and say so** rather than touching it. Report what the user would need to run
  instead (e.g. `/mdtechnical` then `/mdimplement` to actually build the feature).

## Document the current state — never the migration

The docs describe **what the system is now**, as if it had always been this way.
They are a description of the present, not a changelog or a migration guide.

- **Write the end state, not the transition.** Edit the prose so it reads as the
  current truth. Do **not** add "previously X, now Y", "this used to…", "as of this
  change", "migrated from…", "the old behaviour was…", or before/after framing.
- **No migration instructions.** Do not document how to move from an old version to
  a new one, how to upgrade existing data/config, or steps that only matter to
  readers who knew the prior state. A reader arriving fresh should see only how
  things work today.
- **Remove, don't annotate, superseded content.** When the change replaces existing
  documentation, delete or rewrite the stale text in place — do not leave it behind
  with a note that it is outdated.
- Version history and migration paths, if they ever belong anywhere, are not this
  skill's concern; keep `./docs/` a clean snapshot of the current system.

## No open questions — ask the user instead

The documentation must contain **no open questions at all**.

- **Never write** an `## Open Questions` section, a TODO, a "TBD", a "to be
  confirmed", or any other placeholder into `./docs/`.
- When the request is ambiguous or you hit something you cannot resolve from the
  request, the code, or the existing docs, **stop and ask the user** a focused
  clarifying question. Fold their answer into the prose as settled fact.
- Only write what is resolved. If something genuinely cannot be settled even after
  asking, omit the uncertain claim rather than parking it in the docs as an open
  item.

## `./docs/index.md` structure — mandatory

`./docs/index.md` is the root index of the entire documentation tree. It must
always maintain a **tree-structured overview** of the repository topology:

```
<wrapper repo (this repo)>
├── <subrepo-a/> — <one-line role>
│   ├── <service-1> — <one-line description>
│   └── <service-2> — <one-line description>
├── <subrepo-b/> — <one-line role>
│   └── <service-3> — <one-line description>
└── …
```

The required sections and their content:

- **Wrapper repo** — a brief statement of what this meta/wrapper repo owns directly
  (e.g. its own infrastructure tree, tooling, or orchestration artefacts) and its
  role in relation to the subrepos.
- **Subrepos (submodules)** — one entry per pinned submodule. Each entry names the
  local path, the source repository, and a one-line role description.
- **Services per subrepo** — for each subrepo, enumerate the services or major
  components it contains, each with a one-line description. This may be a nested
  list under the subrepo entry or a dedicated sub-section.
- **Documentation index** — a table pointing to every `./docs/**/*.md` file that
  covers cross-cutting or per-subrepo topics, with a one-line description for each.

Whenever this skill adds, removes, or renames a subrepo, service, or documentation
file, it must also update `./docs/index.md` to keep the tree accurate. The index
must never be out of sync with the actual submodule set and service inventory.

## Steps

1. **Verify `./docs/` exists.** If it does not exist, raise an error and stop —
   "`./docs/` not found; the `mddocs` skill only edits the existing documentation
   tree." Do not create documentation anywhere else.

2. **Understand the request.** Read `$ARGUMENTS`. Determine what the documentation
   must now say. If the request is about a capability or behaviour, read the
   relevant code/specs (read-only) so the docs you write are accurate and use the
   project's real names, paths, commands, and contracts.

3. **Find the precise placement.** Before writing a single word, determine exactly
   where the new content belongs:
   - Identify the correct **file**: which service/sub-service subtree owns this
     topic? Prefer the most specific file over a parent-level overview.
   - Identify the correct **section within that file**: which heading is the
     natural owner? Read the surrounding paragraphs to understand the existing
     scope before inserting anything.
   - Prefer updating an existing file over creating a new one; create a new file
     under `./docs/` only when the topic genuinely has no home.
   - **If you are uncertain** about the right file or the right section — because
     the topic could reasonably live in more than one place, or because the
     existing structure does not clearly point to an answer — **stop and ask the
     user** before writing. State the two or three candidate locations and explain
     the trade-off briefly; let the user decide. Do not guess.

4. **Integrate — don't append.** Once the placement is confirmed, write the new
   content so it reads as if it was always part of the destination file:
   - Match the surrounding heading level, tone, terminology, and sentence style.
   - Weave the new prose into the existing flow rather than tacking it on as a
     separate block.
   - If the new content overlaps with or contradicts anything already in the file
     (same fact stated differently, a claim the new content supersedes, a step
     that conflicts), **surface each conflict explicitly to the user** and offer
     to remove the old passage. Do not silently leave two competing statements in
     the same file. Only delete the old content once the user confirms it should go.
   - If you add a new file, add a one-line entry for it in the appropriate index
     table.

5. **Self-check before finishing.** Confirm **every** path you wrote is inside
   `./docs/`. If any write touched something outside `./docs/`, you have violated
   the skill's contract — revert that change. Also confirm the prose describes the
   **current state only** — no "previously/now", before/after, or migration wording
   crept in — and that **no open question, TODO, TBD, or placeholder** remains.

6. **Report.** List the `./docs/` files created/edited and what changed in each.
   If the documented change implies follow-up work in code/specs, say so as a
   suggestion (e.g. "to actually implement this, run `/mdtechnical` →
   `/mdimplement`") — but do **not** perform that work here.

## Notes

- This skill never runs migrations, never edits the `Makefile`, never adds
  permissions, never commits. It only changes prose under `./docs/`.
- Committing the docs change (if wanted) is a separate step: `/mdgit` will branch
  it as `docs/<name>` per `specs/git.md`.
