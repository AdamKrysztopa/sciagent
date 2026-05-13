"""Provider scaffold generator for SciAgent.

Usage:
    uv run python scripts/new_provider.py FooProvider [--key-env-var AGT_FOO_KEY] \
        [--base-url https://api.example.com] [--no-test]

Creates:
    src/agt/tools/{snake_name}.py   — SearchProviderBase subclass skeleton
    tests/test_{snake_name}.py      — minimal pytest stub (unless --no-test)
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _to_snake(name: str) -> str:
    """Convert CamelCase to snake_case.

    >>> _to_snake("FooProvider")
    'foo_provider'
    >>> _to_snake("MyNewClient")
    'my_new_client'
    """
    return _CAMEL_RE.sub("_", name).lower()


def _provider_short_name(snake: str) -> str:
    """Return the provider name without a trailing ``_provider`` or ``_client``."""
    for suffix in ("_provider", "_client"):
        if snake.endswith(suffix):
            return snake[: -len(suffix)]
    return snake


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def _provider_template(
    class_name: str,
    snake_name: str,
    short_name: str,
    key_env_var: str | None,
    base_url: str,
) -> str:
    snake_upper = snake_name.upper()
    has_key = key_env_var is not None

    # Build capabilities block
    field_lines = "\n".join(
        f"        _F.{f}: _S.NONE,"
        for f in (
            "TITLE",
            "ABSTRACT",
            "AUTHORS",
            "DOI",
            "YEAR",
            "VENUE",
            "CITATION_COUNT",
            "OA_URL",
            "REFERENCES",
            "RELATED",
        )
    )
    caps_extras = ""
    if has_key:
        caps_extras += f'\n    key_env_var="{key_env_var}",'
        caps_extras += (
            f'\n    key_upgrade_hint="Set {key_env_var} to enable authenticated access.",'
        )

    # Build __init__ signature and body
    if has_key:
        init_extra_param = "        api_key: str | None = None,\n"
        init_body_extra = "        self._api_key = api_key\n"
    else:
        init_extra_param = ""
        init_body_extra = ""

    return textwrap.dedent(f"""\
        \"\"\"{class_name} search provider.\"\"\"

        from __future__ import annotations

        from typing import cast

        import httpx
        from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

        from agt.models import NormalizedAuthor, NormalizedPaper
        from agt.tools.capabilities import FieldSupport as _S
        from agt.tools.capabilities import ProviderField as _F
        from agt.tools.capabilities import SearchProviderCapabilities
        from agt.tools.provider_base import SearchProviderBase

        _{snake_upper}_BASE_URL = "{base_url}"


        class {class_name}ResponseError(RuntimeError):
            \"\"\"Raised when {class_name} response payload is malformed.\"\"\"


        {class_name}Capabilities = SearchProviderCapabilities(
            name="{short_name}",
            requires_key={has_key!s},
            fields={{
        {field_lines}
            }},{caps_extras}
        )


        class {class_name}(SearchProviderBase):
            \"\"\"{class_name} search provider returning NormalizedPaper models.\"\"\"

            capabilities_ = {class_name}Capabilities

            def __init__(
                self,
                *,
                mailto: str | None = None,
                timeout: float = 15.0,
        {init_extra_param}        base_url: str = _{snake_upper}_BASE_URL,
            ) -> None:
                super().__init__(mailto=mailto, timeout=timeout)
                self._base_url = base_url.rstrip("/")
        {init_body_extra}
            async def _search_impl(
                self,
                query: str,
                *,
                limit: int = 25,
                author: str | None = None,
                year_from: int | None = None,
                year_to: int | None = None,
            ) -> list[NormalizedPaper]:
                # TODO: implement — remove the early return and fill in real logic
                _ = author
                _ = year_from
                _ = year_to
                if not query.strip():
                    return []

                url = f"{{self._base_url}}/search"
                params: dict[str, str] = {{"q": query, "pageSize": str(min(limit, 100))}}

                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=1, max=8),
                    retry=retry_if_exception_type((
                        httpx.TimeoutException,
                        httpx.NetworkError,
                        httpx.HTTPStatusError,
                    )),
                    reraise=True,
                ):
                    with attempt:
                        response = await self._client.get(url, params=params)
                        response.raise_for_status()
                        payload_obj: object = response.json()
                        if not isinstance(payload_obj, dict):
                            raise {class_name}ResponseError("Payload must be a JSON object")
                        payload = cast(dict[str, object], payload_obj)

                        raw_results = payload.get("results")
                        if raw_results is None:
                            return []
                        if not isinstance(raw_results, list):
                            raise {class_name}ResponseError("Missing list field: results")

                        papers: list[NormalizedPaper] = []
                        for item_obj in cast(list[object], raw_results):
                            if not isinstance(item_obj, dict):
                                continue
                            paper = self._parse_item(cast(dict[str, object], item_obj))
                            if paper is not None:
                                papers.append(paper)
                        return papers

                raise {class_name}ResponseError("{class_name} request failed after retries")

            @staticmethod
            def _parse_item(item: dict[str, object]) -> NormalizedPaper | None:
                # TODO: map raw API fields to NormalizedPaper — see doaj.py for the pattern
                title_raw = item.get("title")
                if not isinstance(title_raw, str) or not title_raw.strip():
                    return None
                return NormalizedPaper(
                    title=title_raw.strip(),
                    authors=[],
                    source="{short_name}",
                )
        """)


def _test_template(class_name: str, snake_name: str) -> str:
    return textwrap.dedent(f"""\
        \"\"\"Stub tests for {class_name}.\"\"\"

        # TODO: add VCR cassette tests — see tests/test_doaj.py for the pattern

        from __future__ import annotations

        import pytest

        from agt.tools.{snake_name} import {class_name}


        @pytest.mark.anyio
        async def test_{snake_name}_stub_returns_empty() -> None:
            client = {class_name}()
            assert await client.search("test") == []
        """)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a new SciAgent search provider scaffold.",
    )
    parser.add_argument(
        "provider_name",
        help="CamelCase class name, e.g. FooProvider",
    )
    parser.add_argument(
        "--key-env-var",
        default=None,
        help="Env var name for the API key, e.g. AGT_FOO_KEY",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Base URL, e.g. https://api.example.com",
    )
    parser.add_argument(
        "--no-test",
        action="store_true",
        help="Skip generating the test stub",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    class_name: str = args.provider_name
    snake_name = _to_snake(class_name)
    short_name = _provider_short_name(snake_name)
    key_env_var: str | None = args.key_env_var
    base_url: str = args.base_url or "https://FILL_ME_IN"
    no_test: bool = args.no_test

    repo_root = Path(__file__).resolve().parent.parent
    provider_path = repo_root / "src" / "agt" / "tools" / f"{snake_name}.py"
    test_path = repo_root / "tests" / f"test_{snake_name}.py"

    created: list[Path] = []
    skipped: list[Path] = []

    # --- provider file ---
    if provider_path.exists():
        print(f"WARNING: {provider_path.relative_to(repo_root)} already exists — skipping.")
        skipped.append(provider_path)
    else:
        provider_path.write_text(
            _provider_template(
                class_name=class_name,
                snake_name=snake_name,
                short_name=short_name,
                key_env_var=key_env_var,
                base_url=base_url,
            ),
            encoding="utf-8",
        )
        created.append(provider_path)

    # --- test file ---
    if not no_test:
        if test_path.exists():
            print(f"WARNING: {test_path.relative_to(repo_root)} already exists — skipping.")
            skipped.append(test_path)
        else:
            test_path.write_text(
                _test_template(class_name=class_name, snake_name=snake_name),
                encoding="utf-8",
            )
            created.append(test_path)

    for path in created:
        print(f"Created: {path.relative_to(repo_root)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
