"""The progress view: own graded history only, oldest first, no scores from broken sessions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from getter_api.llm.config import load_llm_config
from getter_api.llm.gateway import LLMGateway
from getter_api.models import AuditLog, InterviewSession, LearningItem
from tests.conftest import FakeClock, as_user
from tests.test_interview_api import LONG_ANSWER, BrokenGrader, answer, start

ALICE = as_user("alice@example.com")
BOB = as_user("bob@example.com")


async def finish(
    client: Any, clock: FakeClock, headers: dict[str, str] = ALICE, **kwargs: str
) -> str:
    session = await start(client, headers=headers, **kwargs)
    await answer(client, session["id"], LONG_ANSWER, headers=headers)
    await client.post(f"/sessions/{session['id']}/end", headers=headers)
    clock.advance(hours=1)
    return str(session["id"])


async def test_progress_is_empty_without_graded_sessions(make_client: Any) -> None:
    client = await make_client()
    resp = await client.get("/progress", headers=ALICE)
    assert resp.status_code == 200
    assert resp.json() == {"roles": []}
    assert (await client.get("/progress")).status_code == 401


async def test_history_is_ordered_with_latest_and_previous(
    make_client: Any, clock: FakeClock
) -> None:
    client = await make_client(free_sessions_per_day=20)
    ids = [await finish(client, clock) for _ in range(3)]
    await start(client)  # an unfinished session adds nothing
    await finish(client, clock, level="junior")  # a different level is its own group

    body = (await client.get("/progress", headers=ALICE)).json()
    assert [(r["level"], r["sessions"]) for r in body["roles"]] == [("junior", 1), ("mid", 3)]
    junior, mid = body["roles"]
    assert mid["skills"]
    for skill in mid["skills"]:
        assert [p["session_id"] for p in skill["points"]] == ids
        dates = [p["date"] for p in skill["points"]]
        assert dates == sorted(dates)
        assert skill["latest"] == skill["points"][-1]["score"]
        assert skill["previous"] == skill["points"][-2]["score"]
        assert skill["delta"] == skill["latest"] - skill["previous"]
        assert skill["name"] != skill["skill_id"]
    assert all(s["previous"] is None and s["delta"] is None for s in junior["skills"])


async def test_delta_follows_the_two_latest_scores(make_client: Any, clock: FakeClock) -> None:
    client = await make_client()
    await finish(client, clock)
    await finish(client, clock)
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.sessionmaker() as db:
        sessions = list(
            await db.scalars(select(InterviewSession).order_by(InterviewSession.created_at))
        )
        for session, value in zip(sessions, (1, 3), strict=True):
            assert session.report is not None
            for score in session.report.skill_scores:
                score.score = value
        await db.commit()
    skills = (await client.get("/progress", headers=ALICE)).json()["roles"][0]["skills"]
    assert all(s["previous"] == 1 and s["latest"] == 3 and s["delta"] == 2 for s in skills)


async def test_other_users_data_is_never_included(make_client: Any, clock: FakeClock) -> None:
    client = await make_client()
    await finish(client, clock)
    await finish(client, clock, headers=BOB)
    await finish(client, clock, headers=BOB)
    alice = (await client.get("/progress", headers=ALICE)).json()
    bob = (await client.get("/progress", headers=BOB)).json()
    assert alice["roles"][0]["sessions"] == 1
    assert bob["roles"][0]["sessions"] == 2
    own = {p["session_id"] for r in alice["roles"] for s in r["skills"] for p in s["points"]}
    other = {p["session_id"] for r in bob["roles"] for s in r["skills"] for p in s["points"]}
    assert own and other and not own & other
    carol = await client.get("/progress", headers=as_user("carol@example.com"))
    assert carol.json() == {"roles": []}


async def test_failed_and_ungraded_sessions_add_no_scores(make_client: Any) -> None:
    gateway = LLMGateway(load_llm_config(), {"dev": BrokenGrader()})
    client = await make_client(gateway)
    session = await start(client)
    await answer(client, session["id"], LONG_ANSWER)
    await client.post(f"/sessions/{session['id']}/end", headers=ALICE)
    await start(client)  # still in progress
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.sessionmaker() as db:
        statuses = {s.status for s in await db.scalars(select(InterviewSession))}
    assert statuses == {"failed", "in_progress"}
    assert (await client.get("/progress", headers=ALICE)).json() == {"roles": []}


async def test_recurring_gaps_count_sessions_and_the_view_is_audited(
    make_client: Any, clock: FakeClock
) -> None:
    client = await make_client()
    for _ in range(2):
        await finish(client, clock)
    await finish(client, clock, headers=BOB)
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.sessionmaker() as db:
        sessions = list(
            await db.scalars(select(InterviewSession).order_by(InterviewSession.created_at))
        )
        for i, session in enumerate(sessions):
            assert session.report is not None
            for li in list(session.report.learning_items):
                await db.delete(li)
            skill_id = "reliability" if i < 2 else "api_design"
            title = f"Gap {i}"
            session.report.learning_items = [
                LearningItem(
                    position=0, skill_id=skill_id, title=title, detail="d", practice={"items": []}
                )
            ]
        await db.commit()
    body = (await client.get("/progress", headers=ALICE)).json()
    gaps = body["roles"][0]["gaps"]
    assert [(g["skill_id"], g["sessions"], g["title"]) for g in gaps] == [
        ("reliability", 2, "Gap 1")
    ]
    async with app.state.sessionmaker() as db:
        actions = [a.action for a in await db.scalars(select(AuditLog))]
    assert "progress.view" in actions
