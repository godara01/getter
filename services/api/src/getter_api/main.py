from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from getter_api.admin.routes import router as admin_router
from getter_api.content import library
from getter_api.db import make_engine, make_sessionmaker, utcnow
from getter_api.interview.engine import InterviewEngine
from getter_api.interview.grading import Grader
from getter_api.llm.config import load_llm_config
from getter_api.llm.gateway import LLMGateway
from getter_api.models import InterviewSession
from getter_api.routes.community import router as community_router
from getter_api.routes.progress import router as progress_router
from getter_api.routes.sessions import router as sessions_router
from getter_api.settings import Settings, get_settings

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    gateway: LLMGateway | None = None,
    clock: Callable[[], datetime] = utcnow,
) -> FastAPI:
    settings = settings or get_settings()
    gateway = gateway or LLMGateway(load_llm_config(settings.llm_config or None))
    content = library()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        app.state.sessionmaker = make_sessionmaker(engine)
        app.state.redis = (
            await create_pool(RedisSettings.from_dsn(settings.redis_url))
            if settings.redis_url
            else None
        )
        recovery = asyncio.create_task(_resume_grading(app))
        try:
            yield
        finally:
            recovery.cancel()
            if app.state.redis is not None:
                await app.state.redis.aclose()
            await engine.dispose()

    app = FastAPI(title="Getter API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = InterviewEngine(gateway, content, settings, clock)
    app.state.grader = Grader(gateway, content, settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["content-type", "x-dev-user-email", "authorization"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        try:
            async with app.state.sessionmaker() as db:
                await db.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(503, "database unavailable") from exc
        return {"status": "ok"}

    app.include_router(sessions_router)
    app.include_router(progress_router)
    app.include_router(community_router)
    app.include_router(admin_router)
    return app


async def _resume_grading(app: FastAPI) -> None:
    """Grade sessions left in 'grading' by a restart, so none are stuck."""
    try:
        async with app.state.sessionmaker() as db:
            ids = list(
                await db.scalars(
                    select(InterviewSession.id).where(InterviewSession.status == "grading")
                )
            )
        for session_id in ids:
            if app.state.redis is not None:
                await app.state.redis.enqueue_job(
                    "grade_session", str(session_id), _job_id=f"grade:{session_id}"
                )
                continue
            async with app.state.sessionmaker() as db:
                session = await db.get(InterviewSession, session_id)
                if session is not None and session.status == "grading":
                    await app.state.grader.grade(db, session)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("resuming grading failed")
