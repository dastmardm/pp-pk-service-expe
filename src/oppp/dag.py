"""Render the agent's fixed 8-stage DAG to a PNG.

The pipeline has a fixed stage path (CONST-1):
  Stage -1: Expand (LLM abbreviation expansion)
  Stage  0: Enhance (TERMite NER)
  Stage  1: Decompose + Reconcile (LLM segmentation)
  Stage 2A: Translate input filters (closed-set grounding)
  Stage 3A: Aggregate -> MachineQuery
  Stage 2B: Translate runtime closed-set filters
  Stage 3B: Assemble final row result
  Stage 2C: Apply open-set post-filters

Rendering uses matplotlib (pure-pip; no system Graphviz needed). Install with the
'viz' extra: ``pip install 'oppp[viz]'``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Fixed 8-stage labels (CONST-1 — no pluggable backends).
STAGE_LABELS = [
    "Stage -1\nExpand",
    "Stage 0\nEnhance",
    "Stage 1\nDecompose",
    "Stage 2A\nTranslate input",
    "Stage 3A\nAggregate",
    "Stage 2B\nRuntime translate",
    "Stage 3B\nAssemble rows",
    "Stage 2C\nPost-filter",
]

# Default output location (per project convention, docs/ holds written artifacts).
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "docs" / "agent-dag.png"


@dataclass
class Node:
    id: str
    label: str
    x: float
    y: float
    backends: list[str] = field(default_factory=list)
    kind: str = "stage"  # stage | io | resource | handler | detail
    w: float = 1.9
    h: float = 1.0
    sub: str = ""  # small secondary line (functions / notes) under the label


@dataclass
class Edge:
    src: str
    dst: str
    kind: str = "flow"  # flow (solid) | route (dotted) | dep (dashed)
    label: str = ""


def build_dag() -> tuple[list[Node], list[Edge]]:
    """Describe the fixed-stage agent as nodes + edges."""
    # ---- main data-flow spine (left -> right), y = 0 ----------------------------
    spine = [
        Node("query", "NL query", 0, 0, kind="io"),
        Node("expand", "Stage -1\nExpand", 2.5, 0, sub="clarify + spell out abbreviations"),
        Node("enhance", "Stage 0\nEnhance", 5.0, 0, sub="TERMite NER → EntityAnnotation"),
        Node("decompose", "Stage 1\nDecompose", 7.5, 0, sub="segment → Components"),
        Node("translate_a", "Stage 2A\nTranslate input", 10.0, 0, sub="closed-set grounding"),
        Node("aggregate_a", "Stage 3A\nAggregate", 12.5, 0, sub="boolean tree → MachineQuery"),
        Node("machine_query", "MachineQuery\n(API payload)", 15.2, 0, kind="io"),
    ]

    row_mode = [
        Node(
            "translate_b", "Stage 2B\nRuntime translate", 10.0, -2.5,
            sub="runtime closed-set",
        ),
        Node("assemble_b", "Stage 3B\nAssemble rows", 12.5, -2.5, sub="row result"),
        Node("postfilter", "Stage 2C\nPost-filter", 15.2, -2.5, sub="open-set filter on rows"),
    ]

    # ---- shared resources --------------------------------------------------------
    resources = [
        Node("termite", "TERMite NER", 5.0, 2.3, kind="resource", w=2.0),
        Node("llm", "LLM client\n(oppp.llm)", 9.0, 3.2, kind="resource", w=2.0),
        Node(
            "taxonomy", "Taxonomy CSVs\n(closed-vocab)", 10.0, -4.5, kind="resource", w=2.6,
            sub="drugs · species · routes · …",
        ),
    ]

    nodes = spine + row_mode + resources

    edges = [
        # ---- data flow (solid) ----
        Edge("query", "expand"),
        Edge("expand", "enhance", label="expanded"),
        Edge("enhance", "decompose", label="enhanced + annotations"),
        Edge("decompose", "translate_a", label="components"),
        Edge("translate_a", "aggregate_a", label="subqueries"),
        Edge("aggregate_a", "machine_query"),
        # ---- row-mode path ----
        Edge("machine_query", "translate_b", "route", label="row mode"),
        Edge("translate_b", "assemble_b"),
        Edge("assemble_b", "postfilter"),
        # ---- dependencies (dashed) ----
        Edge("llm", "expand", "dep"),
        Edge("termite", "enhance", "dep"),
        Edge("llm", "decompose", "dep"),
        Edge("llm", "translate_a", "dep"),
        Edge("llm", "aggregate_a", "dep"),
        Edge("taxonomy", "translate_a", "dep"),
    ]
    return nodes, edges


_COLORS = {
    "stage": ("#e3f0ff", "#2b6cb0"),
    "io": ("#f0f0f0", "#555555"),
    "resource": ("#fff4e0", "#c05621"),
    "handler": ("#e6f6ec", "#2f855a"),
    "detail": ("#f3eefb", "#6b46c1"),
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

    fig, ax = plt.subplots(figsize=(22, 11))

    def anchor(node: Node, side: str) -> tuple[float, float]:
        if side == "right":
            return node.x + node.w / 2, node.y
        if side == "left":
            return node.x - node.w / 2, node.y
        if side == "top":
            return node.x, node.y + node.h / 2
        return node.x, node.y - node.h / 2  # bottom

    def best_sides(s: Node, d: Node) -> tuple[str, str]:
        dx, dy = d.x - s.x, d.y - s.y
        if abs(dx) >= abs(dy):
            return ("right", "left") if dx >= 0 else ("left", "right")
        return ("top", "bottom") if dy >= 0 else ("bottom", "top")

    _STYLES = {
        "flow": dict(color="#2b6cb0", lw=2.2, linestyle="-"),
        "route": dict(color="#6b46c1", lw=1.3, linestyle=(0, (1, 2))),
        "dep": dict(color="#c05621", lw=1.1, linestyle=(0, (4, 3))),
    }

    for e in edges:
        s, d = by_id[e.src], by_id[e.dst]
        if e.kind == "flow":
            p0, p1 = anchor(s, "right"), anchor(d, "left")
        else:
            ss, ds = best_sides(s, d)
            p0, p1 = anchor(s, ss), anchor(d, ds)
        ax.add_patch(
            FancyArrowPatch(
                p0, p1, arrowstyle="-|>", mutation_scale=15, shrinkA=2, shrinkB=2,
                zorder=1, **_STYLES[e.kind],
            )
        )
        if e.label:
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            ax.text(
                mx, my + 0.16, e.label, ha="center", va="bottom",
                fontsize=8, color="#2b6cb0", style="italic", zorder=5,
            )

    for n in nodes:
        face, edge = _COLORS[n.kind]
        ax.add_patch(
            FancyBboxPatch(
                (n.x - n.w / 2, n.y - n.h / 2), n.w, n.h,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=face, edgecolor=edge, linewidth=1.5, zorder=3,
            )
        )
        has_below = bool(n.backends) or bool(n.sub)
        title_fs = 11 if n.kind in ("stage", "io") else 9.5
        ax.text(
            n.x, n.y + (0.18 if has_below else 0), n.label,
            ha="center", va="center", fontsize=title_fs,
            fontweight="bold", color=edge, zorder=4,
        )
        extra_y = n.y - 0.20
        if n.sub:
            ax.text(
                n.x, extra_y, n.sub, ha="center", va="center",
                fontsize=7.2, color=edge, style="italic", zorder=4,
            )
            extra_y -= 0.26 * (1 + n.sub.count("\n"))

    ax.text(
        8.0, 5.5, "PharmaPendium PK NL → Machine-Query Agent (fixed pipeline)",
        ha="center", fontsize=15, fontweight="bold",
    )
    ax.text(
        8.0, 5.05,
        "solid = data flow   ·   dotted = row-mode branch   ·   dashed = depends on",
        ha="center", fontsize=10, color="#666666",
    )

    ax.set_xlim(-1.4, 17.0)
    ax.set_ylim(-5.5, 6.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out
