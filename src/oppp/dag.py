"""Render the agent's component DAG to a PNG.

Nodes are the key components of the agent (the four pipeline stages plus the
shared resources they depend on); edges are the relationships between them:

  * data-flow edges (solid)   — the NL query threads stage to stage to the final
    machine query;
  * dependency edges (dashed) — a stage uses a shared resource (ServiceConfig,
    the LLM client, the taxonomy index).

The pluggable backends under each stage are read from the live registries, so
the diagram stays in sync with what is actually registered.

Rendering uses matplotlib (pure-pip; no system Graphviz needed). Install with the
'viz' extra: ``pip install 'oppp[viz]'``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from oppp.stages.aggregate import aggregator_registry
from oppp.stages.decompose import decomposer_registry
from oppp.stages.enhance import enhancer_registry
from oppp.stages.translate import translator_registry

# Default output location (per project convention, docs/ holds written artifacts).
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "docs" / "agent-dag.png"


@dataclass
class Node:
    id: str
    label: str
    x: float
    y: float
    backends: list[str] = field(default_factory=list)
    kind: str = "stage"  # stage | io | resource


@dataclass
class Edge:
    src: str
    dst: str
    kind: str = "flow"  # flow (solid, data) | dep (dashed, dependency)
    label: str = ""


def build_dag() -> tuple[list[Node], list[Edge]]:
    """Describe the agent as nodes + edges, with backends pulled from registries."""
    # Main data-flow spine (left -> right), y = 0. Wide x-step so the flow labels
    # fit in the gaps between boxes.
    spine = [
        Node("query", "NL query", 0, 0, kind="io"),
        Node("enhance", "Stage 0\nEnhance", 3.0, 0, enhancer_registry.names()),
        Node("decompose", "Stage 1\nDecompose", 6.0, 0, decomposer_registry.names()),
        Node("translate", "Stage 2\nTranslate", 9.0, 0, translator_registry.names()),
        Node("aggregate", "Stage 3\nAggregate", 12.0, 0, aggregator_registry.names()),
        Node("machine_query", "MachineQuery\n(API payload)", 15.0, 0, kind="io"),
    ]
    # Shared resources the stages depend on.
    resources = [
        Node("llm", "LLM client\n(oppp.llm)", 9.0, 2.6, kind="resource"),
        Node("taxonomy", "Taxonomy index\n(CSV grounding)", 9.0, -2.6, kind="resource"),
        Node("service", "ServiceConfig\n(fields / facets)", 3.0, -2.6, kind="resource"),
    ]
    nodes = spine + resources

    edges = [
        # data flow
        Edge("query", "enhance"),
        Edge("enhance", "decompose", label="enhanced"),
        Edge("decompose", "translate", label="components"),
        Edge("translate", "aggregate", label="subqueries"),
        Edge("aggregate", "machine_query"),
        # dependencies (dashed)
        Edge("llm", "decompose", "dep"),
        Edge("llm", "translate", "dep"),
        Edge("llm", "aggregate", "dep"),
        Edge("taxonomy", "translate", "dep"),
        Edge("taxonomy", "decompose", "dep"),  # gazetteer double
        Edge("service", "enhance", "dep"),
        Edge("service", "decompose", "dep"),
        Edge("service", "translate", "dep"),
        Edge("service", "aggregate", "dep"),
    ]
    return nodes, edges


_COLORS = {
    "stage": ("#e3f0ff", "#2b6cb0"),
    "io": ("#f0f0f0", "#555555"),
    "resource": ("#fff4e0", "#c05621"),
}


def render_png(out: Path | str = DEFAULT_OUT) -> Path:
    """Render the agent DAG to `out` (PNG). Returns the written path."""
    try:
        import matplotlib

        matplotlib.use("Agg")  # headless; no display needed
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    except ImportError as e:  # pragma: no cover - optional extra
        raise RuntimeError("install the 'viz' extra: pip install 'oppp[viz]'") from e

    nodes, edges = build_dag()
    by_id = {n.id: n for n in nodes}

    fig, ax = plt.subplots(figsize=(19, 8))
    box_w, box_h = 1.7, 1.0

    def anchor(node: Node, side: str) -> tuple[float, float]:
        if side == "right":
            return node.x + box_w / 2, node.y
        if side == "left":
            return node.x - box_w / 2, node.y
        if side == "top":
            return node.x, node.y + box_h / 2
        return node.x, node.y - box_h / 2  # bottom

    # edges first (so boxes sit on top)
    for e in edges:
        s, d = by_id[e.src], by_id[e.dst]
        if e.kind == "flow":
            p0, p1 = anchor(s, "right"), anchor(d, "left")
            style = dict(color="#2b6cb0", lw=2.0, linestyle="-")
        else:
            # dependency: leave from the side facing the target stage
            side_s = "bottom" if s.y > d.y else "top"
            side_d = "top" if s.y > d.y else "bottom"
            p0, p1 = anchor(s, side_s), anchor(d, side_d)
            style = dict(color="#c05621", lw=1.2, linestyle=(0, (4, 3)))
        ax.add_patch(FancyArrowPatch(
            p0, p1, arrowstyle="-|>", mutation_scale=16,
            shrinkA=2, shrinkB=2, **style,
        ))
        if e.label:
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            ax.text(mx, my + 0.18, e.label, ha="center", va="bottom",
                    fontsize=8, color="#2b6cb0", style="italic")

    # nodes
    for n in nodes:
        face, edge = _COLORS[n.kind]
        ax.add_patch(FancyBboxPatch(
            (n.x - box_w / 2, n.y - box_h / 2), box_w, box_h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=face, edgecolor=edge, linewidth=1.6, zorder=3,
        ))
        ax.text(n.x, n.y + (0.16 if n.backends else 0), n.label, ha="center",
                va="center", fontsize=11, fontweight="bold", color=edge, zorder=4)
        if n.backends:
            ax.text(n.x, n.y - 0.28, "{" + " | ".join(n.backends) + "}",
                    ha="center", va="center", fontsize=8, color=edge, zorder=4)

    ax.text(7.5, 4.0, "PharmaPendium NL → Machine-Query Agent",
            ha="center", fontsize=15, fontweight="bold")
    ax.text(7.5, 3.6, "solid = data flow   ·   dashed = depends on   ·   "
            "{ } = pluggable backends (default first)",
            ha="center", fontsize=10, color="#666666")

    ax.set_xlim(-1.3, 16.3)
    ax.set_ylim(-3.9, 4.4)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out
