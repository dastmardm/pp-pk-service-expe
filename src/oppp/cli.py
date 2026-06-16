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
):
    """Run the full pipeline on QUERY."""
    result = run_pipeline(query, service, decomposer=decomposer, normalizer=normalizer)
    if payload_only:
        typer.echo(json.dumps(result.machine_query.to_payload(), indent=2, ensure_ascii=False))
        raise typer.Exit(0 if result.ok else 1)

    typer.echo("# Decomposition")
    for c in result.decomposition.components:
        bg = f" [{c.boolean_group.op.value}:{c.boolean_group.id}]" if c.boolean_group else ""
        typer.echo(f"  [{c.type.value:8}] {c.field:18} <- {c.nl_fragment!r}{bg}  ({c.source})")
        typer.echo(f"             reason: {c.reason}")
    typer.echo("\n# Machine subqueries")
    for sq in result.subqueries:
        typer.echo(f"  {json.dumps(sq.to_constraint(), ensure_ascii=False)}")
    typer.echo("\n# Machine query")
    typer.echo(json.dumps(result.machine_query.to_payload(), indent=2, ensure_ascii=False))
    typer.echo(f"\nok={result.ok}  issues={[i.message for i in result.issues]}")
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
    limit: int = typer.Option(0, help="0 = all gold cases."),
):
    """Evaluate against the SME gold set."""
    report = evaluate(
        service=service, decomposer=decomposer, normalizer=normalizer,
        limit=limit or None,
    )
    typer.echo(f"cases={len(report.cases)}  valid_rate={report.valid_rate:.2f}  "
               f"routing_recall={report.routing_recall:.2f}  macro_f1={report.macro_f1:.2f}")
    typer.echo("\nper-field F1:")
    for fname, f1 in report.field_f1().items():
        typer.echo(f"  {fname:18} {f1:.2f}")


if __name__ == "__main__":
    app()
