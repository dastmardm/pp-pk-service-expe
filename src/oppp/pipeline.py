"""Pipeline orchestration: decompose -> translate -> aggregate.

The default runner is a plain sequential function (no heavy deps). A LangGraph
graph is offered as an optional backend with the same signature, so the pipeline
can run in either; each stage is independently invokable for evaluation.
"""

from __future__ import annotations

from oppp.models import Decomposition, MachineSubquery, PipelineResult
from oppp.normalize.base import get_normalizer
from oppp.services.base import get_service
from oppp.stages.aggregate import aggregate
from oppp.stages.decompose import get_decomposer
from oppp.stages.translate import translate_component


def run_pipeline(
    query: str,
    service: str = "safety",
    *,
    decomposer: str = "gazetteer",
    normalizer: str = "noop",
) -> PipelineResult:
    """Full end-to-end run, returning every intermediate artifact."""
    svc = get_service(service)
    norm = get_normalizer(normalizer)

    decomp: Decomposition = get_decomposer(decomposer).decompose(query, svc)

    subqueries: list[MachineSubquery] = []
    for comp in decomp.filters:
        sq = translate_component(comp, svc, norm)
        if sq is not None:
            subqueries.append(sq)

    machine_query, issues = aggregate(decomp, subqueries, svc)

    return PipelineResult(
        query=query,
        service=service,
        decomposition=decomp,
        subqueries=subqueries,
        machine_query=machine_query,
        issues=issues,
    )


def build_langgraph(service: str = "safety", *, decomposer: str = "gazetteer",
                    normalizer: str = "noop"):
    """Optional LangGraph wiring of the same three stages (needs the 'llm' extra)."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("install the 'llm' extra: pip install 'oppp[llm]'") from e

    from typing import TypedDict

    svc = get_service(service)
    norm = get_normalizer(normalizer)
    decomp_backend = get_decomposer(decomposer)

    class State(TypedDict, total=False):
        query: str
        decomposition: Decomposition
        subqueries: list[MachineSubquery]
        result: PipelineResult

    def n_decompose(state: State) -> State:
        state["decomposition"] = decomp_backend.decompose(state["query"], svc)
        return state

    def n_translate(state: State) -> State:
        subs = [translate_component(c, svc, norm) for c in state["decomposition"].filters]
        state["subqueries"] = [s for s in subs if s is not None]
        return state

    def n_aggregate(state: State) -> State:
        mq, issues = aggregate(state["decomposition"], state["subqueries"], svc)
        state["result"] = PipelineResult(
            query=state["query"], service=service,
            decomposition=state["decomposition"], subqueries=state["subqueries"],
            machine_query=mq, issues=issues,
        )
        return state

    g = StateGraph(State)
    g.add_node("decompose", n_decompose)
    g.add_node("translate", n_translate)
    g.add_node("aggregate", n_aggregate)
    g.add_edge(START, "decompose")
    g.add_edge("decompose", "translate")
    g.add_edge("translate", "aggregate")
    g.add_edge("aggregate", END)
    return g.compile()
