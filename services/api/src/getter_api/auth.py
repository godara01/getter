"""Who is calling. Dev mode only for now; real sign-in comes next.

In dev mode the caller names themselves in the X-Dev-User-Email header and a
candidate account is created on first use. Settings refuse dev mode in
staging and production, so this can't ship by accident.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from getter_api.db import get_db
from getter_api.models import User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_dev_user_email: Annotated[str | None, Header()] = None,
) -> User:
    email = (x_dev_user_email or "").strip().lower()
    if not email or len(email) > 320 or not EMAIL_RE.match(email):
        raise HTTPException(401, "sign in required")
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None:
        user = User(email=email, role="candidate")
        db.add(user)
        await db.commit()
    return user
