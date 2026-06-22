"""Render the agent's component DAG to a PNG.

Besides the four pipeline-stage spine the diagram surfaces the mechanisms that
decide a query's correctness: Stage 2 routes each field to one of two handlers by
its **bucket**, and Stage 3 runs the guards that keep a bad value from silently
zeroing the whole query:

  * **closed-vocab** fields are grounded against a taxonomy CSV (exact → fuzzy →
    LLM-map, re-grounded), with class/MedDRA-family rollup; an ungroundable term is
    *dropped*, never emitted (CONST-1, via `_drop_ungroundable`);
  * **open-set** fields (free text, no CSV) strip relational glue and are then
    *probed against the API* — a filter whose isolated server-side count is 0 is
    dropped (`drop_empty_open_filters`) rather than left to zero the AND.

Edges:
  * data-flow (solid)        — the query threads stage to stage to the payload;
  * routing (dotted)         — a stage fans out to its handlers / guard functions;
  * dependency (dashed)      — a stage/handler uses a shared resource (CSV, LLM, API).

Pluggable backends under each stage are read from the live registries, so the
diagram stays in sync with what is actually registered.

Rendering uses matplotlib (pure-pip; no system Graphviz needed). Install with the
'viz' extra: ``pip install 'oppp[viz]'``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from oppp.stages.aggregate import aggregator_registry
from oppp.stages.decompose import decomposer_registry
from oppp.stages.enhance import enhancer_registry
from oppp.stages.expand import expander_registry
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
    """Describe the agent as nodes + edges, with backends pulled from registries."""
    # ---- main data-flow spine (left -> right), y = 0 ----------------------------
    spine = [
        Node("query", "NL query", 0, 0, kind="io"),
        Node(
            "expand", "Stage -1\nExpand", 2.7, 0, expander_registry.names(),
            sub="clarify + spell out abbreviations",
        ),
        Node(
            "enhance", "Stage 0\nEnhance", 5.5, 0, enhancer_registry.names(),
            sub="NER → EntityAnnotation",
        ),
        Node(
            "decompose", "Stage 1\nDecompose", 8.3, 0, decomposer_registry.names(),
            sub="segment → Components",
        ),
        Node(
            "translate", "Stage 2\nTranslate", 11.1, 0, translator_registry.names(),
            sub="route by field bucket",
        ),
        Node(
            "aggregate", "Stage 3\nAggregate", 13.9, 0, aggregator_registry.names(),
            sub="boolean tree + guards",
        ),
        Node("machine_query", "MachineQuery\n(API payload)", 16.9, 0, kind="io"),
    ]

    s1: list[Node] = []

    # ---- Stage 2 detail: the per-bucket field handlers (below the spine) ---------
    # The translator routes each component to a handler keyed on its FieldSpec bucket.
    s2 = [
        Node(
            "closed", "closed-vocab", 9.3, -2.6, kind="handler", w=3.0, h=1.2,
            sub="translate closed\nCSV grounding · class/MedDRA rollup",
        ),
        Node(
            "open", "open-set (free text)", 12.7, -2.6, kind="handler", w=3.0, h=1.2,
            sub="translate open · enum/boolean\nconnective-strip; server-side zero-count drop",
        ),
    ]

    s3: list[Node] = []

    # ---- shared resources --------------------------------------------------------
    resources = [
        Node("termite", "TERMite NER", 5.5, 2.3, kind="resource", w=2.0, sub="utils/termite"),
        Node("llm", "LLM client\n(oppp.llm)", 11.1, 3.4, kind="resource", w=2.0),
        Node(
            "taxonomy", "Taxonomy CSVs\n(closed-vocab)", 9.3, -4.8, kind="resource", w=2.6,
            sub="drugs · effects · species · …",
        ),
    ]

    nodes = spine + s1 + s2 + s3 + resources

    edges = [
        # ---- data flow (solid) ----
        Edge("query", "expand"),
        Edge("expand", "enhance", label="expanded query"),
        Edge("enhance", "decompose", label="enhanced + annotations"),
        Edge("decompose", "translate", label="components"),
        Edge("translate", "aggregate", label="subqueries"),
        Edge("aggregate", "machine_query"),
        # ---- Stage 2 routing: translate fans out to the per-bucket handlers ----
        Edge("translate", "closed", "route"),
        Edge("translate", "open", "route"),
        # ---- dependencies (dashed) ----
        Edge("llm", "expand", "dep"),
        Edge("termite", "enhance", "dep"),
        Edge("llm", "decompose", "dep"),
        Edge("llm", "translate", "dep"),
        Edge("llm", "aggregate", "dep"),
        Edge("taxonomy", "closed", "dep"),
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

    fig, ax = plt.subplots(figsize=(24, 13))

    def anchor(node: Node, side: str) -> tuple[float, float]:
        if side == "right":
            return node.x + node.w / 2, node.y
        if side == "left":
            return node.x - node.w / 2, node.y
        if side == "top":
            return node.x, node.y + node.h / 2
        return node.x, node.y - node.h / 2  # bottom

    def best_sides(s: Node, d: Node) -> tuple[str, str]:
        """Pick anchor sides by relative position so arrows leave/enter cleanly."""
        dx, dy = d.x - s.x, d.y - s.y
        if abs(dx) >= abs(dy):
            return ("right", "left") if dx >= 0 else ("left", "right")
        return ("top", "bottom") if dy >= 0 else ("bottom", "top")

    _STYLES = {
        "flow": dict(color="#2b6cb0", lw=2.2, linestyle="-"),
        "route": dict(color="#6b46c1", lw=1.3, linestyle=(0, (1, 2))),
        "dep": dict(color="#c05621", lw=1.1, linestyle=(0, (4, 3))),
    }

    # edges first (so boxes sit on top)
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

    # nodes
    for n in nodes:
        face, edge = _COLORS[n.kind]
        ax.add_patch(
            FancyBboxPatch(
                (n.x - n.w / 2, n.y - n.h / 2), n.w, n.h,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=face, edgecolor=edge, linewidth=1.5, zorder=3,
            )
        )
        # title (nudge up when there is a backends or sub line below it)
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
        if n.backends:
            ax.text(
                n.x, extra_y, "{" + " | ".join(n.backends) + "}",
                ha="center", va="center", fontsize=7.6, color=edge, zorder=4,
            )

    # title + legend
    ax.text(
        8.5, 6.5, "PharmaPendium NL → Machine-Query Agent",
        ha="center", fontsize=16, fontweight="bold",
    )
    ax.text(
        8.5, 6.05,
        "solid = data flow   ·   dotted = routes to handler/function   ·   "
        "dashed = depends on   ·   { } = pluggable backends (default first)",
        ha="center", fontsize=10, color="#666666",
    )
    # colour key
    key = [
        ("stage", "pipeline stage"),
        ("handler", "field-bucket handler"),
        ("detail", "function / mechanism"),
        ("resource", "shared resource"),
        ("io", "input / output"),
    ]
    kx = 1.0
    for kind, lbl in key:
        face, edge = _COLORS[kind]
        ax.add_patch(
            FancyBboxPatch(
                (kx, 5.5), 0.34, 0.22, boxstyle="round,pad=0.01,rounding_size=0.05",
                facecolor=face, edgecolor=edge, linewidth=1.2, zorder=3,
            )
        )
        ax.text(kx + 0.42, 5.61, lbl, ha="left", va="center", fontsize=8.5, color="#333333")
        kx += 2.7

    ax.set_xlim(-1.6, 18.6)
    ax.set_ylim(-5.8, 7.0)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out
