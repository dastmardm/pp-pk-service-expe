# Streamlit UI (demo & debug)

The pipeline is wrapped behind a **Streamlit app** so a query can be run and
inspected stage by stage in the browser. It is the interactive counterpart to
the `oppp` CLI: the same fixed agent path, with run controls and every
intermediate output on screen.

Entry point: [ui/app.py](../../src/oppp/ui/app.py). It calls the same
[run_pipeline()](../../src/oppp/pipeline.py) the CLI does, so the UI and
`oppp run` behave identically for a given question and service — the UI adds no
behaviour the stages don't already have; it is a presentation layer.

> **Run it:** `streamlit run src/oppp/ui/app.py` (needs the `ui` extra:
> `pip install -e '.[ui]'`). The fixed pipeline also needs the LLM and TERMite
> extras plus `.env` credentials.

## What the screen shows

Three regions: a **run controls** sidebar, a **question picker** plus free-text
question box, and a **per-stage output** area that fills in after a run.

### 1. Question picker (top)

A list of the gold-set questions from [`docs/PPPK.xlsx`](../PPPK.xlsx) (`PK_Query`
sheet) is shown above the query box. Picking one (by query number / question) loads
it into the query box; pressing **Translate** runs the agent against it. A free-text
box stays available for arbitrary questions.

### 2. Run controls

The UI exposes controls that change the service target or execution behavior.
It does not expose per-stage method controls. TERMite enhancement is always part
of the run, and no stage can be bypassed or replaced.

| Control | Purpose | CLI equivalent |
|---------|---------|----------------|
| Service | The PharmaPendium PK service surface. | `--service pk` |
| Execute | POST the valid final query to the PharmaPendium API for a live count. | `--execute` / `--no-execute` |

Turning **Execute** on posts the final query to the PharmaPendium API for a live
count. The Stage -1 expander, Stage 0 TERMite enhancer, Stage 1 decomposer,
Stage 2 translator/normalizer, and Stage 3 aggregator are fixed and run in that
order.

### 3. Intermediate output per stage

After the run, each stage's intermediate artifact is displayed, mirroring the
CLI's stage-by-stage trace and the `PipelineResult` fields:

| Stage | What is shown | From |
|-------|---------------|------|
| 0 — enhance | recognized-entity annotations (`surface → label`, type) from TERMite | `result.enhanced` |
| 1 — decompose | the per-field components table (`type`, `field`, `fragment`, boolean group, `source`, `reason`) | `result.decomposition.components` |
| 2 — translate | each machine subquery — the `(operator, field, value)` constraint — plus its grounding (matched preferred labels, `expanded_from` class/term, confidence) | `result.subqueries` |
| 3 — aggregate | the final machine-query payload (the JSON the API receives) and validation status (`ok` / issues) | `result.machine_query.to_payload()`, `result.ok`, `result.issues` |
| execution | when **Execute** is on and the query is valid: the `countTotal` returned by the API | `execute_count(...)` |

Showing every stage makes the UI a debugging surface: you can see exactly where a
wrong result came from — a mis-routed field in Stage 1, bad grounding in Stage 2,
or the wrong boolean shape in Stage 3 — instead of only the final query.

## Relationship to the CLI

Anything the UI shows can be reproduced from the terminal:

```bash
# the UI's "Translate" button == this fixed pipeline
oppp run "<question>" --execute

# the UI's question picker == loading a gold case by number
oppp run --case 23
```

Single stages map to the isolation commands (`oppp enhance` / `decompose` /
`field` / `aggregate`) described in [build-status.md](build-status.md).

> **Status:** the app exists ([ui/app.py](../../src/oppp/ui/app.py)) and renders
> the run-controls sidebar, gold-set question picker, Stage 0 annotations, Stage 1
> component table, Stage 2 subqueries with grounding, Stage 3 payload, and
> execution count. Stage -1 expansion is not displayed as a separate UI
> panel.
