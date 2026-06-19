"""Typer CLI: run the full pipeline, isolate a single stage, or evaluate.

Each subcommand exposes a step so it can be exercised on its own (the
isolatability the design requires).
"""

from __future__ import annotations

import json

import typer

from oppp.eval.harness import evaluate
from oppp.pipeline import run_pipeline
from oppp.services.base import get_service
from oppp.stages.aggregate import get_aggregator
from oppp.stages.decompose import decompose as run_decompose
from oppp.stages.enhance import enhance as run_enhance
from oppp.stages.translate import translate_one
from oppp.taxonomy.index import get_index

app = typer.Typer(no_args_is_help=True, help="Decomposed NL -> machine-query translator.")


@app.command()
def run(
    query: str = typer.Argument(None, help="The NL question (omit when using --case)."),
    service: str = "safety",
    enhancer: str = typer.Option("termite", help="Stage 0 enhancer: noop | termite."),
    decomposer: str = typer.Option("llm", help="Stage 1 decomposer: llm | gazetteer (offline)."),
    translator: str = typer.Option("tool", help="Stage 2 translator."),
    aggregator: str = typer.Option(
        "llm", help="Stage 3 aggregator: llm | deterministic (offline)."
    ),
    normalizer: str = "fuzzy",
    case: int = typer.Option(
        None, "--case", help="Load the question from the SME gold set by query_number."
    ),
    payload_only: bool = typer.Option(False, help="Print only the API payload JSON."),
    execute: bool = typer.Option(
        True,
        "--execute/--no-execute",
        "-e/-E",
        help="Execute against the API and report datapoints retrieved (on by default; --no-execute to skip).",
    ),
):
    """Run the full pipeline on QUERY (or a gold --case), showing every stage.

    With --case, also prints the SME gold filters next to the agent's filters.
    """
    gold_row = None
    if case is not None:
        from oppp.eval.compare import find_gold_case

        gold_row = find_gold_case(case)
        if gold_row is None:
            typer.echo(f"no gold case with query_number={case}", err=True)
            raise typer.Exit(2)
        query = gold_row.get("question", "").strip()
    if not query:
        typer.echo("provide a QUERY or --case N", err=True)
        raise typer.Exit(2)

    result = run_pipeline(
        query,
        service,
        enhancer=enhancer,
        decomposer=decomposer,
        translator=translator,
        aggregator=aggregator,
        normalizer=normalizer,
    )
    if payload_only:
        typer.echo(json.dumps(result.machine_query.to_payload(), indent=2, ensure_ascii=False))
        raise typer.Exit(0 if result.ok else 1)

    typer.echo("# Input")
    if case is not None:
        typer.echo(f"  case      : {case}  ({gold_row.get('query_type', '').strip()})")
    typer.echo(f"  query     : {query!r}")
    typer.echo(
        f"  config    : service={service} enhancer={enhancer} decomposer={decomposer} "
        f"translator={translator} aggregator={aggregator} normalizer={normalizer} execute={execute}"
    )
    typer.echo()
    typer.echo("# Stage 0 — enhancement")
    if result.enhanced and result.enhanced.annotations:
        for a in result.enhanced.annotations:
            typer.echo(f"  {a.entity_type or 'ENTITY':18} {a.surface!r} -> {a.label!r}")
    else:
        typer.echo(f"  (enhancer={enhancer}: no annotations)")
    typer.echo()
    typer.echo("# Stage 1 — decomposition")
    typer.echo(f"  input: {(result.enhanced.text if result.enhanced else query)!r}")
    for c in result.decomposition.components:
        bg = f" [{c.boolean_group.op.value}:{c.boolean_group.id}]" if c.boolean_group else ""
        typer.echo(f"  [{c.type.value:8}] {c.field:18} <- {c.nl_fragment!r}{bg}  ({c.source})")
        typer.echo(f"             reason: {c.reason}")

    typer.echo("\n# Stage 2 — translate subqueries (+ grounding)")
    for sq in result.subqueries:
        typer.echo(f"  {json.dumps(sq.to_constraint(), ensure_ascii=False)}")
        if sq.grounding and sq.grounding.matched:
            names = ", ".join(h.name for h in sq.grounding.matched[:8])
            extra = len(sq.grounding.matched) - 8
            if extra > 0:
                names += f", (+{extra} more)"
            tag = (
                f" expanded_from={sq.grounding.expanded_from}" if sq.grounding.expanded_from else ""
            )
            typer.echo(f"      grounded[{sq.grounding.confidence:.2f}]{tag}: {names}")
        if sq.notes:
            typer.echo(f"      note: {sq.notes}")

    typer.echo("\n# Stage 3 — final machine query")
    typer.echo(json.dumps(result.machine_query.to_payload(), indent=2, ensure_ascii=False))
    typer.echo(f"\nok={result.ok}  issues={[i.message for i in result.issues]}")

    if gold_row is not None:
        from oppp.eval.compare import compare_rows

        typer.echo("\n# Gold (SME) vs Agent filters")
        typer.echo(f"  {'field':18} {'status':8} gold  →  agent")
        for field, status, gold, agent in compare_rows(result, gold_row, get_service(service)):
            typer.echo(f"  {field:18} {status:8}")
            typer.echo(f"      gold : {gold or '—'}")
            typer.echo(f"      agent: {agent or '—'}")
        if gold_row.get("mapping_comment", "").strip():
            typer.echo(f"\n  SME note: {gold_row['mapping_comment'].strip()}")

    if execute and result.ok:
        from oppp.execute import execute_count

        ex = execute_count(result.machine_query, get_service(service))
        typer.echo("\n# Execution")
        if ex.ok:
            typer.echo(f"  datapoints retrieved = {ex.count_total}")
            if gold_row is not None and gold_row.get("s", "").strip():
                typer.echo(f"  expected             = {gold_row['s'].strip()}  (SME gold)")
        else:
            typer.echo(f"  failed: {ex.error}")
    elif execute and not result.ok:
        typer.echo("\n# Execution")
        typer.echo("  skipped: query has validation errors (not executed)")
    raise typer.Exit(0 if result.ok else 1)


