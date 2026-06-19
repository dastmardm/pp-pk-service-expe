---
name: "implement"
description: "Build or update the codebase to satisfy a technical specification and its planning artefacts. Use as the third pipeline step, after /technical and before /evaluation."
argument-hint: "Path to technical specification (default: specs/technical.md); optional scope filter"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

$ARGUMENTS may contain a path to the technical specification and/or a scope filter (e.g. "bronze only"). Default spec path: `specs/technical.md`.

## Outline

You are the **`implement`** step:

```
technical → implement → evaluation → fix
```

Read the technical specification and produce or update the codebase so it satisfies every requirement in that document.

### Steps

1. Read the technical specification from the path in $ARGUMENTS, or the default
   `specs/technical.md` (if the repo uses a different name for that artefact, e.g.
   `specs/technical_specification.md`, read that instead — see `../CONVENTIONS.md` → Artefact path resolution).
   Also read the other planning artefacts `/technical` produced for context:
   `constitution.md`, `requirements.md`, `plan.md`, `tasks.md`, `skeleton.md`,
   `evaluation.md`. (You do not need `git.md` — that is `/git`'s input.)
   Stop with an error if the technical spec does not exist — run `/technical` first.

2. Explore the existing codebase to understand current structure before making any changes.

3. Derive a work list from the technical spec:
   - One item per requirement
   - Group by component or layer
   - Note dependencies between items (implement in dependency order)
   - If a scope filter was given, restrict to matching items but still read the full spec for context

4. Implement each item:
   - Write or modify only the files needed to satisfy the requirement
   - After each change, verify it satisfies the requirement and does not break callers
   - Check for security issues: no hardcoded secrets, no SQL string formatting, no command injection

5. For any new configuration or secrets introduced:
   - Add them to the env template file specified in `specs/technical.md` → Configuration and Secrets, with a comment and safe default

6. For any new database changes:
   - Write an idempotent migration file following the naming convention defined in `specs/skeleton.md` → Conventions (and `specs/tasks.md`)

7. Do not:
   - Add comments explaining what code does
   - Add error handling for impossible conditions
   - Introduce abstractions not required by the spec
   - Add backwards-compatibility shims

8. Report: files created or modified, requirements satisfied, any requirements left unimplemented and why. Next step: `/evaluation`.
