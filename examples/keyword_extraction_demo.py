"""Run keyword extraction examples from prompts.

Usage:
  uv run python examples/keyword_extraction_demo.py
  uv run python examples/keyword_extraction_demo.py --max-prompts 5
"""

from __future__ import annotations

import argparse

from agt.tools.query_constraints import parse_query_constraints

_DEFAULT_PROMPTS = [
    "the most cited 2020 and newer timeseries papers - list 5",
    "most recent papers in nutrition in sport not older than 2024",
    "deep reinforcement learning robotics 2023 and newer",
    "retrieval augmented generation game changers",
    "graph learning papers between 2020 and 2024",
    "transformer papers from 2021 to 2023",
    "nutrition papers not about supplements",
    "energy metabolism excluding marketing but not caffeine",
    "open access clinical trials after 2022 with at least 25 citations",
    "highest quoted papers in protein folding",
]


def run_demo(max_prompts: int) -> None:
    prompts = _DEFAULT_PROMPTS[: max(1, min(max_prompts, 10))]

    print("Keyword Extraction Demo")
    print("=" * 80)
    for idx, prompt in enumerate(prompts, start=1):
        constraints = parse_query_constraints(prompt, default_limit=10)
        print(f"{idx:02d}. prompt: {prompt}")
        print(f"    include_keywords: {constraints.keywords.include_keywords}")
        print(f"    exclude_keywords: {constraints.keywords.exclude_keywords}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run keyword extraction examples")
    parser.add_argument(
        "--max-prompts",
        type=int,
        default=10,
        help="How many prompts to run (1-10).",
    )
    args = parser.parse_args()
    run_demo(args.max_prompts)


if __name__ == "__main__":
    main()
