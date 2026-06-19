"""Fill the per-stage columns of docs/sme_stage_cases.csv from the LIVE pipeline.

Unlike utils/build_sme_stage_cases.py (which hand-authors the SME *intent*), this
tool runs each ``nl query`` through the actual pluggable pipeline and rewrites the
five per-stage columns from what the stages really produce:

    termite | decompose | translate | aggregate | machine query

``nl query`` and ``counts`` are copied through verbatim — the pipeline is run but
never executed against the PharmaPendium API, so counts are left untouched.

Default backends are the production stack (termite / llm / tool / llm), so the
``termite`` column is populated and the real LLM stages are exercised. Every
backend is overridable by flag, e.g. to run fully offline:

    python utils/fill_stage_cases_from_pipeline.py \
        --enhancer noop --decomposer gazetteer \
        --translator deterministic --aggregator deterministic

The output is the input by default (overwrite in place); a timestamped ``.bak`` is
written first unless --no-backup is given.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
# Make the package importable even without an editable install (src/ layout).
SRC = ROOT / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DEFAULT_CSV = ROOT / "docs" / "sme_stage_cases.csv"

# Columns regenerated from the pipeline (nl query + counts are preserved as-is).
HEADER = ["nl query", "counts", "termite", "decompose", "translate", "aggregate", "machine query"]
GENERATED = ["termite", "decompose", "translate", "aggregate", "machine query"]


# --- formatting helpers (mirrors utils/build_sme_stage_cases.py) ------------
def j(obj: Any) -> str:
    """Compact JSON for the machine-query cell (matches the existing file style)."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def abbrev(values: list[str], keep: int = 3) -> str:
    """Readable, abbreviated value list for the aggregate/translate cells."""
    if len(values) <= keep:
        return ", ".join(str(v) for v in values)
    return ", ".join(str(v) for v in values[:keep]) + f", …(+{len(values) - keep} more)"


def _fmt_value(value: Any) -> str:
    """Render a MATCH value the way the gold cells do: lists in [..], scalars quoted."""
    if isinstance(value, list):
        return f"[{abbrev([str(v) for v in value])}]"
    if isinstance(value, bool):
        return str(value)
    return f'"{value}"'


# --- column renderers (driven by the live PipelineResult) -------------------
def render_termite(result: Any) -> str:
    enh = result.enhanced
    if not enh or not enh.annotations:
        return ""
    return "; ".join(f"{a.entity_type or 'ENTITY'}:{a.label}" for a in enh.annotations)


def render_decompose(result: Any) -> str:
    parts = []
    for c in result.decomposition.components:
        bg = f"({c.boolean_group.op.value})" if c.boolean_group else ""
        parts.append(f'{c.field}[{c.type.value}]:"{c.nl_fragment}"{bg}')
    return "; ".join(parts)


def _render_subquery(sq: Any) -> str:
    op = sq.operator.value
    if op == "REGEX":
        return f'REGEX {sq.field}="{sq.pattern}"'
    if op in ("RANGE", "DATE_RANGE"):
        return f"{op} {sq.field}={j(sq.value)}"
    if op == "EMPTY":
        return f"EMPTY {sq.field}"
    head = f"MATCH {sq.field}={_fmt_value(sq.value)}"
    return head + (f" (entityFilter:{sq.entity_name})" if sq.entity_name else "")


def render_translate(result: Any) -> str:
    parts = [_render_subquery(sq) for sq in result.subqueries]
    questions = result.decomposition.questions
    if questions:
        parts.append("question:" + "+".join(c.field for c in questions))
    return "; ".join(parts)


def _render_tree(node: Any) -> str:
    if not isinstance(node, dict) or len(node) != 1:
        return j(node)
    (op, body), = node.items()
    if op == "AND":
        return "AND[ " + ", ".join(_render_tree(c) for c in body) + " ]"
    if op == "OR":
        return "OR( " + ", ".join(_render_tree(c) for c in body) + " )"
    if op == "NOT":
        return "NOT( " + _render_tree(body) + " )"
    if op == "MATCH":
        return f"{body['field']}={_fmt_value(body['value'])}"
    if op == "REGEX":
        return f'{body["field"]}~"{body.get("pattern")}"'
    if op in ("RANGE", "DATE_RANGE"):
        rng = {k: v for k, v in body.items() if k != "field"}
        return f"{body['field']}={j(rng)}"
    if op == "EMPTY":
        return f"{body['field']}:empty"
    return j(node)


