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

from oppp.models import (
    Decomposition,
    EnhancedQuery,
    ExpandedQuery,
    MachineSubquery,
    PipelineResult,
)
from oppp.normalize.base import get_normalizer
from oppp.services.base import get_service
from oppp.stages.aggregate import drop_empty_open_filters, get_aggregator
from oppp.stages.decompose import get_decomposer, reconcile_with_annotations
from oppp.stages.enhance import get_enhancer
from oppp.stages.expand import get_expander
from oppp.stages.translate import get_translator


def run_pipeline(
    query: str,
    service: str = "safety",
    *,
    expander: str = "llm",
    enhancer: str = "noop",
    decomposer: str = "llm",
    translator: str = "tool",
    aggregator: str = "llm",
    normalizer: str = "noop",
    probe_open_filters: bool = False,
) -> PipelineResult:
    """Full end-to-end run, returning every intermediate artifact.

    ``expander`` (Stage -1) rewrites the query into a clearer, abbreviation-expanded
    form before enhancement; the original is preserved on the result. Defaults to the
    'llm' backend, which degrades to pass-through when no LLM is configured.

    ``probe_open_filters`` (live paths only) asks the API to drop any open-set
    filter whose isolated server-side count is 0 — a value that matches no record
    and would silently zero the query. It costs one cheap count call per open-set
    filter, so it is off by default (offline/test runs stay hermetic) and enabled by
    the CLI ``run`` and the eval harness.
    """
    svc = get_service(service)
    norm = get_normalizer(normalizer)

    expanded: ExpandedQuery = get_expander(expander).expand(query, svc)
    enhanced: EnhancedQuery = get_enhancer(enhancer).enhance(expanded.text, svc)
    decomp: Decomposition = get_decomposer(decomposer).decompose(enhanced.text, svc)
    decomp.query = query  # keep the original user query as the canonical record
    reconcile_with_annotations(decomp, svc, enhanced.annotations)

    tr = get_translator(translator)
    subqueries: list[MachineSubquery] = []
    for comp in decomp.filters:
        sq = tr.translate(comp, svc, norm, enhanced.annotations)
        if sq is not None:
            subqueries.append(sq)

    probe_issues: list = []
    if probe_open_filters:
        subqueries = drop_empty_open_filters(subqueries, svc, probe_issues)

    machine_query, issues = get_aggregator(aggregator).aggregate(decomp, subqueries, svc)
    issues = probe_issues + issues

    return PipelineResult(
        query=query,
        service=service,
        expanded=expanded,
        enhanced=enhanced,
        decomposition=decomp,
        subqueries=subqueries,
        machine_query=machine_query,
        issues=issues,
    )


def build_langgraph(
    service: str = "safety",
    *,
    expander: str = "llm",
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
    exp = get_expander(expander)
    enh = get_enhancer(enhancer)
    dec = get_decomposer(decomposer)
    tr = get_translator(translator)
    agg = get_aggregator(aggregator)

    class State(TypedDict, total=False):
        query: str
        expanded: ExpandedQuery
        enhanced: EnhancedQuery
        decomposition: Decomposition
        subqueries: list[MachineSubquery]
        result: PipelineResult

    def n_expand(state: State) -> State:
        state["expanded"] = exp.expand(state["query"], svc)
        return state

    def n_enhance(state: State) -> State:
        state["enhanced"] = enh.enhance(state["expanded"].text, svc)
        return state

    def n_decompose(state: State) -> State:
        d = dec.decompose(state["enhanced"].text, svc)
        d.query = state["query"]
        reconcile_with_annotations(d, svc, state["enhanced"].annotations)
        state["decomposition"] = d
        return state

    def n_translate(state: State) -> State:
        anns = state["enhanced"].annotations
        subs = [tr.translate(c, svc, norm, anns) for c in state["decomposition"].filters]
        state["subqueries"] = [s for s in subs if s is not None]
        return state

    def n_aggregate(state: State) -> State:
        mq, issues = agg.aggregate(state["decomposition"], state["subqueries"], svc)
        state["result"] = PipelineResult(
            query=state["query"],
            service=service,
            expanded=state["expanded"],
            enhanced=state["enhanced"],
            decomposition=state["decomposition"],
            subqueries=state["subqueries"],
            machine_query=mq,
            issues=issues,
        )
        return state

    g = StateGraph(State)
    g.add_node("expand", n_expand)
    g.add_node("enhance", n_enhance)
    g.add_node("decompose", n_decompose)
    g.add_node("translate", n_translate)
    g.add_node("aggregate", n_aggregate)
    g.add_edge(START, "expand")
    g.add_edge("expand", "enhance")
    g.add_edge("enhance", "decompose")
    g.add_edge("decompose", "translate")
    g.add_edge("translate", "aggregate")
    g.add_edge("aggregate", END)
    return g.compile()
