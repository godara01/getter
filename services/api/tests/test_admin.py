"""Admin API: authorization, re-grading, deletion requests and audit entries."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from sqlalchemy import func, select

from getter_api.llm.config import load_llm_config
from getter_api.llm.gateway import LLMGateway
from getter_api.models import (
    AuditLog,
    Consent,
    FeedbackReport,
    InterviewSession,
    SessionTurn,
    SkillScore,
    User,
    Waitlist,
)
from tests.conftest import as_user
from tests.test_interview_api import (
    ALICE,
    LONG_ANSWER,
    BrokenGrader,
    answer,
    start,
    total_questions,
)

ADMIN = as_user("root@example.com")
OVERRIDES = {"admin_emails": ["Root@Example.com"]}


async def finished(client: httpx.AsyncClient, headers: dict[str, str] = ALICE) -> str:
    session = await start(client, headers=headers)
    for _ in range(total_questions("backend-junior-mid")):
        session = await answer(client, session["id"], LONG_ANSWER, headers)
    assert session["status"] == "grading"
    return str(session["id"])


async def count(client: httpx.AsyncClient, model: Any) -> int:
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.sessionmaker() as db:
        return int(await db.scalar(select(func.count()).select_from(model)) or 0)


async def audit_actions(client: httpx.AsyncClient) -> list[str]:
    resp = await client.get("/admin/audit", headers=ADMIN)
    assert resp.status_code == 200
    return [r["action"] for r in resp.json()]


async def test_admin_routes_require_sign_in_and_admin_role(make_client: Any) -> None:
    client = await make_client(**OVERRIDES)
    sid = await finished(client)
    someone = uuid.uuid4()
    calls = [
        ("GET", "/admin/sessions"),
        ("GET", f"/admin/sessions/{sid}"),
        ("POST", f"/admin/sessions/{sid}/regrade"),
        ("POST", f"/admin/users/{someone}/deletion"),
        ("GET", "/admin/audit"),
    ]
    for method, path in calls:
        assert (await client.request(method, path)).status_code == 401, path
        resp = await client.request(method, path, headers=ALICE)
        assert resp.status_code == 403, path
    # Nothing was changed or read by the refused calls.
    assert await count(client, AuditLog) == 0
    assert (await client.get("/admin/sessions", headers=ADMIN)).status_code == 200


async def test_admin_cannot_be_self_assigned(make_client: Any) -> None:
    client = await make_client()  # no admin emails configured
    resp = await client.get("/admin/sessions", headers=ADMIN)
    assert resp.status_code == 403
    # A role column set in the database is the other way in.
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.sessionmaker() as db:
        user = await db.scalar(select(User).where(User.email == "root@example.com"))
        assert user is not None
        user.role = "admin"
        await db.commit()
    assert (await client.get("/admin/sessions", headers=ADMIN)).status_code == 200


async def test_list_sessions_filters_and_hides_content(make_client: Any) -> None:
    client = await make_client(**OVERRIDES)
    sid = await finished(client)
    other = await start(client, headers=as_user("bob@example.com"))
    rows = (await client.get("/admin/sessions", headers=ADMIN)).json()
    assert {r["id"] for r in rows} == {sid, other["id"]}
    row = next(r for r in rows if r["id"] == sid)
    assert row["status"] == "completed"
    assert row["verdict"] in {"meets", "above"}
    assert "turns" not in row and "email" not in row
    only = await client.get("/admin/sessions", params={"status": "in_progress"}, headers=ADMIN)
    assert [r["id"] for r in only.json()] == [other["id"]]
    by_user = await client.get("/admin/sessions", params={"user_id": row["user_id"]}, headers=ADMIN)
    assert [r["id"] for r in by_user.json()] == [sid]
    costly = await client.get("/admin/sessions", params={"min_cost_inr": 1000}, headers=ADMIN)
    assert costly.json() == []
    assert (
        await client.get("/admin/sessions", params={"limit": 0}, headers=ADMIN)
    ).status_code == 422


async def test_reading_a_session_is_audited(make_client: Any) -> None:
    client = await make_client(**OVERRIDES)
    sid = await finished(client)
    resp = await client.get(f"/admin/sessions/{sid}", headers=ADMIN)
    detail = resp.json()
    assert any(t["text"] == LONG_ANSWER for t in detail["turns"])
    assert detail["scores"] and all(s["evidence"] for s in detail["scores"])
    assert (await client.get(f"/admin/sessions/{uuid.uuid4()}", headers=ADMIN)).status_code == 404
    entries = (
        await client.get("/admin/audit", params={"action": "admin.session.view"}, headers=ADMIN)
    ).json()
    assert [(e["target_type"], e["target_id"]) for e in entries] == [("session", sid)]
    assert entries[0]["actor_user_id"] is not None


async def test_regrade_replaces_the_report_and_is_idempotent(make_client: Any) -> None:
    client = await make_client(**OVERRIDES)
    sid = await finished(client)
    before = (await client.get(f"/sessions/{sid}/report", headers=ALICE)).json()
    assert await count(client, FeedbackReport) == 1

    resp = await client.post(f"/admin/sessions/{sid}/regrade", headers=ADMIN)
    assert resp.status_code == 202
    after = (await client.get(f"/sessions/{sid}/report", headers=ALICE)).json()
    assert after["verdict"] == before["verdict"]
    assert await count(client, FeedbackReport) == 1
    assert await count(client, SkillScore) == len(before["skills"])
    for skill in after["skills"]:
        assert all(e["quote"] for e in skill["evidence"])

    # A session already waiting for grading is only queued again, never duplicated.
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.sessionmaker() as db:
        row = await db.get(InterviewSession, uuid.UUID(sid))
        assert row is not None
        row.status = "grading"
        await db.commit()
    for _ in range(2):
        assert (
            await client.post(f"/admin/sessions/{sid}/regrade", headers=ADMIN)
        ).status_code == 202
    assert await count(client, FeedbackReport) == 1
    actions = await audit_actions(client)
    assert actions.count("admin.session.regrade") == 3


async def test_regrade_refuses_unfinished_sessions(make_client: Any) -> None:
    client = await make_client(**OVERRIDES)
    running = await start(client)
    resp = await client.post(f"/admin/sessions/{running['id']}/regrade", headers=ADMIN)
    assert resp.status_code == 409
    resp = await client.post(f"/admin/sessions/{uuid.uuid4()}/regrade", headers=ADMIN)
    assert resp.status_code == 404


async def test_regrade_of_a_failed_session_keeps_grading_rules(make_client: Any) -> None:
    broken = LLMGateway(load_llm_config(), {"dev": BrokenGrader()})
    client = await make_client(broken, **OVERRIDES)
    sid = await finished(client)
    assert (await client.get(f"/sessions/{sid}/report", headers=ALICE)).status_code == 409
    # Still unusable output: the retry fails again and no score appears.
    assert (await client.post(f"/admin/sessions/{sid}/regrade", headers=ADMIN)).status_code == 202
    assert (await client.get(f"/sessions/{sid}/report", headers=ALICE)).status_code == 409
    assert await count(client, FeedbackReport) == 0
    # With a working model the same session now gets a normal, evidence-backed report.
    app = client._transport.app  # type: ignore[attr-defined]
    app.state.grader.gateway = LLMGateway(load_llm_config())
    assert (await client.post(f"/admin/sessions/{sid}/regrade", headers=ADMIN)).status_code == 202
    report = (await client.get(f"/sessions/{sid}/report", headers=ALICE)).json()
    assert report["verdict"] in {"meets", "above"}
    async with app.state.sessionmaker() as db:
        row = await db.get(InterviewSession, uuid.UUID(sid))
        assert row is not None
        assert row.error is None


async def test_deletion_request_leaves_no_personal_data(make_client: Any) -> None:
    client = await make_client(**OVERRIDES)
    sid = await finished(client)
    await finished(client, as_user("bob@example.com"))
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.sessionmaker() as db:
        user = await db.scalar(select(User).where(User.email == "alice@example.com"))
        assert user is not None
        user.name = "Alice Example"
        db.add(Waitlist(email="alice@example.com", role_interest="backend"))
        await db.commit()
        alice_id = user.id
    await client.get(f"/sessions/{sid}/report", headers=ALICE)  # a candidate-side audit entry

    resp = await client.post(f"/admin/users/{alice_id}/deletion", headers=ADMIN)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["already_deleted"] is False and body["sessions_deleted"] == 1
    assert body["consents_deleted"] >= 1 and body["waitlist_deleted"] == 1

    async with app.state.sessionmaker() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(InterviewSession)
                .where(InterviewSession.user_id == alice_id)
            )
            == 0
        )
        assert (
            await db.scalar(
                select(func.count()).select_from(Consent).where(Consent.user_id == alice_id)
            )
            == 0
        )
        assert await db.scalar(select(func.count()).select_from(Waitlist)) == 0
        user = await db.get(User, alice_id)
        assert user is not None and user.deleted_at is not None
        assert user.name is None and "alice" not in user.email
        # Only bob's data remains anywhere.
        bob_sessions = await db.scalar(select(func.count()).select_from(InterviewSession))
        assert bob_sessions == 1
        assert await db.scalar(select(func.count()).select_from(FeedbackReport)) == 1
        assert await db.scalar(select(func.count()).select_from(SkillScore)) > 0
        turn_owners = set(await db.scalars(select(SessionTurn.session_id)))
        assert uuid.UUID(sid) not in turn_owners and turn_owners
        details = [
            str(a.details) + a.target_id + a.action for a in await db.scalars(select(AuditLog))
        ]
        assert not any("alice" in d.lower() for d in details)
        tomb = await db.scalar(select(AuditLog).where(AuditLog.action == "admin.user.deletion"))
        assert tomb is not None and tomb.target_id == str(alice_id)
        assert tomb.details["sessions"] == 1

    # She is signed out for good, repeating is harmless, and the audit trail has one tombstone.
    assert (await client.get("/sessions", headers=ALICE)).json() == []
    again = (await client.post(f"/admin/users/{alice_id}/deletion", headers=ADMIN)).json()
    assert again["already_deleted"] is True
    actions = await audit_actions(client)
    assert actions.count("admin.user.deletion") == 1


async def test_deletion_guards(make_client: Any) -> None:
    client = await make_client(**OVERRIDES)
    resp = await client.post(f"/admin/users/{uuid.uuid4()}/deletion", headers=ADMIN)
    assert resp.status_code == 404
    await client.get("/admin/sessions", headers=ADMIN)
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.sessionmaker() as db:
        me = await db.scalar(select(User).where(User.email == "root@example.com"))
        assert me is not None
        my_id = me.id
    resp = await client.post(f"/admin/users/{my_id}/deletion", headers=ADMIN)
    assert resp.status_code == 409


async def test_audit_log_filters(make_client: Any) -> None:
    client = await make_client(**OVERRIDES)
    sid = await finished(client)
    await client.get(f"/admin/sessions/{sid}", headers=ADMIN)
    await client.post(f"/admin/sessions/{sid}/regrade", headers=ADMIN)
    rows = (await client.get("/admin/audit", params={"target_id": sid}, headers=ADMIN)).json()
    assert {r["action"] for r in rows} == {"admin.session.view", "admin.session.regrade"}
    rows = (await client.get("/admin/audit", params={"target_type": "user"}, headers=ADMIN)).json()
    assert rows == []
    assert (
        await client.get("/admin/audit", params={"limit": 1}, headers=ADMIN)
    ).json().__len__() == 1


def test_cli_sends_the_right_requests(monkeypatch: Any, capsys: Any) -> None:
    from getter_api.admin import __main__ as cli

    sent: list[tuple[str, str, dict[str, Any]]] = []

    def fake(method: str, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        sent.append((method, path, params or {}))
        return []

    monkeypatch.setattr(cli, "call", fake)
    cli.main(["sessions", "--status", "failed"])
    cli.main(["regrade", "abc"])
    cli.main(["delete-user", "u1"])
    cli.main(["audit", "--action", "admin.session.view"])
    assert sent[0][:2] == ("GET", "/admin/sessions") and sent[0][2]["status"] == "failed"
    assert sent[1][:2] == ("POST", "/admin/sessions/abc/regrade")
    assert sent[2][:2] == ("POST", "/admin/users/u1/deletion")
    assert sent[3][:2] == ("GET", "/admin/audit")
    assert capsys.readouterr().out.count("[]") == 4
