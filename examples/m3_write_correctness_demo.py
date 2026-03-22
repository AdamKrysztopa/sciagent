"""M3 write correctness demo with deterministic mock Zotero responses."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from agt.config import Settings, configure_logging
from agt.guardrails import configure_guardrails
from agt.models import NormalizedPaper
from agt.tools.zotero_upsert import upsert_papers


def _settings() -> Settings:
    return Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-demo",
        "AGT_ZOTERO_API_KEY": "zotero-demo",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_ZOTERO_LIBRARY_TYPE": "user",
    })


def _paper(title: str, doi: str | None, authors: list[str]) -> NormalizedPaper:
    return NormalizedPaper(
        title=title,
        doi=doi,
        authors=authors,
        year=2024,
        url="https://example.org/paper",
        abstract="Example abstract",
        source="semantic_scholar",
    )


def _build_demo_transport() -> httpx.MockTransport:
    collections: list[dict[str, Any]] = [
        {"key": "PARENT1", "data": {"name": "Research", "parentCollection": None}},
    ]
    items_by_collection: dict[str, list[dict[str, Any]]] = {"PARENT1": []}
    collection_counter = 2
    item_counter = 1

    def find_collection(key: str) -> dict[str, Any] | None:
        for collection in collections:
            if collection.get("key") == key:
                return collection
        return None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal collection_counter, item_counter
        path = request.url.path

        if request.method == "GET" and path == "/users/12345/collections":
            return httpx.Response(200, json=collections)

        if request.method == "POST" and path == "/users/12345/collections":
            payload = json.loads(request.content.decode("utf-8"))
            data = payload[0]
            key = f"C{collection_counter}"
            collection_counter += 1
            new_collection = {
                "key": key,
                "data": {
                    "name": data["name"],
                    "parentCollection": data.get("parentCollection"),
                },
            }
            collections.append(new_collection)
            items_by_collection[key] = []
            return httpx.Response(200, json={"successful": {"0": {"key": key}}})

        if (
            request.method == "GET"
            and path.startswith("/users/12345/collections/")
            and path.endswith("/items/top")
        ):
            key = path.split("/")[4]
            return httpx.Response(200, json=items_by_collection.get(key, []))

        if request.method == "POST" and path == "/users/12345/items":
            payload = json.loads(request.content.decode("utf-8"))[0]
            title = str(payload.get("title", ""))
            if "Bad" in title:
                return httpx.Response(
                    200,
                    json={"successful": {}, "failed": {"0": {"message": "invalid title"}}},
                )

            key = f"I{item_counter}"
            item_counter += 1
            collection_keys = payload.get("collections") or []
            target_collection = collection_keys[0] if collection_keys else ""
            collection = find_collection(target_collection)
            creators = payload.get("creators") or []
            items_by_collection.setdefault(target_collection, []).append({
                "key": key,
                "data": {
                    "title": title,
                    "DOI": payload.get("DOI", ""),
                    "creators": creators,
                    "parentCollection": collection["data"].get("parentCollection")
                    if collection
                    else None,
                },
            })
            return httpx.Response(200, json={"successful": {"0": {"key": key}}})

        return httpx.Response(404, text="Unhandled endpoint")

    return httpx.MockTransport(handler)


def _print_result(label: str, payload: dict[str, Any]) -> None:
    print(f"\n=== {label} ===")
    print(
        f"created={payload['created']} unchanged={payload['unchanged']} failed={payload['failed']} "
        f"retry_safe_failures={payload['retry_safe_failures']}"
    )
    collection = payload["collection"]
    print(
        f"collection={collection['name']} key={collection['key']} reused={collection['reused']} "
        f"parent={collection['parent_key']}"
    )
    for outcome in payload["outcomes"]:
        print(
            f"  [{outcome['index']}] {outcome['status']} title={outcome['title']} "
            f"key={outcome.get('item_key')} reason={outcome.get('reason')}"
        )


async def _run_demo() -> None:
    settings = _settings()
    configure_logging(settings.log_level)
    configure_guardrails(settings)

    transport = _build_demo_transport()
    client = httpx.AsyncClient(base_url="https://api.zotero.org", transport=transport)
    try:
        first_run = await upsert_papers(
            collection_name="AI Reading List",
            parent_collection_name="Research",
            papers=[_paper("Reliable RAG", "10.1000/rag", ["Ada Lovelace"])],
            settings=settings,
            client=client,
        )
        _print_result("First Run (Create)", first_run.model_dump())

        second_run = await upsert_papers(
            collection_name="AI Reading List",
            parent_collection_name="Research",
            papers=[_paper("Reliable RAG", "10.1000/rag", ["Ada Lovelace"])],
            settings=settings,
            client=client,
        )
        _print_result("Second Run (Idempotent)", second_run.model_dump())

        partial = await upsert_papers(
            collection_name="AI Reading List",
            parent_collection_name="Research",
            papers=[
                _paper("Bad Payload Example", "10.1000/bad", ["Grace Hopper"]),
                _paper("Missing Authors Example", "10.1000/no-authors", []),
            ],
            settings=settings,
            client=client,
        )
        _print_result("Partial Failures", partial.model_dump())
    finally:
        await client.aclose()


def main() -> None:
    asyncio.run(_run_demo())


if __name__ == "__main__":
    main()
