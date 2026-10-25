"""Outgoing email. Sending is best effort and must never break the caller."""

from __future__ import annotations

import logging
import uuid
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from getter_api.models import Consent, InterviewSession, User
from getter_api.settings import Settings

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


class Mailer(Protocol):
    async def send(self, to: str, subject: str, text: str) -> None: ...


class LogMailer:
    """Used when no API key is set: local runs, tests and e2e."""

    async def send(self, to: str, subject: str, text: str) -> None:
        log.info("email not sent (no GETTER_RESEND_API_KEY): to=%s subject=%s", to, subject)


class ResendMailer:
    def __init__(self, api_key: str, sender: str, client: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key
        self.sender = sender
        self.client = client

    async def send(self, to: str, subject: str, text: str) -> None:
        payload = {"from": self.sender, "to": [to], "subject": subject, "text": text}
        headers = {"authorization": f"Bearer {self.api_key}"}
        if self.client is not None:
            res = await self.client.post(RESEND_URL, json=payload, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(RESEND_URL, json=payload, headers=headers)
        res.raise_for_status()


def build_mailer(settings: Settings) -> Mailer:
    if settings.resend_api_key:
        return ResendMailer(settings.resend_api_key, settings.mail_from)
    return LogMailer()


def report_link(settings: Settings, session_id: uuid.UUID) -> str:
    return f"{settings.web_base_url.rstrip('/')}/report/?id={session_id}"


async def may_email(db: AsyncSession, user: User) -> bool:
    """False for deleted or unreachable accounts, or if any consent was withdrawn last."""
    if user.deleted_at is not None or user.email.endswith(".invalid"):
        return False
    rows = await db.scalars(
        select(Consent).where(Consent.user_id == user.id).order_by(Consent.created_at)
    )
    latest: dict[str, bool] = {}
    for row in rows:
        latest[row.kind] = row.granted
    return all(latest.values())


async def notify_report_ready(
    db: AsyncSession, mailer: Mailer, settings: Settings, session: InterviewSession
) -> None:
    """Tell the candidate their report is ready. Link only: no scores or quotes."""
    try:
        user = await db.get(User, session.user_id)
        if user is None or not await may_email(db, user):
            return
        link = report_link(settings, session.id)
        await mailer.send(
            user.email,
            "Your Getter practice report is ready",
            f"Your practice interview report is ready. Only you can see it:\n\n{link}\n",
        )
    except Exception:
        log.exception("report-ready email failed for session %s", session.id)
