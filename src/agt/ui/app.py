"""Streamlit prototype for search and approval flow."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, cast

import streamlit as st

from agt.graph.workflow import finalize_approval, run_search_phase
from agt.models import AgentState

st.set_page_config(page_title="SciAgent", page_icon="📚", layout="wide")
st.title("SciAgent")
st.caption("Search papers, review, and approve an idempotent Zotero write.")

query = st.text_input("Search query", placeholder="Recent papers on retrieval-augmented generation")
collection = st.text_input("Collection", value="Inbox")

if "m4_checkpoint" not in st.session_state:
    st.session_state["m4_checkpoint"] = None
if "m4_final_state" not in st.session_state:
    st.session_state["m4_final_state"] = None


def _paper_title(index: int, paper: dict[str, Any]) -> str:
    return f"{index}. {paper.get('title', 'Untitled')}"


def _render_outcomes(write_result: dict[str, Any] | None) -> None:
    if write_result is None:
        st.info("No write attempt yet.")
        return

    outcomes_raw = cast(object, write_result.get("outcomes", []))
    outcomes = cast(list[object], outcomes_raw) if isinstance(outcomes_raw, list) else []
    if outcomes:
        rows: list[dict[str, object | None]] = []
        for outcome_raw in outcomes:
            if not isinstance(outcome_raw, dict):
                continue
            outcome = cast(dict[str, object], outcome_raw)
            rows.append({
                "index": outcome.get("index"),
                "title": outcome.get("title"),
                "status": outcome.get("status"),
                "reason": outcome.get("reason"),
                "item_key": outcome.get("item_key"),
            })
        st.write(rows)
    else:
        st.json(write_result)


def _identity_fragment(fn: Callable[[], None]) -> Callable[[], None]:
    return fn


fragment_decorator = cast(
    Callable[[Callable[[], None]], Callable[[], None]],
    getattr(st, "experimental_fragment", _identity_fragment),
)

if st.button("Search", type="primary"):
    if not query.strip():
        st.warning("Enter a query first.")
    else:
        try:
            checkpoint = asyncio.run(run_search_phase(query=query, collection_name=collection))
        except RuntimeError as exc:
            st.error(str(exc))
            st.stop()

        st.session_state["m4_checkpoint"] = checkpoint
        st.session_state["m4_final_state"] = None

checkpoint_state = cast(object, st.session_state.get("m4_checkpoint"))
checkpoint = (
    cast(dict[str, object], checkpoint_state) if isinstance(checkpoint_state, dict) else None
)
if checkpoint is not None:
    typed_checkpoint = cast(AgentState, checkpoint)
    st.caption(
        f"request_id={typed_checkpoint['request_id']} thread_id={typed_checkpoint['thread_id']}"
    )

    st.subheader("Results")
    papers = typed_checkpoint["papers"]
    selected_indices: list[int] = []
    for index, paper in enumerate(papers):
        is_selected = st.checkbox(
            _paper_title(index, paper),
            value=True,
            key=f"select-paper-{index}",
        )
        if is_selected:
            selected_indices.append(index)
        st.write({
            "source": paper.get("source"),
            "year": paper.get("year"),
            "doi": paper.get("doi"),
            "arxiv_id": paper.get("arxiv_id"),
            "score": paper.get("score"),
        })
        if paper.get("summary"):
            st.caption(str(paper["summary"]))

    edited_collection = st.text_input(
        "Collection to use at approval",
        value=str(typed_checkpoint.get("collection_name") or "Inbox"),
        key="approval-collection",
    )

    @fragment_decorator
    def _approval_actions() -> None:
        approve = st.button("Approve Selected", type="primary")
        reject = st.button("Reject", type="secondary")
        if not approve and not reject:
            return

        try:
            final_state = asyncio.run(
                finalize_approval(
                    typed_checkpoint,
                    approved=approve,
                    collection_name=edited_collection,
                    selected_indices=selected_indices,
                )
            )
        except RuntimeError as exc:
            st.error(str(exc))
            return

        st.session_state["m4_final_state"] = final_state

    _approval_actions()

    st.subheader("Preflight")
    st.json(typed_checkpoint["preflight"])

    st.subheader("Search Metadata")
    st.json(typed_checkpoint["search_metadata"])

final_state = cast(object, st.session_state.get("m4_final_state"))
typed_final_state = cast(dict[str, object], final_state) if isinstance(final_state, dict) else None
if typed_final_state is not None:
    final = cast(AgentState, typed_final_state)
    st.subheader("Final Status")
    st.write({
        "phase": final["phase"],
        "decision": final["decision"],
        "approved": final["approved"],
        "collection": final["collection_name"],
        "selected_indices": final["selected_indices"],
    })

    st.subheader("Write Status")
    _render_outcomes(final["write_result"])

    st.subheader("Trace")
    st.json(final["trace_spans"])
