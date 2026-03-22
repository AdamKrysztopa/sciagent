# SciAgent Runnable Examples

This folder tracks one runnable example per milestone (`M1` to `M6`).

## Run Commands

- M1 (planned): `source .venv/bin/activate && python examples/m1_foundation_demo.py`
- M2 (implemented): `source .venv/bin/activate && python examples/m2_retrieval_demo.py --query "retrieval augmented generation"`
- M3 (planned): `source .venv/bin/activate && python examples/m3_write_correctness_demo.py`
- M4 (planned): `source .venv/bin/activate && python examples/m4_approval_flow_demo.py`
- M5 (planned): `source .venv/bin/activate && python examples/m5_hardening_demo.py`
- M6 (planned): `source .venv/bin/activate && python examples/m6_zotero_addon_demo.py`

## Notes

- `m2_retrieval_demo.py` is live-search only and uses Semantic Scholar directly.
- If Semantic Scholar returns rate-limit responses, retry later instead of switching to mock data.

## M2 Required Validation Queries

- `source .venv/bin/activate && python examples/m2_retrieval_demo.py --query "the most trandign 2026 timeseries papers - list 5" --limit 5`
- `source .venv/bin/activate && python examples/m2_retrieval_demo.py --query "the most advanced RAG techniques in 2026 - game changers. Make sure the community perception is good!" --limit 5`

## CI Hooks

- Run all hooks exactly as CI expects: `source .venv/bin/activate && ruff check . && ruff format --check . && pyright && pytest -q`
- Pre-commit equivalent: `source .venv/bin/activate && pre-commit run --all-files`
