"""Run with `uv run arq getter_api.worker.WorkerSettings`."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from arq import Retry, cron
from arq.connections import RedisSettings
from fastapi import BackgroundTasks, Request
from sqlalchemy import select

from getter_api.content import library
from getter_api.db import make_engine, make_sessionmaker
from getter_api.interview.grading import Grader
from getter_api.llm.config import load_llm_config
from getter_api.llm.gateway import LLMGateway
from getter_api.llm.types import AllModelsFailed
from getter_api.models import InterviewSession
from getter_api.settings import get_settings

log = logging.getLogger(__name__)
MAX_TRIES = 3


async def grade_session(ctx: dict[str, Any], session_id: str) -> None:
    async with ctx["sessionmaker"]() as db:
        session = await db.scalar(
            select(InterviewSession)
            .where(InterviewSession.id == uuid.UUID(session_id))
            .with_for_update()
        )
        if session is None or session.status != "grading":
            return
        try:
            # Leave time to save a clear failure before arq's outer timeout.
            async with asyncio.timeout(240):
                await ctx["grader"].grade(db, session, retry_on_failure=True)
        except Exception as exc:
            log.exception("grading attempt failed for %s", session_id)
            # Model failures have recorded billable calls, so preserve them.
            if isinstance(exc, AllModelsFailed) and db.is_active:
                await db.commit()
            else:
                await db.rollback()
            if ctx.get("job_try", 1) < MAX_TRIES:
                raise Retry(defer=ctx.get("job_try", 1) * 5) from None
            session = await db.get(InterviewSession, uuid.UUID(session_id))
            if session is not None and session.status == "grading":
                session.status = "failed"
                session.error = "Grading failed after three attempts; no score was produced."
                await db.commit()


async def grade_locally(request: Request, session_id: uuid.UUID) -> None:
    ctx = {
        "sessionmaker": request.app.state.sessionmaker,
        "grader": request.app.state.grader,
    }
    for attempt in range(1, MAX_TRIES + 1):
        ctx["job_try"] = attempt
        try:
            await grade_session(ctx, str(session_id))
            return
        except Retry:
            continue


async def dispatch_grading(
    request: Request, background: BackgroundTasks, session_id: uuid.UUID
) -> None:
    if request.app.state.settings.redis_url:
        try:
            await request.app.state.redis.enqueue_job(
                "grade_session", str(session_id), _job_id=f"grade:{session_id}"
            )
        except Exception:
            # The database is the outbox: the worker's periodic sweep picks up
            # sessions if Redis was unavailable between commit and enqueue.
            log.exception("enqueue failed; worker recovery will retry %s", session_id)
    else:
        background.add_task(grade_locally, request, session_id)


async def recover_grading(ctx: dict[str, Any]) -> None:
    async with ctx["sessionmaker"]() as db:
        ids = list(
            await db.scalars(
                select(InterviewSession.id).where(InterviewSession.status == "grading")
            )
        )
    for session_id in ids:
        await ctx["redis"].enqueue_job(
            "grade_session", str(session_id), _job_id=f"grade:{session_id}"
        )


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    ctx["db_engine"] = engine
    ctx["sessionmaker"] = make_sessionmaker(engine)
    ctx["grader"] = Grader(
        LLMGateway(load_llm_config(settings.llm_config or None)), library(), settings
    )
    await recover_grading(ctx)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["db_engine"].dispose()


class WorkerSettings:
    functions = [grade_session]
    cron_jobs = [cron(recover_grading, minute=set(range(60)))]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url or "redis://localhost:6379/0")
    on_startup = startup
    on_shutdown = shutdown
    max_tries = MAX_TRIES
    max_jobs = 1
    job_timeout = 300
    keep_result = 3600
