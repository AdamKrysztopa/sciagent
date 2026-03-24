"""Lightweight request/thread tracing helpers for workflow spans."""

from __future__ import annotations

import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any

import structlog


def _empty_attributes() -> dict[str, Any]:
    return {}


def _empty_spans() -> list[SpanRecord]:
    return []


@dataclass(slots=True)
class SpanRecord:
    """Single trace span captured during workflow execution."""

    name: str
    started_at_ms: int
    ended_at_ms: int | None = None
    duration_ms: int | None = None
    attributes: dict[str, Any] = field(default_factory=_empty_attributes)


@dataclass(slots=True)
class TraceContext:
    """Per-workflow trace container keyed by request and thread IDs."""

    request_id: str
    thread_id: str
    spans: list[SpanRecord] = field(default_factory=_empty_spans)

    @classmethod
    def create(cls, thread_id: str | None = None) -> TraceContext:
        return cls(request_id=str(uuid.uuid4()), thread_id=thread_id or str(uuid.uuid4()))


@contextmanager
def trace_step(trace: TraceContext, name: str, **attributes: Any) -> Generator[SpanRecord]:
    """Create a span and log start/finish with stable request/thread metadata."""

    logger = structlog.get_logger("agt.trace").bind(
        request_id=trace.request_id, thread_id=trace.thread_id, span=name
    )
    started = time.perf_counter()
    started_ms = int(time.time() * 1000)
    span = SpanRecord(name=name, started_at_ms=started_ms, attributes=attributes)
    trace.spans.append(span)
    logger.info("span_start", attributes=attributes)
    try:
        yield span
    finally:
        ended_ms = int(time.time() * 1000)
        duration_ms = int((time.perf_counter() - started) * 1000)
        span.ended_at_ms = ended_ms
        span.duration_ms = duration_ms
        logger.info("span_end", duration_ms=duration_ms, attributes=attributes)


def serialize_spans(spans: list[SpanRecord]) -> list[dict[str, Any]]:
    """Convert spans to JSON-serializable dictionaries for status payloads."""

    return [asdict(span) for span in spans]
