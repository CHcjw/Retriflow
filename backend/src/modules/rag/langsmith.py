from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from core.config import get_settings

try:
    import langsmith as ls
except Exception:  # pragma: no cover - optional runtime dependency guard
    ls = None


@contextmanager
def retriflow_langsmith_context(
    *,
    run_name: str,
    metadata: dict[str, Any] | None = None,
) -> Iterator[None]:
    settings = get_settings()
    if not settings.langsmith_tracing or ls is None:
        yield
        return

    trace_metadata = {
        "app": "retriflow",
        "run_name": run_name,
        **(metadata or {}),
    }
    with ls.tracing_context(
        enabled=True,
        project_name=settings.langsmith_project,
        metadata=trace_metadata,
    ):
        yield
