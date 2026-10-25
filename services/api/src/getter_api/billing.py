"""Paid interview packs through Razorpay.

Flow: the site asks for an order, opens Razorpay Checkout, and sends the result to
`/billing/verify`. The Razorpay webhook is the backstop if the candidate closes the
tab. Both paths check an HMAC signature and call `grant_payment`, which credits the
account once per payment however often it is called. Credits are a ledger; the balance
is the sum. Card details never reach Getter.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime
from typing import Any, Protocol

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from getter_api.models import CreditEntry, Payment, User
from getter_api.settings import CreditPack, Settings


class PaymentsUnavailableError(Exception):
    """Razorpay is not configured or did not answer."""


class RazorpayApi(Protocol):
    async def create_order(
        self, amount_paise: int, receipt: str, notes: dict[str, str]
    ) -> dict[str, Any]: ...


class RazorpayClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.http = http or httpx.AsyncClient(timeout=15)

    async def create_order(
        self, amount_paise: int, receipt: str, notes: dict[str, str]
    ) -> dict[str, Any]:
        try:
            resp = await self.http.post(
                f"{self.settings.razorpay_api_url}/orders",
                auth=(self.settings.razorpay_key_id, self.settings.razorpay_key_secret),
                json={
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": receipt,
                    "notes": notes,
                },
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise PaymentsUnavailableError("could not create the order with Razorpay") from exc
        if not isinstance(data.get("id"), str):
            raise PaymentsUnavailableError("Razorpay returned an unexpected order")
        return data


def payments_enabled(settings: Settings) -> bool:
    return bool(settings.razorpay_key_id and settings.razorpay_key_secret)


def find_pack(settings: Settings, pack_id: str) -> CreditPack | None:
    return next((p for p in settings.credit_packs if p.id == pack_id), None)


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def checkout_signature_valid(settings: Settings, order_id: str, payment_id: str, sig: str) -> bool:
    """Razorpay signs `order_id|payment_id` with the key secret after a Checkout payment."""
    if not settings.razorpay_key_secret:
        return False
    expected = _hmac_hex(settings.razorpay_key_secret, f"{order_id}|{payment_id}".encode())
    return hmac.compare_digest(expected, sig)


def webhook_signature_valid(settings: Settings, body: bytes, sig: str) -> bool:
    if not settings.razorpay_webhook_secret:
        return False
    return hmac.compare_digest(_hmac_hex(settings.razorpay_webhook_secret, body), sig)


async def balance(db: AsyncSession, user_id: uuid.UUID) -> int:
    total = await db.scalar(
        select(func.coalesce(func.sum(CreditEntry.delta), 0)).where(CreditEntry.user_id == user_id)
    )
    return int(total or 0)


async def grant_payment(
    db: AsyncSession, payment: Payment, razorpay_payment_id: str, now: datetime
) -> bool:
    """Mark the order paid and credit the account. True the first time, False on repeats."""
    # Lock the order so a webhook and a verify call for the same payment cannot both grant.
    locked = await db.scalar(
        select(Payment)
        .where(Payment.id == payment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert locked is not None
    if locked.status == "paid":
        return False
    locked.status = "paid"
    locked.razorpay_payment_id = razorpay_payment_id
    locked.paid_at = now
    db.add(
        CreditEntry(
            user_id=locked.user_id, delta=locked.credits, reason="purchase", payment_id=locked.id
        )
    )
    return True


async def spend_credit(db: AsyncSession, user: User, session_id: uuid.UUID) -> bool:
    """Use one credit for a new interview. False when the account has none.

    The caller holds the user row lock (check_free_limits takes it), so two requests
    cannot spend the same credit."""
    if await balance(db, user.id) < 1:
        return False
    db.add(CreditEntry(user_id=user.id, delta=-1, reason="interview", session_id=session_id))
    return True
