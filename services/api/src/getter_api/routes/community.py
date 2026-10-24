"""Public waitlist and private consent records. No email is sent."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError

from getter_api.auth import EMAIL_RE
from getter_api.consents import accept_signup_terms as record_signup_terms
from getter_api.models import Consent, Waitlist, WaitlistAttempt
from getter_api.routes.sessions import DB, CurrentUser, Engine

router = APIRouter()


class WaitlistIn(BaseModel):
    email: str = Field(max_length=320)
    role_interest: Literal["backend", "devops_sre", "other"]

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL_RE.fullmatch(email):
            raise ValueError("enter a valid email")
        return email


class TermsIn(BaseModel):
    accept_terms: bool
    text_version: str


class ConsentOut(BaseModel):
    id: uuid.UUID
    kind: str
    text_version: str
    granted: bool
    created_at: datetime
    updated_at: datetime


def consent_out(consent: Consent) -> ConsentOut:
    return ConsentOut.model_validate(consent, from_attributes=True)


@router.post("/waitlist", status_code=202)
async def join_waitlist(
    body: WaitlistIn, request: Request, db: DB, engine: Engine
) -> dict[str, str]:
    now = engine.clock()
    # Use the direct peer. Only the trusted reverse proxy may supply real IPs
    # through uvicorn's explicitly configured forwarded-allow-ips setting.
    ip = request.client.host if request.client else "unknown"
    digest = hashlib.sha256(ip.encode()).hexdigest()
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {
                "key": int(digest[:15], 16),
            },
        )
    await db.execute(
        delete(WaitlistAttempt).where(WaitlistAttempt.created_at <= now - timedelta(hours=1))
    )
    db.add(WaitlistAttempt(ip_hash=digest, created_at=now))
    await db.flush()
    attempts = await db.scalar(
        select(func.count())
        .select_from(WaitlistAttempt)
        .where(
            WaitlistAttempt.ip_hash == digest,
            WaitlistAttempt.created_at > now - timedelta(hours=1),
        )
    )
    await db.commit()
    if (attempts or 0) > engine.settings.waitlist_requests_per_hour:
        raise HTTPException(
            429, "please try the waitlist again in an hour", headers={"Retry-After": "3600"}
        )
    if await db.scalar(select(Waitlist.id).where(Waitlist.email == body.email)) is None:
        db.add(Waitlist(email=body.email, role_interest=body.role_interest, created_at=now))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()  # A concurrent signup already stored this email.
    # The same response for a new address and a duplicate, to avoid probing.
    return {"message": "You're on the waitlist. No email has been sent."}


@router.post("/account/terms", response_model=ConsentOut)
async def accept_signup_terms(
    body: TermsIn, db: DB, user: CurrentUser, engine: Engine
) -> ConsentOut:
    if not body.accept_terms or body.text_version != engine.settings.terms_version:
        raise HTTPException(422, "accept the current terms before signing up")
    consent = await record_signup_terms(db, user, body.text_version, engine.clock())
    await db.commit()
    return consent_out(consent)


@router.get("/consents", response_model=list[ConsentOut])
async def list_consents(db: DB, user: CurrentUser) -> list[ConsentOut]:
    rows = await db.scalars(
        select(Consent).where(Consent.user_id == user.id).order_by(Consent.created_at)
    )
    return [consent_out(row) for row in rows]


@router.delete("/consents/{consent_id}", status_code=204)
async def withdraw_consent(
    consent_id: uuid.UUID, db: DB, user: CurrentUser, engine: Engine
) -> Response:
    row = await db.get(Consent, consent_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "consent not found")
    if row.granted:
        row.granted = False
        row.updated_at = engine.clock()
        await db.commit()
    return Response(status_code=204)
