"""Streamlit debug/demo UI: enter a query and inspect each stage.

Run with:  streamlit run src/oppp/ui/app.py
(needs the 'ui' extra: pip install 'oppp[ui]')
"""

from __future__ import annotations

import json

import streamlit as st

from oppp.normalize.base import normalizer_registry
from oppp.pipeline import run_pipeline
from oppp.services.base import get_service, service_registry
from oppp.stages.aggregate import aggregator_registry
from oppp.stages.decompose import decomposer_registry
from oppp.stages.enhance import enhancer_registry
from oppp.stages.translate import translator_registry

st.set_page_config(page_title="oppp — NL → machine query", layout="wide")
st.title("NL → machine query (decomposed pipeline)")


@st.cache_data
def _gold_questions() -> list[tuple[str, str]]:
    """(label, question) options for the gold-set picker; empty if unavailable."""
    try:
        from oppp.eval.harness import load_gold_cases

        out = []
        for row in load_gold_cases():
            q = (row.get("question") or "").strip()
            if q:
                out.append((f"#{row.get('query_number', '?')}: {q[:70]}", q))
        return out
    except Exception:
        return []


with st.sidebar:
    st.header("Config")
    service = st.selectbox("Service", service_registry.names() or ["safety"])
    enhancer = st.selectbox("Enhancer (Stage 0)", enhancer_registry.names())
    decomposer = st.selectbox("Decomposer (Stage 1)", decomposer_registry.names())
    translator = st.selectbox("Translator (Stage 2)", translator_registry.names())
    aggregator = st.selectbox("Aggregator (Stage 3)", aggregator_registry.names())
    normalizer = st.selectbox("Normalizer (misspelling)", normalizer_registry.names())
    execute = st.checkbox("Execute against the search API", value=False)
    st.caption("The 'llm'/'tool'/'termite' backends need the llm extra + .env credentials.")

_DEFAULT_Q = (
    "What are the drug causing neutropenia or Thrombocytopenia in human, "
    "at which dose, dosing regimen and route?"
)
gold = _gold_questions()
picked = ""
if gold:
    labels = ["(custom — type below)"] + [label for label, _ in gold]
    choice = st.selectbox("Gold-set question", labels)
    if choice != labels[0]:
        picked = next(q for label, q in gold if label == choice)

query = st.text_input("Question", value=picked or _DEFAULT_Q)

if st.button("Translate", type="primary") and query.strip():
    try:
        result = run_pipeline(
            query,
            service,
            enhancer=enhancer,
            decomposer=decomposer,
            translator=translator,
            aggregator=aggregator,
            normalizer=normalizer,
        )
    except Exception as e:  # pragma: no cover - UI guard
        st.error(f"{type(e).__name__}: {e}")
        st.stop()

    if result.ok:
        st.success("Valid machine query produced.")
    else:
        st.warning("Issues: " + "; ".join(i.message for i in result.issues))

    st.subheader("Stage 0 — enhancement")
    enhanced = result.enhanced
    if enhanced and enhanced.annotations:
        st.caption(f"source: {enhanced.source}")
        st.dataframe(
            [
                {"surface": a.surface, "label": a.label, "type": a.entity_type or ""}
                for a in enhanced.annotations
            ],
            use_container_width=True,
        )
    else:
        st.caption(f"enhancer={enhancer}: query passed through unchanged (no annotations).")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Stage 1 — decomposition")
        st.dataframe(
            [
                {
                    "type": c.type.value,
                    "field": c.field,
                    "fragment": c.nl_fragment,
                    "bool": c.boolean_group.op.value if c.boolean_group else "",
                    "source": c.source,
                    "reason": c.reason,
                }
                for c in result.decomposition.components
            ],
            use_container_width=True,
        )
        st.subheader("Stage 2 — machine subqueries")
        for sq in result.subqueries:
            st.code(json.dumps(sq.to_constraint(), ensure_ascii=False), language="json")
            if sq.grounding and sq.grounding.matched:
                names = ", ".join(h.name for h in sq.grounding.matched[:8])
                tag = (
                    f" (expanded from {sq.grounding.expanded_from})"
                    if sq.grounding.expanded_from
                    else ""
                )
                st.caption(f"grounded → {names}{tag}")

    with c2:
        st.subheader("Stage 3 — final machine query")
        st.code(
            json.dumps(result.machine_query.to_payload(), indent=2, ensure_ascii=False),
            language="json",
        )

    if execute and result.ok:
        from oppp.execute import execute_count

        st.subheader("Execution")
        try:
            ex = execute_count(result.machine_query, get_service(service))
        except Exception as e:  # pragma: no cover - UI guard
            st.error(f"{type(e).__name__}: {e}")
        else:
            if ex.ok:
                st.metric("datapoints retrieved", ex.count_total)
            else:
                st.error(f"execution failed: {ex.error}")
