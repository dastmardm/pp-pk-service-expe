---
name: "mdrevdocs"
description: "Reverse-engineer the human-facing documentation tree under docs/ from the existing source code. Reads the codebase (and any specs/config/infra) and writes docs/ — creating the docs/ folder and its internal files plus docs/index.md. The inverse of the forward chain: where /mdtechnical → /mdimplement goes docs/ → specs → code, this skill goes code → docs/. Use to bootstrap or refresh docs/ from what the code actually does."
argument-hint: "(optional) a scope hint — which part of the codebase to document, or a focus (e.g. \"document the k3s adapters\" or \"just the pipeline\"). With no argument, document the whole repository."
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` is an **optional scope hint** — it may name a subsystem, directory,
or focus to document (e.g. *"document the k3s adapters"*, *"just the pipeline"*).
It is **not** a documentation request and **not** a source of product facts: every
fact in the docs you write must come from the **source code** (and the project's
specs/config/infra), never from the argument text. With no argument, document the
**whole repository**.

## What this skill is — the reverse of the forward chain

The other skills run **forward**: a human edits `docs/`, then
`/mdtechnical` → `/mdimplement` projects that intent down into `specs/` and then
into **code**. Documentation is the *input*; code is the *output*.

```
forward:   docs/  ──▶  /mdtechnical  ──▶  specs/  ──▶  /mdimplement  ──▶  code
reverse:   code   ──▶  /mdrevdocs    ──▶  docs/                  (this skill)
```

`mdrevdocs` runs **backward**. It treats the **existing source code as the source
of truth** and reverse-engineers the human-facing documentation tree under
`docs/` from it — *creating* the `docs/` folder and the internal files that
describe what the system is, what it does, and how it is operated. This is how you
**bootstrap `docs/` for a repo that has code but no docs**, or **refresh `docs/`**
so it once again reflects what the code actually does.

> **Typical user request:** *"There's no `docs/` yet — read the code and write the
> documentation for it."* The answer is a full run of this skill: read the
> codebase, then create `docs/` with an index and the per-topic files.

It is the natural complement to `/mddocs`: `mddocs` edits human-authored
documentation when a human knows what should change; `mdrevdocs` *derives* that
documentation in the first place, from the code, when none exists or it has gone
stale. After `mdrevdocs` writes `docs/`, a human reviews and refines it (optionally
via `/mddocs`), and from then on the forward chain (`/mdtechnical`) can project it.

## The one hard rule — only `docs/**` may be written

This skill **reads** the codebase and **writes documentation**. Its only write
target is `docs/`.

- **The ONLY files you may create, edit, or delete are under `docs/`.** Every
  write target's path MUST begin with `docs/`. Treat any write outside `docs/` as
  forbidden — do not do it, even if it seems helpful.
- **Specifically off-limits (non-exhaustive):** source code (`k3s-base/**`,
  `k3s-maine/**`, and any adapters/pipeline/schema trees), `specs/**`, `README.md`
  at the repo root, `Makefile`, `*.sql`, `migrations/**`, `scripts/**`, `*.sh`,
  `pyproject.toml`, `.env*`, `.sdd/**`, and anything else not under `docs/`.
- **No code changes. No spec changes. No config changes. No git.** You document
  what exists; you do not modify it, refactor it, or "fix" it while reading. If you
  notice a bug or inconsistency in the code, **note it in the docs as an observed
  behaviour or open question** — do not change the code.
- **You MAY read anything** (code, specs, config, infra manifests, scripts, commit
  history) — reading is unrestricted and is the whole point. **Writing is
  `docs/`-only.**
- If documenting accurately would require touching a non-`docs/` file, **stop and
  say so** rather than touching it.

## Steps

1. **Establish scope.** Read `$ARGUMENTS`. If it names a subsystem or focus, scope
   the documentation to that; otherwise document the whole repository. State the
   scope you settled on in your final report.

2. **Read the codebase as the source of truth.** Explore the repo (do not assume
   fixed paths — discover them). Build an accurate model of:
   - **What the system is and does** — its purpose and core capabilities, inferred
     from entry points, services, manifests, and how the pieces wire together.
   - **Components & boundaries** — the modules/services/adapters, what each is
     responsible for, and how they interact.
   - **Data & contracts** — schemas, path templates, message shapes, the data flow
     between components (state these as the *observed* contracts the code enforces).
   - **Operational model** — how it is built, deployed, configured, and run
     (manifests, scripts, env vars, secrets-by-name — never secret *values*).
   - **Configuration surface** — the env vars / settings the code reads, each with
     its purpose and where it is consumed.
   Ground every documented claim in something you actually read. Prefer the real
   names, paths, and commands from the code over invented ones.

3. **Design the `docs/` tree.** Decide the documentation structure that fits this
   project. A sensible default, adapt as the code warrants:
   - `docs/index.md` — the top-level index: one short paragraph on what the project
     is, plus an index **table** linking every other doc file with a one-line
     description (this is the index the forward chain and `/mddocs` rely on).
   - `docs/overview.md` — purpose, core capabilities, key actors, high-level data
     flow (the *what* and *why*, in human language).
   - `docs/architecture.md` — components, their responsibilities, and how they
     interact; the observed data contracts and path templates.
   - `docs/operations.md` — how to build, deploy, configure, and run the system;
     the configuration/secrets surface (names and purpose, never values).
   - one focused file per major subsystem when a single page would be too dense.
   Keep it human-facing: this is product/operations documentation, **not** a spec
   and **not** an API dump. Omit implementation minutiae that a reader does not need.

4. **Resolve unknowns by asking — never by leaving open questions.** Where the code
   alone cannot reveal intent (*why* a choice was made, an apparent inconsistency,
   an ambiguous behaviour), **stop and ask the user** a focused clarifying question,
   then fold the answer into the prose as settled fact. **Do not** write an
   `## Open Questions` section, a TODO, a "TBD", a "to be confirmed", or any other
   placeholder into `docs/`. The documentation must contain **no open questions at
   all** — only resolved, stated facts. If a question is genuinely unanswerable and
   the user cannot resolve it, omit the uncertain claim rather than parking it in
   the docs as an open item. Gather your clarifying questions and ask them before
   finalising the files.

5. **Create `docs/` and write the files.** Create the `docs/` directory if it does
   not exist and write the files. Use clear, consistent prose, headings, and
   cross-references **within `docs/`**. Every new file gets a one-line entry in the
   `docs/index.md` index table.

6. **No provenance watermark in the docs.** Do **not** stamp the documentation with
   a note that it was reverse-engineered or derived from the source code. Write the
   `docs/` files as clean, human-facing documentation that simply describes the
   system — no "generated from code", "reverse-engineered", "auto-derived", or
   similar banners in `docs/index.md` or any other file. Convey the
   derived-and-awaiting-ratification nature in your **final report to the user**
   (Step 8), not in the `.md` files.

7. **Self-check before finishing.** Confirm **every** path you wrote begins with
   `docs/`. Confirm `docs/index.md` exists and links every other file you created.
   Confirm no fact in the docs lacks a basis in the code you read. Confirm **no
   file contains an open question, TODO, TBD, or placeholder**, and **no file
   carries a "reverse-engineered / generated from source" watermark**. If any write
   touched something outside `docs/`, you have violated the contract — revert it.

8. **Report.** List the `docs/` files created/edited and what each covers, the
   scope you documented, the clarifying questions you asked and how their answers
   shaped the docs, and the suggested next step: a human reviews/refines `docs/`
   (optionally via `/mddocs`), after which `/mdtechnical` can project it forward
   into `specs/` and code. Note here (to the user, not in the docs) that the
   documentation was derived from the code and is awaiting human ratification.

## Notes

- **Direction matters.** This is the *only* skill that writes `docs/` **from**
  code. The forward chain (`/mdtechnical` → `/mdimplement`) writes code **from**
  `docs/`. Do not conflate the two: never let a `specs/` artefact or generated
  file leak into the docs as if it were human intent — your only input is the code.
- **Derived, not ratified.** Like `/mdresearch` output, what you write is *derived
  evidence* about the system, awaiting human ratification. Convey this in your
  **report to the user** (Step 8) — **not** as a watermark in the `.md` files. A
  human turning it into ratified intent (via review / `/mddocs`) is what makes it
  the source of truth the forward chain may then project from.
- **No open questions in `docs/`.** Resolve unknowns by asking the user and folding
  the answer in (Step 4). Never leave an `## Open Questions`, TODO, TBD, or
  placeholder in the documentation.
- This skill never runs migrations, never edits the `Makefile`, never adds
  permissions, never commits. It only creates/edits prose under `docs/`.
- Committing the docs (if wanted) is a separate step: `/mdgit` will branch it as
  `docs/<name>` per `specs/git.md`.
