"""Pipeline orchestration: enhance -> decompose -> translate -> aggregate.

Every stage is pluggable by name and independently invokable, so any one can be
swapped or evaluated in isolation:

  * enhance    (optional) NL query -> enhanced query    [noop | termite]
  * decompose  enhanced query -> per-field components    [llm | gazetteer]
  * translate  one component -> one machine subquery      [tool]
  * aggregate  components + subqueries -> machine query    [llm | deterministic]

Production defaults are the LLM-based design (decompose + aggregate via LLM,
no-op enhancer). Hermetic runs pin the offline doubles:
``decomposer='gazetteer', aggregator='deterministic'``.
"""

from __future__ import annotations

from oppp.models import Decomposition, EnhancedQuery, MachineSubquery, PipelineResult
from oppp.normalize.base import get_normalizer
from oppp.services.base import get_service
from oppp.stages.aggregate import get_aggregator
from oppp.stages.decompose import get_decomposer
from oppp.stages.enhance import get_enhancer
from oppp.stages.translate import get_translator


def run_pipeline(
    query: str,
    service: str = "safety",
    *,
    enhancer: str = "noop",
    decomposer: str = "llm",
    translator: str = "tool",
    aggregator: str = "llm",
    normalizer: str = "noop",
) -> PipelineResult:
    """Full end-to-end run, returning every intermediate artifact."""
    svc = get_service(service)
    norm = get_normalizer(normalizer)

    enhanced: EnhancedQuery = get_enhancer(enhancer).enhance(query, svc)
    decomp: Decomposition = get_decomposer(decomposer).decompose(enhanced.text, svc)
    decomp.query = query  # keep the original user query as the canonical record

    tr = get_translator(translator)
    subqueries: list[MachineSubquery] = []
    for comp in decomp.filters:
        sq = tr.translate(comp, svc, norm)
        if sq is not None:
            subqueries.append(sq)

    machine_query, issues = get_aggregator(aggregator).aggregate(decomp, subqueries, svc)

    return PipelineResult(
        query=query,
        service=service,
        enhanced=enhanced,
        decomposition=decomp,
        subqueries=subqueries,
        machine_query=machine_query,
        issues=issues,
    )


def build_langgraph(
    service: str = "safety",
    *,
    enhancer: str = "noop",
    decomposer: str = "llm",
    translator: str = "tool",
    aggregator: str = "llm",
    normalizer: str = "noop",
):
    """Optional LangGraph wiring of the same stages (needs the 'llm' extra)."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("install the 'llm' extra: pip install 'oppp[llm]'") from e

    from typing import TypedDict

    svc = get_service(service)
    norm = get_normalizer(normalizer)
    enh = get_enhancer(enhancer)
    dec = get_decomposer(decomposer)
    tr = get_translator(translator)
    agg = get_aggregator(aggregator)

    class State(TypedDict, total=False):
        query: str
        enhanced: EnhancedQuery
        decomposition: Decomposition
        subqueries: list[MachineSubquery]
        result: PipelineResult

    def n_enhance(state: State) -> State:
        state["enhanced"] = enh.enhance(state["query"], svc)
        return state

    def n_decompose(state: State) -> State:
        d = dec.decompose(state["enhanced"].text, svc)
        d.query = state["query"]
        state["decomposition"] = d
        return state

    def n_translate(state: State) -> State:
        subs = [tr.translate(c, svc, norm) for c in state["decomposition"].filters]
        state["subqueries"] = [s for s in subs if s is not None]
        return state

    def n_aggregate(state: State) -> State:
        mq, issues = agg.aggregate(state["decomposition"], state["subqueries"], svc)
        state["result"] = PipelineResult(
            query=state["query"],
            service=service,
            enhanced=state["enhanced"],
            decomposition=state["decomposition"],
            subqueries=state["subqueries"],
            machine_query=mq,
            issues=issues,
        )
        return state

    g = StateGraph(State)
    g.add_node("enhance", n_enhance)
    g.add_node("decompose", n_decompose)
    g.add_node("translate", n_translate)
    g.add_node("aggregate", n_aggregate)
    g.add_edge(START, "enhance")
    g.add_edge("enhance", "decompose")
    g.add_edge("decompose", "translate")
    g.add_edge("translate", "aggregate")
    g.add_edge("aggregate", END)
    return g.compile()
