"""Admission limits only: a running practice interview is never interrupted."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from getter_api.db import as_utc
from getter_api.models import InterviewSession, LLMCall, User
from getter_api.settings import Settings

log = logging.getLogger(__name__)


def pause(until: datetime, reason: str, now: datetime) -> None:
    raise HTTPException(
        429,
        f"{reason}; you can start again after {until.isoformat()}",
        headers={"Retry-After": str(max(1, int((until - now).total_seconds())))},
    )


async def check_free_limits(
    db: AsyncSession, user: User, settings: Settings, now: datetime
) -> None:
    day = timedelta(days=1)
    # Serializes admissions for the same account on Postgres.
    await db.scalar(select(User).where(User.id == user.id).with_for_update())
    starts = list(
        await db.scalars(
            select(InterviewSession.created_at)
            .where(
                InterviewSession.user_id == user.id,
                InterviewSession.created_at > now - day,
            )
            .order_by(InterviewSession.created_at)
        )
    )
    if len(starts) >= settings.free_sessions_per_day:
        pause(
            as_utc(starts[-settings.free_sessions_per_day]) + day,
            f"free practice is limited to {settings.free_sessions_per_day} interviews a day",
            now,
        )

    window = timedelta(hours=settings.free_cost_window_hours)
    rows = (
        await db.execute(
            select(LLMCall.created_at, LLMCall.cost_inr)
            .where(
                LLMCall.user_id == user.id,
                LLMCall.created_at > now - window,
                LLMCall.created_at <= now,
            )
            .order_by(LLMCall.created_at)
        )
    ).all()
    spend = sum((Decimal(str(row.cost_inr)) for row in rows), Decimal(0))
    cap = Decimal(str(settings.free_account_cost_inr))
    if spend >= cap:
        for row in rows:
            spend -= Decimal(str(row.cost_inr))
            if spend < cap:
                pause(
                    as_utc(row.created_at) + window,
                    "your free practice cost allowance is used",
                    now,
                )

    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    calls = list(
        await db.scalars(
            select(LLMCall).where(
                LLMCall.created_at > now - day,
                LLMCall.created_at <= now,
            )
        )
    )
    daily = sum(
        (Decimal(str(c.cost_inr)) for c in calls if as_utc(c.created_at) >= midnight), Decimal(0)
    )
    sessions = {c.session_id for c in calls if c.session_id is not None}
    measured = sum(c.cost_inr for c in calls if c.session_id is not None)
    if sessions and measured / len(sessions) > settings.session_cost_warning_inr:
        log.warning(
            "Average practice cost over the last day is INR %.2f per session",
            measured / len(sessions),
        )
    if daily >= Decimal(str(settings.global_daily_cost_inr)):
        pause(midnight + day, "free practice is paused because today's budget is used", now)
