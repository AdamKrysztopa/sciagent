"""Streamlit prototype for search and approval flow."""

from __future__ import annotations

import asyncio

import streamlit as st

from agt.graph.workflow import run_workflow

st.set_page_config(page_title="SciAgent", page_icon="📚", layout="wide")
st.title("SciAgent")
st.caption("Search papers, review, and approve an idempotent Zotero write.")

query = st.text_input("Search query", placeholder="Recent papers on retrieval-augmented generation")
collection = st.text_input("Collection", value="Inbox")
approved = st.checkbox("Approve write", value=False)

if st.button("Run", type="primary"):
    if not query.strip():
        st.warning("Enter a query first.")
    else:
        try:
            state = asyncio.run(
                run_workflow(query=query, collection_name=collection, approved=approved)
            )
        except RuntimeError as exc:
            st.error(str(exc))
            st.stop()

        st.caption(f"request_id={state['request_id']} thread_id={state['thread_id']}")
        st.subheader("Results")
        for paper in state["papers"]:
            display_index = paper.index if paper.index is not None else -1
            st.markdown(f"**{display_index}. {paper.title}**")
            st.write({
                "source": paper.source,
                "year": paper.year,
                "doi": paper.doi,
                "score": paper.score,
            })
            if paper.summary:
                st.caption(paper.summary)

        st.subheader("Preflight")
        st.json(state["preflight"])

        st.subheader("Write Status")
        st.json(state["write_result"])

        st.subheader("Trace")
        st.json(state["trace_spans"])
