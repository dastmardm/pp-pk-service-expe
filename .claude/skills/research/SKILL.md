---
name: "research"
description: "Analyse one or more data sources against supplementary materials and extract the insight a request asks for, writing the resulting insight into the project's docs/ tree — where it becomes a source the technical→implement chain consumes. Generic: the data source(s), the supplementary inputs, and the question all come from the request; the deliverable always lands under docs/. Use when the user wants to investigate, profile, cross-reference, or derive something from data — e.g. \"read X and Y, find the relationship, and document it\". Trigger phrases: \"analyse this data\", \"extract insight from\", \"research\", \"profile this dataset\", \"figure out the mapping between\", \"investigate this source\"."
argument-hint: "What to research: the data source(s) to read, any supplementary code/docs/schemas, the question to answer, and optionally the docs/research topic/filename for the write-up (it always lands under docs/research/; default docs/research/<topic>.md — e.g. \"read source A and schema B, find the A→B mapping, write docs/research/a-b-mapping.md\")"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` is a free-text research request. It describes some mix of: **data
source(s)** to read, **supplementary materials** (code, docs, schemas, examples)
that inform the analysis, and the **question** to answer. It may also suggest a
**topic/filename** for the write-up — which always lands under **`docs/research/`**
(see the hard rules), never at a caller-chosen path; resolve what you can from the
request and the project, and ask about the rest.

> **One concrete instance of the generic pattern:** *"read the silver layer for
> store X, read the gold-layer schema for X, find the silver→gold mapping, and
> document it."* The insight is written to e.g. `docs/research/woo-mapping.md`. That
> is just one shape. This skill does **generic** data analysis — substitute any
> sources, any question — but the deliverable is always a `docs/` artefact.

## What this skill is

A **read-and-reason** loop over data. You connect to the data source(s)
read-only, write small throwaway analysis code to read / sample / profile /
cross-reference them, reason about the result against the supplementary inputs,
and synthesise the answer into a **`docs/` insight artefact**. The scratch code
is a means to an end — only the `docs/` deliverable persists.

```
data source(s) + supplementary materials + question  ──▶  /research  ──▶  docs/ insight artefact
                          (read-only)                  (throwaway scratch code, then cleaned up)   (a source /technical reads)
```

## The hard rules

1. **Read-only on every data source.** Never write to, delete from, mutate,
   migrate, or otherwise alter a source you were asked to analyse (object
   storage, databases, files, APIs). You **observe** it; you do not change it. If
   answering would require a write to the source, stop and say so.

2. **Scratch code is ephemeral; only the deliverable persists.** Put throwaway
   analysis scripts in a temporary, version-control-ignored location (a system
   temp dir, or a `tmp/`/`.scratch/` path you confirm is git-ignored). Clean it up
   when done. The repository must end up with **only** the `docs/` deliverable
   (plus anything the user explicitly asked to keep) — no leftover
   scratch scripts, sample dumps, or notebooks.

3. **The insight deliverable lives under `docs/research/**`.** The persisted write-up
   is the project's *derived knowledge about its data*, so it is written **only under
   the reserved `docs/research/**` namespace** (filename = the topic, e.g.
   `docs/research/woo-mapping.md`) — never elsewhere in `docs/` and never outside it.
   This both puts the insight into the `docs/ → technical → implement` lineage (so
   `/technical` picks it up) and keeps it fenced as **derived evidence**, distinct from
   the human-authored intent it must never silently override (`../CONVENTIONS.md` →
   `docs/` authority). Open the write-up with a derived-evidence marker (what was
   analysed, when, sample coverage). Apart from the ephemeral git-ignored scratch of
   Rule 2, **write nothing outside `docs/research/**`** (besides the one `docs/` index
   entry that registers the new file).

## Steps

1. **Parse the request into four parts.** Identify (a) the **data source(s)** to
   read, (b) the **supplementary materials** (code/docs/schemas/examples) that
   constrain or inform the analysis, (c) the **question** to answer, and (d) the
   **`docs/` topic** — which `docs/` file the write-up belongs in (default
   `docs/research/<topic>.md`). If the source or the question is genuinely
   ambiguous, ask a focused question (with a recommended default) before doing
   work; don't guess at the target of the analysis.

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

5. **Synthesise the `docs/research/` insight artefact.** Write the deliverable **under
   `docs/research/`** (filename = the topic), following the surrounding `docs/`
   structure, tone, and cross-reference style. Make it self-contained and
   evidence-backed: state what was analysed, the findings/insight, **how to leverage
   it in the project**, and any caveats or assumptions — clearly marked as derived
   evidence. Match the shape the question implies (a mapping table, a profile, a
   summary). Add a one-line entry for any new file to the appropriate `docs/` index
   table (as the `docs` skill does), so `/technical` discovers it.

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
  create outside the ephemeral scratch is the `docs/` deliverable (Rule 3).
- **Leave no scratch behind.** Throwaway code is ephemeral and git-ignored, and
  is deleted before you finish (Rule 2).
- **Discover, don't invent.** Connection details, schemas, and credentials come
  from the project's real configuration — not from guesses. Don't print secrets.
- **Evidence over assertion.** Insights must trace to data you actually read;
  flag sampling limits and assumptions instead of overstating confidence.
- **Ask when the target is unclear.** A wrong source, question, or `docs/research/`
  topic wastes the whole run — clarify those up front, then proceed without further
  hand-holding.
- **Don't commit or push.** This skill produces an artefact; version control is a
  separate, user-driven step.

## Notes

- The skill is **product-agnostic**. It assumes nothing about a specific data
  source, schema, or domain — everything specific comes from `$ARGUMENTS` and the
  project. Point it at any sources and ask any question; only the output **home** is
  fixed — the insight always lands under `docs/`.
- It is a **leaf** skill: it does not emit `EXECUTE_COMMAND` or trigger other skills.
  It feeds the pipeline only **indirectly** — its `docs/` write-up becomes a source the
  next `/technical` run reads, exactly like human-authored documentation.
- If the analysis reveals follow-up work (a code change, a migration, a spec edit),
  mention it as a suggestion — but this skill only reads data and writes the `docs/`
  artefact; it does not perform that follow-up.
