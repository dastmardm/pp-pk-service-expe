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
from oppp.stages.decompose import decompose as run_decompose
from oppp.stages.translate import translate_one
from oppp.taxonomy.index import get_index

app = typer.Typer(no_args_is_help=True, help="Decomposed NL -> machine-query translator.")


@app.command()
def run(
    query: str,
    service: str = "safety",
    decomposer: str = "gazetteer",
    normalizer: str = "noop",
    payload_only: bool = typer.Option(False, help="Print only the API payload JSON."),
    execute: bool = typer.Option(False, "--execute", "-e", help="POST the query and print countTotal."),
):
    """Run the full pipeline on QUERY, showing every intermediate stage."""
    result = run_pipeline(query, service, decomposer=decomposer, normalizer=normalizer)
    if payload_only:
        typer.echo(json.dumps(result.machine_query.to_payload(), indent=2, ensure_ascii=False))
        raise typer.Exit(0 if result.ok else 1)

    typer.echo("# Input")
    typer.echo(f"  query     : {query!r}")
    typer.echo(
        f"  config    : service={service} decomposer={decomposer} "
        f"normalizer={normalizer} execute={execute}"
    )
    typer.echo()
    typer.echo("# Stage 1 — decomposition")
    for c in result.decomposition.components:
        bg = f" [{c.boolean_group.op.value}:{c.boolean_group.id}]" if c.boolean_group else ""
        typer.echo(f"  [{c.type.value:8}] {c.field:18} <- {c.nl_fragment!r}{bg}  ({c.source})")
        typer.echo(f"             reason: {c.reason}")

    typer.echo("\n# Stage 2 — machine subqueries (+ grounding)")
    for sq in result.subqueries:
        typer.echo(f"  {json.dumps(sq.to_constraint(), ensure_ascii=False)}")
        if sq.grounding and sq.grounding.matched:
            names = ", ".join(h.name for h in sq.grounding.matched[:8])
            extra = len(sq.grounding.matched) - 8
            if extra > 0:
                names += f", (+{extra} more)"
            tag = f" expanded_from={sq.grounding.expanded_from}" if sq.grounding.expanded_from else ""
            typer.echo(f"      grounded[{sq.grounding.confidence:.2f}]{tag}: {names}")
        if sq.notes:
            typer.echo(f"      note: {sq.notes}")

    typer.echo("\n# Stage 3 — final machine query")
    typer.echo(json.dumps(result.machine_query.to_payload(), indent=2, ensure_ascii=False))
    typer.echo(f"\nok={result.ok}  issues={[i.message for i in result.issues]}")

    if execute and result.ok:
        from oppp.execute import execute_count

        ex = execute_count(result.machine_query, get_service(service))
        if ex.ok:
            typer.echo(f"\n# Execution\n  countTotal = {ex.count_total}")
        else:
            typer.echo(f"\n# Execution\n  failed: {ex.error}")
    raise typer.Exit(0 if result.ok else 1)


@app.command()
def decompose(query: str, service: str = "safety", backend: str = "gazetteer"):
    """Stage 1 only: show the per-field components."""
    d = run_decompose(query, service, backend)
    typer.echo(json.dumps(d.model_dump(mode="json"), indent=2, ensure_ascii=False))


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
        field=field_name, nl_fragment=fragment, type=ComponentType(component_type),
        reason="cli-isolated", source="cli",
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


@app.command(name="eval")
def eval_cmd(
    service: str = "safety",
    decomposer: str = "gazetteer",
    normalizer: str = "fuzzy",
    tolerance: float = typer.Option(0.10, help="Within-tolerance band for count match."),
    execute: bool = typer.Option(True, help="Execute queries against the API to get counts."),
    limit: int = typer.Option(0, help="0 = all gold cases."),
    show_cases: bool = typer.Option(False, help="Print per-case expected vs actual counts."),
):
    """Evaluate against the SME gold set by expected result count (column `s`)."""
    report = evaluate(
        service=service, decomposer=decomposer, normalizer=normalizer,
        tolerance=tolerance, execute=execute, limit=limit or None,
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


if __name__ == "__main__":
    app()
