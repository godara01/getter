"""Report-ready email and the report usefulness rating."""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from getter_api.mail import LogMailer, ResendMailer, build_mailer, notify_report_ready
from getter_api.models import Consent, InterviewSession, ReportRating, User
from getter_api.settings import Settings
from tests.conftest import as_user
from tests.test_interview_api import ALICE, BOB, LONG_ANSWER, answer, start, total_questions

TEMPLATE = "backend-junior-mid"


class Outbox:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail = fail

    async def send(self, to: str, subject: str, text: str) -> None:
        if self.fail:
            raise RuntimeError("mail provider down")
        self.sent.append((to, subject, text))


async def finish(client: httpx.AsyncClient, headers: dict[str, str] = ALICE) -> str:
    session = await start(client, TEMPLATE, headers=headers)
    for _ in range(total_questions(TEMPLATE)):
        session = await answer(client, session["id"], LONG_ANSWER, headers=headers)
    assert session["status"] == "grading"
    return session["id"]


def install(client: httpx.AsyncClient, outbox: Outbox) -> Any:
    app = client._transport.app  # type: ignore[attr-defined]
    app.state.grader.mailer = outbox
    return app


async def test_email_has_report_link_and_nothing_else(make_client: Any) -> None:
    client = await make_client(web_base_url="https://app.example.com/")
    outbox = Outbox()
    install(client, outbox)
    sid = await finish(client)
    assert (await client.get(f"/sessions/{sid}/report", headers=ALICE)).status_code == 200
    [(to, subject, text)] = outbox.sent
    assert to == "alice@example.com"
    assert f"https://app.example.com/report/?id={sid}" in text
    report = (await client.get(f"/sessions/{sid}/report", headers=ALICE)).json()
    for skill in report["skills"]:
        for e in skill["evidence"]:
            assert e["quote"] not in text
    assert report["summary"] not in text and "verdict" not in text.lower()
    assert "/4" not in text and "score" not in (subject + text).lower()


async def test_sending_failure_never_fails_grading(make_client: Any) -> None:
    client = await make_client()
    install(client, Outbox(fail=True))
    sid = await finish(client)
    resp = await client.get(f"/sessions/{sid}/report", headers=ALICE)
    assert resp.status_code == 200
    assert resp.json()["skills"]


async def test_no_email_after_consent_withdrawal(make_client: Any) -> None:
    client = await make_client()
    outbox = Outbox()
    app = install(client, outbox)
    session = await start(client, TEMPLATE)
    consents = (await client.get("/consents", headers=ALICE)).json()
    for c in consents:
        assert (await client.delete(f"/consents/{c['id']}", headers=ALICE)).status_code == 204
    for _ in range(total_questions(TEMPLATE)):
        session = await answer(client, session["id"], LONG_ANSWER)
    assert (await client.get(f"/sessions/{session['id']}/report", headers=ALICE)).status_code == 200
    assert outbox.sent == []
    async with app.state.sessionmaker() as db:
        rows = list(await db.scalars(select(Consent)))
        assert rows and not any(c.granted for c in rows)


async def test_no_email_to_unreachable_clerk_placeholder_address(make_client: Any) -> None:
    client = await make_client()
    outbox = Outbox()
    app = install(client, outbox)
    sid = await finish(client)
    async with app.state.sessionmaker() as db:
        user = await db.scalar(select(User))
        assert user is not None
        user.email = "user_1@clerk.invalid"
        await db.commit()
    async with app.state.sessionmaker() as db:
        session = await db.get(InterviewSession, uuid.UUID(sid))
        await notify_report_ready(db, outbox, app.state.settings, session)
    assert len(outbox.sent) == 1  # only the real one from grading time


def test_adapter_choice_follows_the_api_key() -> None:
    assert isinstance(build_mailer(Settings(environment="test")), LogMailer)
    keyed = build_mailer(Settings(environment="test", resend_api_key="re_x"))
    assert isinstance(keyed, ResendMailer)


async def test_resend_adapter_posts_json_with_bearer_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        mailer = ResendMailer("re_key", "Getter <a@b.c>", http)
        await mailer.send("x@example.com", "Hi", "Body")
    [req] = seen
    assert req.url == "https://api.resend.com/emails"
    assert req.headers["authorization"] == "Bearer re_key"
    assert json.loads(req.content) == {
        "from": "Getter <a@b.c>",
        "to": ["x@example.com"],
        "subject": "Hi",
        "text": "Body",
    }
    failing = httpx.MockTransport(lambda r: httpx.Response(500))
    async with httpx.AsyncClient(transport=failing) as http:
        with pytest.raises(httpx.HTTPStatusError):
            await ResendMailer("k", "f", http).send("x@example.com", "s", "t")


async def test_rating_create_edit_and_validation(make_client: Any) -> None:
    client = await make_client()
    sid = await finish(client)
    url = f"/sessions/{sid}/report/rating"
    assert (await client.get(url, headers=ALICE)).json() is None
    resp = await client.put(url, json={"rating": 4, "comment": "  Clear quotes  "}, headers=ALICE)
    assert resp.status_code == 200
    assert resp.json() == {"rating": 4, "comment": "Clear quotes"}
    resp = await client.put(url, json={"rating": 2}, headers=ALICE)
    assert resp.json() == {"rating": 2, "comment": None}
    assert (await client.get(url, headers=ALICE)).json() == {"rating": 2, "comment": None}
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.sessionmaker() as db:
        assert len(list(await db.scalars(select(ReportRating)))) == 1
    for bad in ({"rating": 0}, {"rating": 6}, {"rating": "x"}, {"rating": 3, "comment": "x" * 501}):
        assert (await client.put(url, json=bad, headers=ALICE)).status_code == 422


async def test_rating_is_owner_only_and_needs_a_report(make_client: Any) -> None:
    client = await make_client()
    sid = await finish(client)
    url = f"/sessions/{sid}/report/rating"
    assert (await client.put(url, json={"rating": 5})).status_code == 401
    assert (await client.put(url, json={"rating": 5}, headers=BOB)).status_code == 404
    assert (await client.get(url, headers=BOB)).status_code == 404
    open_session = await start(client, TEMPLATE, headers=as_user("carol@example.com"))
    carol = as_user("carol@example.com")
    resp = await client.put(
        f"/sessions/{open_session['id']}/report/rating", json={"rating": 5}, headers=carol
    )
    assert resp.status_code == 409


async def test_rating_is_removed_with_the_session(make_client: Any) -> None:
    client = await make_client()
    sid = await finish(client)
    await client.put(f"/sessions/{sid}/report/rating", json={"rating": 5}, headers=ALICE)
    assert (await client.delete(f"/sessions/{sid}", headers=ALICE)).status_code == 204
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.sessionmaker() as db:
        assert list(await db.scalars(select(ReportRating))) == []
