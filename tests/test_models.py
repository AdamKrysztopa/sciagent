from agt.models import AgentState, NormalizedPaper


def test_normalized_paper_defaults() -> None:
    paper = NormalizedPaper(title="A paper")
    assert paper.source == "semantic_scholar"
    assert paper.authors == []
    assert paper.arxiv_id is None


def test_agent_state_allows_checkpoint_safe_serialized_payloads() -> None:
    state: AgentState = {
        "request_id": "req-1",
        "thread_id": "thread-1",
        "messages": ["Processed query: q"],
        "papers": [{"title": "Paper A", "source": "semantic_scholar"}],
        "collection_name": "Inbox",
        "approved": False,
        "decision": "pending",
        "phase": "awaiting_approval",
        "selected_indices": [0],
        "preflight": {"ok": True},
        "trace_spans": [],
        "write_result": None,
        "search_metadata": {"original_query": "q", "regex_query": "q"},
    }

    assert state["papers"][0]["title"] == "Paper A"
