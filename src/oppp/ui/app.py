"""Streamlit debug/demo UI: enter a query and inspect each stage.

Run with:  streamlit run src/oppp/ui/app.py
(needs the 'ui' extra: pip install 'oppp[ui]')
"""

from __future__ import annotations

import json

import streamlit as st

from oppp.normalize.base import normalizer_registry
from oppp.pipeline import run_pipeline
from oppp.services.base import service_registry
from oppp.stages.decompose import decomposer_registry

st.set_page_config(page_title="oppp — NL → machine query", layout="wide")
st.title("NL → machine query (decomposed pipeline)")

with st.sidebar:
    st.header("Config")
    service = st.selectbox("Service", service_registry.names() or ["safety"])
    decomposer = st.selectbox("Decomposer (Stage 1)", decomposer_registry.names())
    normalizer = st.selectbox("Normalizer (misspelling)", normalizer_registry.names())
    st.caption("The 'llm' decomposer needs the llm extra + .env credentials.")

query = st.text_input(
    "Question",
    value="What are the drug causing neutropenia or Thrombocytopenia in human, "
    "at which dose, dosing regimen and route?",
)

if st.button("Translate", type="primary") and query.strip():
    try:
        result = run_pipeline(query, service, decomposer=decomposer, normalizer=normalizer)
    except Exception as e:  # pragma: no cover - UI guard
        st.error(f"{type(e).__name__}: {e}")
        st.stop()

    if result.ok:
        st.success("Valid machine query produced.")
    else:
        st.warning("Issues: " + "; ".join(i.message for i in result.issues))

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
                tag = f" (expanded from {sq.grounding.expanded_from})" if sq.grounding.expanded_from else ""
                st.caption(f"grounded → {names}{tag}")

    with c2:
        st.subheader("Stage 3 — final machine query")
        st.code(
            json.dumps(result.machine_query.to_payload(), indent=2, ensure_ascii=False),
            language="json",
        )
