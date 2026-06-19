# Streamlit UI (demo & debug)

The pipeline is wrapped behind a **Streamlit app** so a query can be run and
inspected stage by stage in the browser. It is the interactive counterpart to
the `oppp` CLI: the same agent, the same backends, but with the per-step
configuration and every intermediate output on screen.

Entry point: [ui/app.py](../../src/oppp/ui/app.py). It calls the same
[run_pipeline()](../../src/oppp/pipeline.py) the CLI does, so the UI and
`oppp run` behave identically for a given configuration — the UI adds no
behaviour the stages don't already have; it is a presentation layer.

> **Run it:** `streamlit run src/oppp/ui/app.py` (needs the `ui` extra:
> `pip install -e '.[ui]'`). The `termite` enhancer and `llm` backends
> additionally need their extras + `.env` credentials; the offline doubles
> (`gazetteer` / `deterministic`) run with neither.

## What the screen shows

Three regions: a **question picker** at the top, a **per-step configuration**
panel, and a **per-stage output** area that fills in after a run.

### 1. Question picker (top)

A list of the SME gold-set questions
([inputs/sme_expected_cases.csv](../../inputs/sme_expected_cases.csv)) is shown
at the top. Picking one (by `query_number` / `question`) loads it into the query
box and runs the agent against it — the fast path for reproducing a known case.
A free-text box stays available for arbitrary questions. When a gold case is
picked, its expected result count `s` is carried alongside so the live count can
be compared to it (see the execution row below).

### 2. Per-step configuration (the registries, selectable)

Every stage's backend is a dropdown populated from that stage's registry, so the
user composes the pipeline without touching code or CLI flags. Each control maps
one-to-one to a [run_pipeline()](../../src/oppp/pipeline.py) argument / `oppp run`
flag:

| Control | Stage | Options (registry) | CLI equivalent |
|---------|-------|--------------------|----------------|
| Service | — | `service_registry` (`safety`) | `--service` |
| Enhancer | 0 — enhance *(optional)* | `noop` (default), `termite` | `--enhancer` |
| Decomposer | 1 — decompose | `llm` (default), `gazetteer` | `--decomposer` |
| Translator | 2 — translate | `tool` (default), `deterministic` | `--translator` |
| Aggregator | 3 — aggregate | `llm` (default), `deterministic` | `--aggregator` |
| Normalizer | 2 — misspelling | `noop` (default), `fuzzy` | `--normalizer` |
| Execute | — | on / off | `--execute` / `--no-execute` |

For example, to demo the optional Stage 0 with and without TERMite, flip the
**Enhancer** dropdown between `termite` and `noop` and re-run. Pinning the
offline doubles (`gazetteer` / `deterministic`) gives an LLM-free run; turning
**Execute** on posts the final query to the PharmaPendium API for a live count.

### 3. Intermediate output per stage

After the run, each stage's intermediate artifact is displayed, mirroring the
CLI's stage-by-stage trace and the `PipelineResult` fields:

| Stage | What is shown | From |
|-------|---------------|------|
| 0 — enhance | the enhanced query text + recognized-entity annotations (`surface → label`, type); empty when the enhancer is `noop` | `result.enhanced` |
| 1 — decompose | the per-field components table (`type`, `field`, `fragment`, boolean group, `source`, `reason`) | `result.decomposition.components` |
| 2 — translate | each machine subquery — the `(operator, field, value)` constraint — plus its grounding (matched preferred labels, `expanded_from` class/term, confidence) | `result.subqueries` |
| 3 — aggregate | the final machine-query payload (the JSON the API receives) and validation status (`ok` / issues) | `result.machine_query.to_payload()`, `result.ok`, `result.issues` |
| execution *(optional)* | when **Execute** is on and the query is valid: the `countTotal` returned, next to the gold `s` if a gold case is loaded | `execute_count(...)` |

Showing every stage makes the UI a debugging surface: you can see exactly where a
wrong result came from — a mis-routed field in Stage 1, bad grounding in Stage 2,
or the wrong boolean shape in Stage 3 — instead of only the final query.

## Relationship to the CLI

Anything the UI shows can be reproduced from the terminal:

```bash
# the UI's "Translate" button == this, with the selected backends
oppp run "<question>" \
  --enhancer noop --decomposer llm --translator tool \
  --aggregator llm --normalizer fuzzy --execute

# the UI's question picker == loading a gold case by number
oppp run --case 23
```

Single stages map to the isolation commands (`oppp enhance` / `decompose` /
`field` / `aggregate`) described in [build-status.md](build-status.md).

> **Status:** the app exists ([ui/app.py](../../src/oppp/ui/app.py)) and renders
> the Stage 1–3 panels with **Service / Decomposer / Normalizer** selectors over
> a single query box. The full per-step selector set (**Enhancer, Translator,
> Aggregator, Execute**), the **Stage 0** output panel, and the **gold-set
> question picker** described above are the documented target; see
> [build-status.md](build-status.md) for the current subset.
