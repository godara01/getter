from __future__ import annotations

from sqlalchemy import select

from getter_api.models import AuditLog, Consent, Waitlist
from tests.test_interview_api import ALICE, BOB, LONG_ANSWER, answer, start


async def test_waitlist_validation_deduplication_and_rate_limit(make_client, clock):
    client = await make_client(waitlist_requests_per_hour=3)
    body = {"email": "  Candidate@Example.com ", "role_interest": "backend"}
    assert (await client.post("/waitlist", json={**body, "email": "invalid"})).status_code == 422
    assert (
        await client.post("/waitlist", json={**body, "role_interest": "invalid"})
    ).status_code == 422
    first = await client.post("/waitlist", json=body)
    assert first.status_code == 202
    assert (await client.post("/waitlist", json=body)).json() == first.json()
    assert (await client.post("/waitlist", json=body)).status_code == 202
    assert (await client.post("/waitlist", json=body)).status_code == 429
    clock.advance(hours=1)
    assert (await client.post("/waitlist", json=body)).status_code == 202
    async with client._transport.app.state.sessionmaker() as db:
        rows = list(await db.scalars(select(Waitlist)))
        assert len(rows) == 1
        assert rows[0].email == "candidate@example.com"
    await client.aclose()


async def test_signup_session_consents_and_withdrawal(make_client, clock):
    client = await make_client()
    terms = {"accept_terms": True, "text_version": "practice-terms-draft-v1"}
    assert (
        await client.post("/account/terms", headers=ALICE, json={**terms, "accept_terms": False})
    ).status_code == 422
    assert (
        await client.post("/account/terms", headers=ALICE, json={**terms, "text_version": "old"})
    ).status_code == 422
    signup = (await client.post("/account/terms", headers=ALICE, json=terms)).json()
    assert (await client.post("/account/terms", headers=ALICE, json=terms)).json()["id"] == signup[
        "id"
    ]
    await start(client)
    records = (await client.get("/consents", headers=ALICE)).json()
    assert {r["kind"] for r in records} == {"signup_terms", "practice_terms"}
    assert all(r["text_version"] == terms["text_version"] for r in records)
    assert (await client.get("/consents", headers=BOB)).json() == []
    assert (await client.delete(f"/consents/{signup['id']}", headers=BOB)).status_code == 404
    clock.advance(minutes=5)
    assert (await client.delete(f"/consents/{signup['id']}", headers=ALICE)).status_code == 204
    async with client._transport.app.state.sessionmaker() as db:
        row = await db.scalar(select(Consent).where(Consent.kind == "signup_terms"))
        assert row.granted is False
    assert (await client.post("/account/terms", headers=ALICE, json=terms)).json()["id"] != signup[
        "id"
    ]
    await client.aclose()


async def test_audit_views_and_deletion_are_private(make_client):
    client = await make_client()
    session = await start(client)
    sid = session["id"]
    await answer(client, sid, LONG_ANSWER)
    await client.post(f"/sessions/{sid}/end", headers=ALICE)
    assert (await client.get(f"/sessions/{sid}/report", headers=BOB)).status_code == 404
    assert (await client.get(f"/sessions/{sid}/report", headers=ALICE)).status_code == 200
    assert (await client.get("/sessions", headers=ALICE)).status_code == 200
    assert (await client.delete(f"/sessions/{sid}", headers=ALICE)).status_code == 204
    async with client._transport.app.state.sessionmaker() as db:
        entries = list(await db.scalars(select(AuditLog).order_by(AuditLog.created_at)))
        assert [entry.action for entry in entries] == [
            "report.view",
            "score.view",
            "session.delete",
        ]
        assert all(entry.target_id == sid for entry in entries)
    await client.aclose()