@app.command()
def enhance(query: str, service: str = "safety", backend: str = "termite"):
    """Stage 0 only: show the enhanced query + entity annotations."""
    e = run_enhance(query, service, backend)
    typer.echo(json.dumps(e.model_dump(mode="json"), indent=2, ensure_ascii=False))


@app.command()
def decompose(query: str, service: str = "safety", backend: str = "llm"):
    """Stage 1 only: show the per-field components."""
    d = run_decompose(query, service, backend)
    typer.echo(json.dumps(d.model_dump(mode="json"), indent=2, ensure_ascii=False))


@app.command()
def aggregate(
    query: str,
    service: str = "safety",
    backend: str = typer.Option("llm", help="Aggregator: llm | deterministic."),
    decomposer: str = "llm",
    translator: str = "tool",
    normalizer: str = "fuzzy",
):
    """Stage 3 only: decompose+translate, then aggregate.

    Isolates the aggregator: hold the upstream stages fixed and compare backends.
    Defaults match `oppp eval` (llm / tool); pass the offline doubles
    (--decomposer gazetteer --translator deterministic) to run hermetically.
    """
    from oppp.stages.decompose import get_decomposer
    from oppp.stages.translate import get_translator

    svc = get_service(service)
    decomp = get_decomposer(decomposer).decompose(query, svc)
    decomp.query = query
    norm = get_normalizer_safe(normalizer)
    tr = get_translator(translator)
    subs = [s for s in (tr.translate(c, svc, norm) for c in decomp.filters) if s is not None]
    mq, issues = get_aggregator(backend).aggregate(decomp, subs, svc)
    typer.echo(json.dumps(mq.to_payload(), indent=2, ensure_ascii=False))
    typer.echo(f"\nissues={[i.message for i in issues]}", err=True)


def get_normalizer_safe(name: str):
    from oppp.normalize.base import get_normalizer

    return get_normalizer(name)