def render_aggregate(result: Any) -> str:
    mq = result.machine_query
    if mq is None:
        return ""
    out = _render_tree(mq.query)
    if mq.entityFilters:
        names = [next(iter(ef), "?") for ef in mq.entityFilters]
        out += f" | entityFilters=[{', '.join(names)}]"
    if mq.facets:
        out += f" | facets=[{', '.join(mq.facets)}]"
    if mq.displayColumns:
        out += f" | displayColumns=[{', '.join(mq.displayColumns)}]"
    return out


def render_machine_query(result: Any) -> str:
    mq = result.machine_query
    return j(mq.to_payload()) if mq is not None else ""


# --- driver -----------------------------------------------------------------
def fill_row(row: dict[str, str], opts: argparse.Namespace) -> dict[str, str]:
    from oppp.pipeline import run_pipeline

    query = (row.get("nl query") or "").strip()
    last_err: Exception | None = None
    for attempt in range(2):  # one retry for transient LLM/network hiccups
        try:
            result = run_pipeline(
                query,
                opts.service,
                enhancer=opts.enhancer,
                decomposer=opts.decomposer,
                translator=opts.translator,
                aggregator=opts.aggregator,
                normalizer=opts.normalizer,
            )
            row["termite"] = render_termite(result)
            row["decompose"] = render_decompose(result)
            row["translate"] = render_translate(result)
            row["aggregate"] = render_aggregate(result)
            row["machine query"] = render_machine_query(result)
            print(f"  OK   ({'ok' if result.ok else 'issues'}): {query[:60]}")
            return row
        except Exception as exc:  # noqa: BLE001 — resilience: one bad row must not abort
            last_err = exc
            if attempt == 0:
                time.sleep(1.0)
    msg = f"ERROR: {type(last_err).__name__}: {last_err}"
    for col in GENERATED:
        row[col] = msg
    print(f"  FAIL: {query[:60]}  -> {msg}")
    return row


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_CSV)
    p.add_argument("--output", type=Path, default=None, help="Defaults to --input (overwrite).")
    p.add_argument("--service", default="safety")
    p.add_argument("--enhancer", default="termite")
    p.add_argument("--decomposer", default="llm")
    p.add_argument("--translator", default="tool")
    p.add_argument("--aggregator", default="llm")
    p.add_argument("--normalizer", default="fuzzy")
    p.add_argument("--limit", type=int, default=0, help="0 = all rows.")
    p.add_argument("--no-backup", action="store_true")
    opts = p.parse_args()

    out_path: Path = opts.output or opts.input

    from oppp.config import load_dotenv_if_present

    load_dotenv_if_present()

    # Fail fast if the chosen enhancer can't initialise (missing toolkit/creds).
    try:
        from oppp.stages.enhance import get_enhancer

        get_enhancer(opts.enhancer)
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot initialise enhancer '{opts.enhancer}': {type(exc).__name__}: {exc}")
        print("Remedy: install the LLM/SciBite extras (pip install -e '.[llm]') and check .env,")
        print("or rerun with offline backends, e.g. --enhancer noop --decomposer gazetteer "
              "--translator deterministic --aggregator deterministic")
        return 2

    with open(opts.input, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("nl query") or "").strip()]

    if opts.limit:
        rows = rows[: opts.limit]

    print(f"Filling {len(rows)} row(s) via "
          f"{opts.enhancer}/{opts.decomposer}/{opts.translator}/{opts.aggregator} "
          f"(normalizer={opts.normalizer}) -> {out_path}")

    filled = [fill_row(row, opts) for row in rows]

    if out_path.exists() and not opts.no_backup:
        bak = out_path.with_suffix(out_path.suffix + f".{time.strftime('%Y%m%d-%H%M%S')}.bak")
        shutil.copy2(out_path, bak)
        print(f"Backup written: {bak}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER, extrasaction="ignore")
        writer.writeheader()
        for row in filled:
            writer.writerow({k: row.get(k, "") for k in HEADER})

    n_err = sum(1 for r in filled if str(r.get("machine query", "")).startswith("ERROR:"))
    print(f"Wrote {len(filled)} row(s) to {out_path} ({n_err} error row(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
