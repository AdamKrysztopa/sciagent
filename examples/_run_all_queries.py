"""Run 5 demo queries and write combined output to /tmp/m2_all_results.txt."""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure we import from the project
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("AGT_XAI_API_KEY", "xai-local")
os.environ.setdefault("AGT_ZOTERO_API_KEY", "zot-local")
os.environ.setdefault("AGT_ZOTERO_LIBRARY_ID", "local-library")
os.environ.setdefault("AGT_SUMMARIZATION_USE_LLM", "false")

from agt.config import Settings
from agt.guardrails import configure_guardrails, thread_context
from agt.tools.search_papers import search_papers
from agt.tools.summarize import summarize_papers

QUERIES = [
    ("the most cited 2020 and newer timeseries papers - list 5", 5),
    ("the most advanced RAG techniques in 2026 game changers", 5),
    ("retrieval augmented generation", 5),
    ("transformer architectures for natural language processing after 2022", 5),
    ("deep reinforcement learning robotics 2023 and newer", 5),
    ("the most trandign 2026 timeseries papers - list 5", 5),
    (
        "the most advanced RAG techniques in 2026 - game changers. Make sure the community perception is good",
        5,
    ),
]

OUTPUT_PATH = "/tmp/m2_all_results.txt"


async def run_query(settings: Settings, query: str, limit: int, idx: int) -> str:
    lines: list[str] = []
    lines.append(f"=== Query {idx}: {query} (limit={limit}) ===")
    try:
        with thread_context(f"batch-{idx}"):
            papers = await search_papers(
                query=query, limit=limit, settings=settings, thread_id=f"batch-{idx}"
            )
        papers = await summarize_papers(papers, provider=None, use_llm=False, max_sentences=2)
        lines.append(f"results: {len(papers)}")
        for p in papers:
            doi = p.doi or "n/a"
            year = p.year if p.year is not None else "n/a"
            idx_str = p.index if p.index is not None else "-"
            lines.append(f"  [{idx_str}] {p.title}")
            lines.append(f"      year={year}  citations={p.citation_count}  doi={doi}")
    except Exception as exc:
        lines.append(f"error: {exc}")
    lines.append("")
    return "\n".join(lines)


async def main() -> None:
    settings = Settings.model_validate({
        "AGT_XAI_API_KEY": os.getenv("AGT_XAI_API_KEY", "xai-local"),
        "AGT_ZOTERO_API_KEY": os.getenv("AGT_ZOTERO_API_KEY", "zot-local"),
        "AGT_ZOTERO_LIBRARY_ID": os.getenv("AGT_ZOTERO_LIBRARY_ID", "local"),
        "AGT_SUMMARIZATION_USE_LLM": False,
    })
    configure_guardrails(settings)

    all_output: list[str] = []
    for idx, (query, limit) in enumerate(QUERIES, start=1):
        result = await run_query(settings, query, limit, idx)
        all_output.append(result)
        print(result)
        sys.stdout.flush()

    with open(OUTPUT_PATH, "w") as f:
        f.write("\n".join(all_output))
    print(f"\n--- All results written to {OUTPUT_PATH} ---")


if __name__ == "__main__":
    asyncio.run(main())
