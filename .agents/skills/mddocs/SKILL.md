---
name: "mddocs"
description: "Author or edit a requested change to the human-facing documentation under docs/ only; touches nothing outside docs/. Use when the user wants to change or add documentation directly — not to propagate it into specs or code (use /mdtechnical → /mdimplement for that)."
argument-hint: "A description of the documentation change to make (e.g. \"add the ability to clear data and start fresh\")"
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

## The one hard rule — only `docs/**` may be written

This skill exists to edit the human-facing documentation and **nothing else**.

- **The ONLY files you may create, edit, or delete are under `docs/`.** Every
  write target's path MUST begin with `docs/`. Treat any write outside `docs/` as
  forbidden — do not do it, even if it seems helpful or "while you're here".
- **Specifically off-limits (non-exhaustive):** `specs/**`, `README.md`, source
  code (`adapters/**`, `pipeline/**`, `schema/**`), `Makefile`,
  `*.sql`, `migrations/**`, `k8s/**`, `scripts/**`, `pyproject.toml`,
  `.env*`, `.Codex/**`, and anything else not under `docs/`.
- **No code changes. No spec changes. No config changes.** If the requested
  documentation describes a feature that does not yet exist in the code, you still
  only write the docs that describe it — you do **not** implement it. (The
  `docs/` → `mdtechnical` → `mdimplement` chain is how documented intent
  becomes code; this skill is strictly the first, docs-only step.)
- **You MAY read anything** (code, specs, config) to understand the system well
  enough to document it accurately. Reading is unrestricted; **writing is
  `docs/`-only**.
- If the request cannot be satisfied without touching a non-`docs/` file, **stop
  and say so** rather than touching it. Report what the user would need to run
  instead (e.g. `/mdtechnical` then `/mdimplement` to actually build
  the feature).

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
  skill's concern; keep `docs/` a clean snapshot of the current system.

## No open questions — ask the user instead

The documentation must contain **no open questions at all**.

- **Never write** an `## Open Questions` section, a TODO, a "TBD", a "to be
  confirmed", or any other placeholder into `docs/`.
- When the request is ambiguous or you hit something you cannot resolve from the
  request, the code, or the existing docs, **stop and ask the user** a focused
  clarifying question. Fold their answer into the prose as settled fact.
- Only write what is resolved. If something genuinely cannot be settled even after
  asking, omit the uncertain claim rather than parking it in the docs as an open
  item.

## Steps

1. **Verify `docs/` exists.** If it does not, raise an error and stop —
   "`docs/` not found; the `mddocs` skill only edits the documentation tree." Do
   not create documentation anywhere else.

2. **Understand the request.** Read `$ARGUMENTS`. Determine what the documentation
   must now say. If the request is about a capability or behaviour, read the
   relevant code/specs (read-only) so the docs you write are accurate and use the
   project's real names, paths, commands, and contracts.

3. **Locate the right doc files.** Explore the `docs/` tree and find the file(s)
   that should carry this change. Prefer updating an existing file over creating a
   new one; create a new `docs/...` file only when the topic genuinely has no home.
   Follow the existing structure, headings, tone, and cross-reference style (links
   within `docs/`, the index tables in `docs/index.md` / section index files).

4. **Make the edits — under `docs/` only.** Write clear, accurate documentation.
   Keep it consistent with the rest of `docs/` (terminology, contract names like
   `CONTRACT-BRONZE-PATH`, command names, path templates). If you add a new file,
   add a one-line entry for it in the appropriate index table within `docs/`.

5. **Self-check before finishing.** Confirm **every** path you wrote begins with
   `docs/`. If any write touched something outside `docs/`, you have violated the
   skill's contract — revert that change. Also confirm the prose describes the
   **current state only** — no "previously/now", before/after, or migration
   wording crept in (see "Document the current state — never the migration") — and
   that **no open question, TODO, TBD, or placeholder** remains (see "No open
   questions — ask the user instead").

6. **Report.** List the `docs/` files created/edited and what changed in each.
   If the documented change implies follow-up work in code/specs, say so as a
   suggestion (e.g. "to actually implement this, run `/mdtechnical` →
   `/mdimplement`") — but do **not** perform that work here.

## Notes

- This skill never runs migrations, never edits the `Makefile`, never adds
  permissions, never commits. It only changes prose under `docs/`.
- Committing the docs change (if wanted) is a separate step: `/mdgit` will branch it
  as `docs/<name>` per `specs/git.md`.
