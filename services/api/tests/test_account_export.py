"""Candidates can download everything stored about them."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from getter_api.models import AuditLog
from tests.conftest import as_user
from tests.test_interview_api import ALICE, BOB, LONG_ANSWER, answer, start


async def test_export_includes_own_data_only(make_client: Any) -> None:
    client = await make_client()
    session = await start(client)
    await answer(client, session["id"], LONG_ANSWER)
    await start(client, headers=BOB)

    resp = await client.get("/account/export", headers=ALICE)
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    data = resp.json()
    assert data["account"]["email"] == "alice@example.com"
    assert len(data["interviews"]) == 1
    interview = data["interviews"][0]
    assert interview["id"] == session["id"]
    assert any(t["text"] == LONG_ANSWER for t in interview["transcript"])
    assert {c["kind"] for c in data["consents"]} >= {"practice_terms"}
    assert "bob@example.com" not in resp.text
    assert data["payments"] == [] and data["credit_ledger"] == []


async def test_export_includes_finished_reports(make_client: Any) -> None:
    client = await make_client()
    session = await start(client)
    await answer(client, session["id"], LONG_ANSWER)
    await client.post(f"/sessions/{session['id']}/end", headers=ALICE)
    assert (await client.get(f"/sessions/{session['id']}/report", headers=ALICE)).status_code == 200
    data = (await client.get("/account/export", headers=ALICE)).json()
    report = data["interviews"][0]["report"]
    assert report is not None and report["skills"]


async def test_export_needs_sign_in_and_is_audited(make_client: Any) -> None:
    client = await make_client()
    assert (await client.get("/account/export")).status_code in (401, 403)
    await client.get("/account/export", headers=as_user("carol@example.com"))
    sessionmaker = client._transport.app.state.sessionmaker  # type: ignore[attr-defined]
    async with sessionmaker() as db:
        actions = list(await db.scalars(select(AuditLog.action)))
    assert "account.export" in actions
