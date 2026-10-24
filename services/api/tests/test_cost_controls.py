from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from getter_api.models import LLMCall, User
from tests.test_interview_api import ALICE, LONG_ANSWER, answer, start


async def seed(client, sid, cost, now, user_email="alice@example.com"):
    async with client._transport.app.state.sessionmaker() as db:
        user = await db.scalar(select(User).where(User.email == user_email))
        db.add(
            LLMCall(
                session_id=uuid.UUID(sid),
                user_id=user.id,
                task="grading",
                provider="dev",
                model="offline",
                input_tokens=1,
                output_tokens=1,
                cost_inr=cost,
                latency_ms=1,
                ok=True,
                created_at=now,
            )
        )
        await db.commit()


@pytest.mark.parametrize("cost,blocked", [(9.99, False), (10, True), (10.01, True)])
@pytest.mark.parametrize("limit", ["account", "global"])
async def test_cost_edges(make_client, clock, cost, blocked, limit):
    client = await make_client(
        free_sessions_per_day=100,
        free_account_cost_inr=10 if limit == "account" else 1000,
        global_daily_cost_inr=10 if limit == "global" else 1000,
    )
    session = await start(client)
    await seed(client, session["id"], cost, clock())
    response = await client.post(
        "/sessions",
        headers=ALICE,
        json={
            "template_id": session["template_id"],
            "level": "junior",
            "accept_terms": True,
        },
    )
    assert response.status_code == (429 if blocked else 201)
    if blocked:
        assert "start again after" in response.json()["detail"]
        assert int(response.headers["retry-after"]) > 0
    # Admission caps never interrupt a running interview.
    await answer(client, session["id"], LONG_ANSWER)
    await client.aclose()


async def test_account_window_and_deletion_do_not_reset_spend(make_client, clock):
    client = await make_client(free_account_cost_inr=10, free_sessions_per_day=100)
    session = await start(client)
    await seed(client, session["id"], 10, clock())
    await client.delete(f"/sessions/{session['id']}", headers=ALICE)
    body = {"template_id": session["template_id"], "level": "junior", "accept_terms": True}
    assert (await client.post("/sessions", headers=ALICE, json=body)).status_code == 429
    # Another account has its own allowance.
    assert (
        await client.post("/sessions", headers={"x-dev-user-email": "bob@example.com"}, json=body)
    ).status_code == 201
    clock.advance(hours=24)
    assert (await client.post("/sessions", headers=ALICE, json=body)).status_code == 201
    await client.aclose()


async def test_global_midnight_and_average_warning(make_client, clock, caplog):
    client = await make_client(global_daily_cost_inr=10, session_cost_warning_inr=5)
    session = await start(client)
    await seed(client, session["id"], 10, clock())
    body = {"template_id": session["template_id"], "level": "junior", "accept_terms": True}
    assert (
        await client.post("/sessions", headers={"x-dev-user-email": "bob@example.com"}, json=body)
    ).status_code == 429
    assert "Average practice cost" in caplog.text
    clock.now = clock.now.replace(hour=0, minute=0) + timedelta(days=1)
    assert (await client.post("/sessions", headers=ALICE, json=body)).status_code == 201
    await client.aclose()


async def test_real_model_call_keeps_account_attribution(make_client, clock):
    client = await make_client(free_account_cost_inr=10, free_sessions_per_day=100)
    session = await start(client)
    await answer(client, session["id"], LONG_ANSWER)
    async with client._transport.app.state.sessionmaker() as db:
        user = await db.scalar(select(User).where(User.email == "alice@example.com"))
        calls = list(
            await db.scalars(select(LLMCall).where(LLMCall.session_id == uuid.UUID(session["id"])))
        )
        assert calls
        assert all(call.user_id == user.id for call in calls)
        # The offline model costs zero; simulate billing on a real recorded call.
        calls[0].cost_inr = 10
        calls[0].created_at = clock()
        await db.commit()
    await client.delete(f"/sessions/{session['id']}", headers=ALICE)
    body = {"template_id": session["template_id"], "level": "junior", "accept_terms": True}
    response = await client.post("/sessions", headers=ALICE, json=body)
    assert response.status_code == 429
    await client.aclose()