@app.command()
def field(
    field_name: str,
    fragment: str,
    service: str = "safety",
    normalizer: str = "fuzzy",
    component_type: str = "filter",
):
    """Stage 2 only: translate one field fragment to a machine subquery."""
    from oppp.models import Component, ComponentType

    comp = Component(
        field=field_name,
        nl_fragment=fragment,
        type=ComponentType(component_type),
        reason="cli-isolated",
        source="cli",
    )
    sq = translate_one(comp, service, normalizer)
    typer.echo(json.dumps(sq.model_dump(mode="json") if sq else None, indent=2, ensure_ascii=False))


@app.command()
def lookup(taxonomy: str, term: str, expand: bool = False, limit: int = 10):
    """Inspect the grounding layer: look a term up in a taxonomy."""
    idx = get_index(taxonomy)
    if expand and idx.is_class(term):
        hits = idx.expand_children(term)
    else:
        hits = idx.lookup(term, limit=limit)
    typer.echo(json.dumps([h.model_dump() for h in hits], indent=2, ensure_ascii=False))


@app.command()
def services():
    """List configured services and their fields."""
    svc = get_service("safety")
    typer.echo(f"safety: {len(svc.fields)} fields; closed={svc.closed_fields()}")


@app.command()
def dag(
    out: str = typer.Option(
        None, "--out", "-o", help="Output PNG path (default: docs/agent-dag.png)."
    ),
):
    """Export the agent's component DAG to a PNG (nodes=components, edges=relations)."""
    from oppp.dag import DEFAULT_OUT, render_png

    path = render_png(out or DEFAULT_OUT)
    typer.echo(f"wrote {path}")


@app.command(name="eval")
def eval_cmd(
    service: str = "safety",
    enhancer: str = typer.Option("termite", help="Stage 0 enhancer (default: termite)."),
    decomposer: str = typer.Option("llm", help="Stage 1 decomposer (default: llm)."),
    translator: str = typer.Option("tool", help="Stage 2 translator (default: tool)."),
    aggregator: str = typer.Option("llm", help="Stage 3 aggregator (default: llm)."),
    normalizer: str = "fuzzy",
    tolerance: float = typer.Option(0.10, help="Within-tolerance band for count match."),
    execute: bool = typer.Option(True, help="Execute queries against the API to get counts."),
    limit: int = typer.Option(0, help="0 = all gold cases."),
    show_cases: bool = typer.Option(False, help="Print per-case expected vs actual counts."),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the report (params + summary on top, then cases). Default .xlsx "
        "(needs the 'report' extra); .csv also supported.",
    ),
):
    """Evaluate against the per-step gold set (docs/sme_stage_cases.csv) by `counts`."""
    report = evaluate(
        service=service,
        enhancer=enhancer,
        decomposer=decomposer,
        translator=translator,
        aggregator=aggregator,
        normalizer=normalizer,
        tolerance=tolerance,
        execute=execute,
        limit=limit or None,
    )
    typer.echo(
        f"cases={len(report.cases)}  valid_rate={report.valid_rate:.2f}  "
        f"executed_rate={report.executed_rate:.2f}  "
        f"exact_count={report.exact_match_rate:.2f}  "
        f"within_{tolerance:g}={report.within_tol_rate:.2f}"
    )
    if show_cases or not execute:
        typer.echo("\nquery_number  expected   actual   ok  note")
        for c in report.cases:
            note = c.exec_error or (";".join(c.issues) if not c.ok else "")
            typer.echo(
                f"  {c.query_number:>3}        {str(c.expected):>7}  {str(c.actual):>7}   "
                f"{'Y' if c.ok else 'N'}   {note[:50]}"
            )

    if output:
        from oppp.eval.harness import write_report

        run_config = {
            "service": service,
            "enhancer": enhancer,
            "decomposer": decomposer,
            "translator": translator,
            "aggregator": aggregator,
            "normalizer": normalizer,
            "execute": execute,
            "limit": limit,
        }
        try:
            written = write_report(report, output, run_config=run_config)
        except (ValueError, RuntimeError) as e:
            typer.echo(f"\nCould not write report: {e}")
            raise typer.Exit(1) from e
        typer.echo(f"\nWrote report to {written}")


if __name__ == "__main__":
    app()
