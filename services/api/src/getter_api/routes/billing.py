"""Interview packs: list, order, confirm and the Razorpay webhook."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from getter_api import billing
from getter_api.audit import audit
from getter_api.models import Payment
from getter_api.routes.sessions import DB, CurrentUser, Engine

router = APIRouter(prefix="/billing")


class PackOut(BaseModel):
    id: str
    title: str
    credits: int
    amount_inr: int


class BillingOut(BaseModel):
    enabled: bool
    key_id: str
    credits: int
    packs: list[PackOut]


class OrderIn(BaseModel):
    pack_id: str


class OrderOut(BaseModel):
    order_id: str
    amount_paise: int
    currency: str
    key_id: str
    pack_title: str


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyOut(BaseModel):
    credits: int
    already_applied: bool


def razorpay_of(request: Request) -> billing.RazorpayApi:
    api = getattr(request.app.state, "razorpay", None)
    if api is None:
        api = billing.RazorpayClient(request.app.state.settings)
        request.app.state.razorpay = api
    return api


@router.get("", response_model=BillingOut)
async def get_billing(db: DB, user: CurrentUser, engine: Engine) -> BillingOut:
    settings = engine.settings
    return BillingOut(
        enabled=billing.payments_enabled(settings),
        key_id=settings.razorpay_key_id,
        credits=await billing.balance(db, user.id),
        packs=[PackOut(**p.model_dump()) for p in settings.credit_packs],
    )


@router.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(
    body: OrderIn, request: Request, db: DB, user: CurrentUser, engine: Engine
) -> OrderOut:
    settings = engine.settings
    if not billing.payments_enabled(settings):
        raise HTTPException(503, "payments are not set up yet")
    pack = billing.find_pack(settings, body.pack_id)
    if pack is None:
        raise HTTPException(422, "unknown pack")
    amount = pack.amount_inr * 100
    payment_id = uuid.uuid4()
    try:
        order = await razorpay_of(request).create_order(
            amount, f"getter-{payment_id.hex[:20]}", {"user_id": str(user.id), "pack": pack.id}
        )
    except billing.PaymentsUnavailableError as exc:
        raise HTTPException(502, "could not start the payment; try again") from exc
    db.add(
        Payment(
            id=payment_id,
            user_id=user.id,
            pack_id=pack.id,
            credits=pack.credits,
            amount_paise=amount,
            currency="INR",
            razorpay_order_id=order["id"],
        )
    )
    await db.commit()
    return OrderOut(
        order_id=order["id"],
        amount_paise=amount,
        currency="INR",
        key_id=settings.razorpay_key_id,
        pack_title=pack.title,
    )


async def _payment_by_order(db: DB, order_id: str) -> Payment | None:
    return await db.scalar(select(Payment).where(Payment.razorpay_order_id == order_id))


@router.post("/verify", response_model=VerifyOut)
async def verify_payment(body: VerifyIn, db: DB, user: CurrentUser, engine: Engine) -> VerifyOut:
    """Confirm a Checkout payment from its signature and add the credits."""
    settings = engine.settings
    if not billing.checkout_signature_valid(
        settings, body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    ):
        raise HTTPException(400, "the payment could not be verified")
    payment = await _payment_by_order(db, body.razorpay_order_id)
    if payment is None or payment.user_id != user.id:
        raise HTTPException(404, "order not found")
    granted = await _grant(db, payment, body.razorpay_payment_id, engine)
    return VerifyOut(credits=await billing.balance(db, user.id), already_applied=not granted)


async def _grant(db: DB, payment: Payment, razorpay_payment_id: str, engine: Engine) -> bool:
    try:
        granted = await billing.grant_payment(db, payment, razorpay_payment_id, engine.clock())
        if granted:
            audit(db, None, "payment.paid", "payment", payment.id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return False
    return granted


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: DB, engine: Engine) -> dict[str, str]:
    """Razorpay calls this when an order is paid, even if the candidate closed the tab."""
    raw = await request.body()
    sig = request.headers.get("x-razorpay-signature", "")
    if not billing.webhook_signature_valid(engine.settings, raw, sig):
        raise HTTPException(400, "bad signature")
    try:
        event: dict[str, Any] = json.loads(raw)
        entity = event["payload"]["payment"]["entity"]
        order_id, payment_id, amount = entity["order_id"], entity["id"], entity["amount"]
    except (ValueError, KeyError, TypeError):
        return {"status": "ignored"}
    if event.get("event") not in ("payment.captured", "order.paid"):
        return {"status": "ignored"}
    payment = await _payment_by_order(db, order_id)
    if payment is None or amount != payment.amount_paise:
        return {"status": "ignored"}
    await _grant(db, payment, payment_id, engine)
    return {"status": "ok"}
