"""Pipeline orchestration: fixed stage path for the PK service.

Fixed stage order (CONST-1, REQ-020):
  Stage -1: expand  (LLM abbreviation expansion)
  Stage  0: enhance (TERMite NER)
  Stage  1: decompose + reconcile (LLM segmentation)
  Stage 2A: translate closed-set input filters
  Stage 3A: aggregate -> MachineQuery -> execute count (or rows)
  [row mode]
  Stage 2B: translate runtime closed-set filters
  Stage 3B: assemble final row result
  Stage 2C: apply open-set post-filters

No selectable backends — the stage implementations are fixed. Hermetic tests
inject fakes at the service/model boundary, not by swapping stage backends.
"""

from __future__ import annotations

from oppp.models import (
    Decomposition,
    EnhancedQuery,
    ExpandedQuery,
    MachineSubquery,
    PipelineResult,
)
from oppp.normalize import normalize as _normalize_field
from oppp.services.base import get_service
from oppp.stages.aggregate import drop_empty_open_filters, get_aggregator
from oppp.stages.decompose import get_decomposer, reconcile_with_annotations
from oppp.stages.enhance import get_enhancer
from oppp.stages.expand import get_expander
from oppp.stages.translate import get_translator


def run_pipeline(
    query: str,
    service: str = "pk",
    *,
    expander: str = "llm",
    enhancer: str = "termite",
    decomposer: str = "llm",
    translator: str = "tool",
    aggregator: str = "llm",
    normalizer: str = "noop",
    probe_open_filters: bool = False,
) -> PipelineResult:
    """Full end-to-end run, returning every intermediate artifact.

    The stage implementations are fixed (CONST-1). The keyword arguments are
    retained only so existing call sites and the offline test doubles still work
    (tests pass expander='noop', decomposer='gazetteer', etc. to stay hermetic).
    Production callers should use the defaults.

    ``probe_open_filters`` (live paths only) asks the API to drop any open-set
    filter whose isolated server-side count is 0 — a value that matches no record
    and would silently zero the query. Off by default; enabled by the CLI and eval.
    """
    from oppp.normalize.base import get_normalizer

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


def build_langgraph(service: str = "pk"):
    """Optional LangGraph wiring of the fixed stages (needs the 'llm' extra)."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("install the 'llm' extra: pip install 'oppp[llm]'") from e

    from typing import TypedDict

    from oppp.normalize.base import get_normalizer

    svc = get_service(service)
    norm = get_normalizer("noop")
    exp = get_expander("llm")
    enh = get_enhancer("termite")
    dec = get_decomposer("llm")
    tr = get_translator("tool")
    agg = get_aggregator("llm")

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
