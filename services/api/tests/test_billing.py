"""Razorpay packs: orders, signature checks, idempotent credits and spending them."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select

from getter_api.billing import PaymentsUnavailableError, RazorpayClient
from getter_api.models import AuditLog, CreditEntry, Payment
from getter_api.settings import Settings
from tests.conftest import as_user
from tests.test_interview_api import ALICE, BOB, start

KEYS = {
    "razorpay_key_id": "rzp_test_key",
    "razorpay_key_secret": "key-secret",
    "razorpay_webhook_secret": "hook-secret",
}


class FakeRazorpay:
    def __init__(self, fail: bool = False) -> None:
        self.orders: list[dict[str, Any]] = []
        self.fail = fail

    async def create_order(
        self, amount_paise: int, receipt: str, notes: dict[str, str]
    ) -> dict[str, Any]:
        if self.fail:
            raise PaymentsUnavailableError("down")
        order = {"id": f"order_{len(self.orders) + 1}", "amount": amount_paise, "notes": notes}
        self.orders.append(order)
        return order


def sign(secret: str, message: str | bytes) -> str:
    raw = message.encode() if isinstance(message, str) else message
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


async def billing_client(make_client: Any, razorpay: Any = None, **overrides: Any) -> Any:
    client = await make_client(**{**KEYS, **overrides})
    client._transport.app.state.razorpay = razorpay or FakeRazorpay()
    return client


async def order(client: httpx.AsyncClient, pack: str = "pack-5", headers: Any = ALICE) -> Any:
    return await client.post("/billing/orders", json={"pack_id": pack}, headers=headers)


async def verify(
    client: httpx.AsyncClient, order_id: str, payment_id: str = "pay_1", headers: Any = ALICE
) -> Any:
    body = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": sign("key-secret", f"{order_id}|{payment_id}"),
    }
    return await client.post("/billing/verify", json=body, headers=headers)


async def test_payments_are_off_without_keys(make_client: Any) -> None:
    client = await make_client()
    info = (await client.get("/billing", headers=ALICE)).json()
    assert info["enabled"] is False and info["credits"] == 0
    assert [p["id"] for p in info["packs"]] == ["pack-5", "pack-15"]
    resp = await order(client)
    assert resp.status_code == 503


async def test_order_uses_the_server_side_price(make_client: Any) -> None:
    razorpay = FakeRazorpay()
    client = await billing_client(make_client, razorpay)
    resp = await order(client, "pack-15")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["amount_paise"], body["currency"], body["key_id"]) == (
        119900,
        "INR",
        "rzp_test_key",
    )
    assert razorpay.orders[0]["amount"] == 119900
    assert "key-secret" not in resp.text
    assert (await order(client, "free-lunch")).status_code == 422


async def test_razorpay_down_gives_a_retryable_error(make_client: Any) -> None:
    client = await billing_client(make_client, FakeRazorpay(fail=True))
    resp = await order(client)
    assert resp.status_code == 502
    assert "try again" in resp.json()["detail"]


async def test_verified_payment_adds_credits_once(make_client: Any) -> None:
    client = await billing_client(make_client)
    order_id = (await order(client)).json()["order_id"]
    first = await verify(client, order_id)
    assert first.json() == {"credits": 5, "already_applied": False}
    again = await verify(client, order_id)
    assert again.json() == {"credits": 5, "already_applied": True}
    assert (await client.get("/billing", headers=ALICE)).json()["credits"] == 5


async def test_bad_signature_and_other_accounts_cannot_claim(make_client: Any) -> None:
    client = await billing_client(make_client)
    order_id = (await order(client)).json()["order_id"]
    bad = await client.post(
        "/billing/verify",
        json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": "pay_1",
            "razorpay_signature": "0" * 64,
        },
        headers=ALICE,
    )
    assert bad.status_code == 400
    assert (await verify(client, order_id, headers=BOB)).status_code == 404
    assert (await client.get("/billing", headers=ALICE)).json()["credits"] == 0


def webhook_body(order_id: str, amount: int, event: str = "payment.captured") -> bytes:
    entity = {"id": "pay_9", "order_id": order_id, "amount": amount, "status": "captured"}
    return json.dumps({"event": event, "payload": {"payment": {"entity": entity}}}).encode()


async def post_hook(client: httpx.AsyncClient, body: bytes, secret: str = "hook-secret") -> Any:
    return await client.post(
        "/billing/webhook", content=body, headers={"x-razorpay-signature": sign(secret, body)}
    )


async def test_webhook_credits_the_account_and_is_idempotent(make_client: Any) -> None:
    client = await billing_client(make_client)
    order_id = (await order(client)).json()["order_id"]
    body = webhook_body(order_id, 49900)
    assert (await post_hook(client, body)).json() == {"status": "ok"}
    assert (await post_hook(client, body)).status_code == 200
    # The Checkout confirmation after the webhook does not add a second set.
    assert (await verify(client, order_id, "pay_9")).json()["credits"] == 5
    assert (await client.get("/billing", headers=ALICE)).json()["credits"] == 5


async def test_webhook_rejects_bad_signatures_wrong_amounts_and_other_events(
    make_client: Any,
) -> None:
    client = await billing_client(make_client)
    order_id = (await order(client)).json()["order_id"]
    body = webhook_body(order_id, 49900)
    assert (await post_hook(client, body, "wrong-secret")).status_code == 400
    assert (await client.post("/billing/webhook", content=body)).status_code == 400
    assert (await post_hook(client, webhook_body(order_id, 100))).json() == {"status": "ignored"}
    assert (await post_hook(client, webhook_body(order_id, 49900, "payment.failed"))).json() == {
        "status": "ignored"
    }
    assert (await post_hook(client, b"not json")).json() == {"status": "ignored"}
    assert (await client.get("/billing", headers=ALICE)).json()["credits"] == 0


async def test_webhook_is_refused_when_no_secret_is_set(make_client: Any) -> None:
    client = await billing_client(make_client, razorpay_webhook_secret="")
    body = webhook_body("order_1", 49900)
    assert (await post_hook(client, body, "")).status_code == 400


async def test_credits_start_interviews_past_the_free_limit(make_client: Any) -> None:
    client = await billing_client(make_client, free_sessions_per_day=1)
    await start(client)
    blocked = await client.post(
        "/sessions",
        json={"template_id": "backend-junior-mid", "level": "mid", "accept_terms": True},
        headers=ALICE,
    )
    assert blocked.status_code == 429

    order_id = (await order(client)).json()["order_id"]
    await verify(client, order_id)
    session = await start(client)
    assert session["status"] == "in_progress"
    assert (await client.get("/billing", headers=ALICE)).json()["credits"] == 4


async def test_free_interviews_do_not_spend_credits(make_client: Any) -> None:
    client = await billing_client(make_client)
    order_id = (await order(client)).json()["order_id"]
    await verify(client, order_id)
    await start(client)
    assert (await client.get("/billing", headers=ALICE)).json()["credits"] == 5


async def test_ledger_and_payment_records(make_client: Any, settings: Settings) -> None:
    client = await billing_client(make_client, free_sessions_per_day=1)
    order_id = (await order(client)).json()["order_id"]
    await verify(client, order_id)
    await start(client)
    session = await start(client)
    sessionmaker = client._transport.app.state.sessionmaker  # type: ignore[attr-defined]
    async with sessionmaker() as db:
        payment = await db.scalar(select(Payment))
        assert payment is not None
        assert (payment.status, payment.amount_paise, payment.razorpay_payment_id) == (
            "paid",
            49900,
            "pay_1",
        )
        entries = list(await db.scalars(select(CreditEntry).order_by(CreditEntry.created_at)))
        assert [(e.delta, e.reason) for e in entries] == [(5, "purchase"), (-1, "interview")]
        assert str(entries[1].session_id) == session["id"]
        assert await db.scalar(select(func.count()).select_from(AuditLog)) >= 1


async def test_other_accounts_have_their_own_balance(make_client: Any) -> None:
    client = await billing_client(make_client)
    order_id = (await order(client)).json()["order_id"]
    await verify(client, order_id)
    assert (await client.get("/billing", headers=as_user("c@example.com"))).json()["credits"] == 0


async def test_razorpay_client_posts_to_the_orders_endpoint() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "order_x"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = RazorpayClient(Settings(environment="test", **KEYS), http)
    order_ = await client.create_order(49900, "rcpt", {"pack": "pack-5"})
    assert order_["id"] == "order_x"
    request = seen[0]
    assert request.url.path == "/v1/orders"
    assert request.headers["authorization"].startswith("Basic ")
    assert json.loads(request.content)["amount"] == 49900

    failing = RazorpayClient(
        Settings(environment="test", **KEYS),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500))),
    )
    with pytest.raises(PaymentsUnavailableError):
        await failing.create_order(100, "r", {})
