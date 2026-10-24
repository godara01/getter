from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock

import pytest
from arq import Retry, create_pool
from arq.connections import RedisSettings
from arq.worker import Worker
from fastapi import BackgroundTasks, Request

from getter_api.models import InterviewSession
from getter_api.worker import dispatch_grading, grade_session


async def prepared(make_client):
    client = await make_client()
    client.headers["x-dev-user-email"] = "queue@example.com"
    templates = (await client.get("/templates")).json()
    session = (
        await client.post(
            "/sessions",
            json={
                "template_id": templates[0]["id"],
                "level": "junior",
                "accept_terms": True,
            },
        )
    ).json()
    app = client._transport.app
    async with app.state.sessionmaker() as db:
        row = await db.get(InterviewSession, uuid.UUID(session["id"]))
        row.status = "grading"
        await db.commit()
    return client, app, session["id"]


async def test_enqueue_and_local_fallback(make_client):
    client, app, sid = await prepared(make_client)
    request = Request({"type": "http", "app": app})
    app.state.settings.redis_url = "redis://unused"
    app.state.redis = AsyncMock()
    background = BackgroundTasks()
    await dispatch_grading(request, background, uuid.UUID(sid))
    app.state.redis.enqueue_job.assert_awaited_once_with(
        "grade_session", sid, _job_id=f"grade:{sid}"
    )
    assert not background.tasks
    app.state.settings.redis_url = ""
    app.state.grader = AsyncMock()
    await dispatch_grading(request, background, uuid.UUID(sid))
    await background()
    app.state.grader.grade.assert_awaited_once()
    app.state.redis = None
    await client.aclose()


async def test_retries_are_bounded_and_completed_jobs_do_nothing(make_client):
    client, app, sid = await prepared(make_client)
    grader = AsyncMock()
    grader.grade.side_effect = RuntimeError("provider unavailable")
    ctx = {"sessionmaker": app.state.sessionmaker, "grader": grader, "job_try": 1}
    with pytest.raises(Retry):
        await grade_session(ctx, sid)
    ctx["job_try"] = 3
    await grade_session(ctx, sid)
    async with app.state.sessionmaker() as db:
        row = await db.get(InterviewSession, uuid.UUID(sid))
        assert row.status == "failed"
        assert row.report is None
        assert "three attempts" in row.error
    await grade_session(ctx, sid)
    assert grader.grade.await_count == 2
    await client.aclose()


@pytest.mark.skipif(not os.getenv("GETTER_TEST_REDIS_URL"), reason="requires test Redis")
async def test_real_arq(make_client):
    client, app, sid = await prepared(make_client)
    pool = await create_pool(RedisSettings.from_dsn(os.environ["GETTER_TEST_REDIS_URL"]))
    queue = f"test:{uuid.uuid4()}"
    job = await pool.enqueue_job("grade_session", sid, _queue_name=queue)
    worker = Worker(
        [grade_session],
        redis_pool=pool,
        queue_name=queue,
        burst=True,
        handle_signals=False,
        ctx={"sessionmaker": app.state.sessionmaker, "grader": app.state.grader},
    )
    try:
        await worker.async_run()
        assert await job.result() is None
        async with app.state.sessionmaker() as db:
            row = await db.get(InterviewSession, uuid.UUID(sid))
            assert row.status == "completed"
            assert row.report is not None
        await grade_session({"sessionmaker": app.state.sessionmaker, "grader": AsyncMock()}, sid)
    finally:
        await worker.close()
        await pool.aclose()
        await client.aclose()
