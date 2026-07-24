"""Shared job runtime helpers.

Extracted from __main__ so adapter modules can build their CLI commands via a
module-local ``register(app)`` without importing (or editing) __main__ —
__main__ stays the single integration point that wires registrations.
"""

from __future__ import annotations

import contextlib
from typing import Any, Iterator

from .config import Settings
from .db import DatabaseGateway, PostgresGateway
from .raw_store import RawStore

USER_AGENT = "CrewGraphs/0.1 (public data pipeline; crewgraphs.com/methods)"


@contextlib.contextmanager
def job_context() -> Iterator[tuple[DatabaseGateway, RawStore, Any]]:
    import httpx

    settings = Settings.from_env()
    gateway = PostgresGateway(settings.database_url)
    store = RawStore(settings)
    http = httpx.Client(
        timeout=httpx.Timeout(300.0, connect=30.0),
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        yield gateway, store, http
    finally:
        http.close()
        gateway.close()


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
