from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from getter_api.db import make_engine
from getter_api.llm.config import load_llm_config
from getter_api.llm.gateway import LLMGateway
from getter_api.main import create_app
from getter_api.models import Base
from getter_api.settings import Settings


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 23, 10, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # Set GETTER_TEST_DATABASE_URL to run the suite against Postgres.
    url = os.environ.get("GETTER_TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{tmp_path}/t.db"
    return Settings(environment="test", database_url=url)


AppFactory = Callable[..., FastAPI]


@pytest.fixture
async def make_client(
    settings: Settings, clock: FakeClock
) -> AsyncIterator[Callable[..., httpx.AsyncClient]]:
    """Build a client for an app; pass gateway= or settings overrides to change behaviour."""
    stack: list[tuple[FastAPI, object]] = []

    async def factory(gateway: LLMGateway | None = None, **overrides: object) -> httpx.AsyncClient:
        s = settings.model_copy(update=overrides)
        engine = make_engine(s.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        app = create_app(s, gateway or LLMGateway(load_llm_config()), clock)
        ctx = app.router.lifespan_context(app)
        await ctx.__aenter__()
        stack.append((app, ctx))
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    yield factory  # type: ignore[misc]
    for _app, ctx in reversed(stack):
        await ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]


def as_user(email: str) -> dict[str, str]:
    return {"x-dev-user-email": email}
