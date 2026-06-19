---
name: "research"
description: "Analyse one or more data sources against supplementary materials and extract the insight a request asks for, writing the result to an output artefact. Generic: the data source, the supplementary inputs, the question, and the output shape all come from the request. Use when the user wants to investigate, profile, cross-reference, or derive something from data — e.g. \"read X and Y, find the relationship, write it to a file\". Trigger phrases: \"analyse this data\", \"extract insight from\", \"research\", \"profile this dataset\", \"figure out the mapping between\", \"investigate this source\"."
argument-hint: "What to research: the data source(s) to read, any supplementary code/docs/schemas, the question to answer, and the desired output file/format (e.g. \"read source A and schema B, find the A→B mapping, write mapping.md\")"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` is a free-text research request. It describes some mix of: **data
source(s)** to read, **supplementary materials** (code, docs, schemas, examples)
that inform the analysis, the **question** to answer, and the **output** to
produce (a file path and/or format). Any of these may be implicit — resolve what
you can from the request and the project, and ask about the rest.

> **One concrete instance of the generic pattern:** *"read the silver layer for
> store X, read the gold-layer schema for X, find the silver→gold mapping, and
> write `woo_mapping.md`."* That is just one shape. This skill does **generic**
> data analysis — substitute any sources, any question, any output.

## What this skill is

A **read-and-reason** loop over data. You connect to the data source(s)
read-only, write small throwaway analysis code to read / sample / profile /
cross-reference them, reason about the result against the supplementary inputs,
and synthesise the answer into the requested output artefact. The scratch code
is a means to an end — only the deliverable persists.

```
data source(s) + supplementary materials + question  ──▶  /research  ──▶  output artefact
                          (read-only)                  (throwaway scratch code, then cleaned up)
```

## The two hard rules

1. **Read-only on every data source.** Never write to, delete from, mutate,
   migrate, or otherwise alter a source you were asked to analyse (object
   storage, databases, files, APIs). You **observe** it; you do not change it. If
   answering would require a write to the source, stop and say so.

2. **Scratch code is ephemeral; only the deliverable persists.** Put throwaway
   analysis scripts in a temporary, version-control-ignored location (a system
   temp dir, or a `tmp/`/`.scratch/` path you confirm is git-ignored). Clean it up
   when done. The repository must end up with **only** the requested output
   artefact (plus anything the user explicitly asked to keep) — no leftover
   scratch scripts, sample dumps, or notebooks.

## Steps

1. **Parse the request into four parts.** Identify (a) the **data source(s)** to
   read, (b) the **supplementary materials** (code/docs/schemas/examples) that
   constrain or inform the analysis, (c) the **question** to answer, and (d) the
   **output** — its file path and format. If the source, the question, or the
   output is genuinely ambiguous, ask a focused question (with a recommended
   default) before doing work; don't guess at the target of the analysis.

2. **Establish read access.** Work out **how** to read each source using the
   project's own conventions — existing config, connection settings, client
   libraries, or helpers already in the repo. Discover credentials/endpoints from
   the project's configured mechanism; never hardcode or invent them, and never
   print secrets. If a source can't be reached, report exactly what's missing
   rather than fabricating data.

3. **Set up a scratch workspace.** Create the throwaway location from Rule 2.
   This is where every exploratory script, sample, and intermediate file lives.

4. **Explore, then analyse.** Iterate: read a small sample first to understand
   shape/structure, then widen as needed. Profile what the question requires
   (fields, types, distributions, keys, relationships, overlaps, gaps).
   Cross-reference the data against the supplementary materials. Prefer small,
   composable scripts you can re-run over one monolithic pass. Ground every
   conclusion in something you actually observed — note sample sizes and any
   assumption you had to make.

5. **Synthesise the output artefact.** Write the requested deliverable at the
   requested path in the requested format. Make it self-contained and
   evidence-backed: state what was analysed, the findings/insight, and any
   caveats or assumptions. Match the structure/tone the request implies (a
   mapping table, a report, a summary, a dataset, etc.). If no path/format was
   given, choose a sensible one and say what you chose.

6. **Clean up the scratch workspace.** Remove the throwaway code and any
   intermediate samples. Confirm the only new/changed files are the deliverable
   (and anything explicitly requested). Verify nothing was written back to a data
   source.

7. **Report.** State: the source(s) read and how, the question answered, where
   the output artefact is, the key insight(s) in one or two lines, and the
   assumptions/limitations (sample coverage, ambiguities resolved, anything not
   verifiable).

## Rules

- **Observe, never alter.** Sources are read-only (Rule 1). The only thing you
  create outside scratch is the deliverable.
- **Leave no scratch behind.** Throwaway code is ephemeral and git-ignored, and
  is deleted before you finish (Rule 2).
- **Discover, don't invent.** Connection details, schemas, and credentials come
  from the project's real configuration — not from guesses. Don't print secrets.
- **Evidence over assertion.** Insights must trace to data you actually read;
  flag sampling limits and assumptions instead of overstating confidence.
- **Ask when the target is unclear.** A wrong source, question, or output wastes
  the whole run — clarify those up front, then proceed without further hand-holding.
- **Don't commit or push.** This skill produces an artefact; version control is a
  separate, user-driven step.

## Notes

- The skill is **product-agnostic**. It assumes nothing about a specific data
  source, schema, or domain — everything specific comes from `$ARGUMENTS` and the
  project. Point it at any sources and ask any question.
- It is a **leaf** skill: it does not chain to or trigger other skills.
- If the analysis reveals follow-up work (a code change, a migration, a spec
  edit), mention it as a suggestion — but this skill only reads data and writes
  the requested artefact; it does not perform that follow-up.
