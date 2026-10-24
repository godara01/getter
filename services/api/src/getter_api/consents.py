"""Record explicit account terms acceptance once per active text version."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from getter_api.models import Consent, User


async def accept_signup_terms(db: AsyncSession, user: User, version: str, now: datetime) -> Consent:
    await db.scalar(select(User).where(User.id == user.id).with_for_update())
    consent = await db.scalar(
        select(Consent).where(
            Consent.user_id == user.id,
            Consent.kind == "signup_terms",
            Consent.text_version == version,
            Consent.granted.is_(True),
        )
    )
    if consent is None:
        consent = Consent(
            user_id=user.id,
            kind="signup_terms",
            text_version=version,
            granted=True,
            created_at=now,
            updated_at=now,
        )
        db.add(consent)
        await db.flush()
    return consent
