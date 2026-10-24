from __future__ import annotations

import re
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from getter_api.db import get_db
from getter_api.models import User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@lru_cache(maxsize=8)
def jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_jwk_set=True, lifespan=300, timeout=5)


def verify_token(token: str, issuer: str, url: str, parties: list[str]) -> str:
    try:
        key = jwks_client(url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["exp", "iss", "sub", "azp"], "verify_aud": False},
        )
        subject = claims["sub"]
        if claims["azp"] not in parties or not isinstance(subject, str) or not subject:
            raise jwt.InvalidTokenError("invalid subject or authorized party")
        if len(subject) > 200:
            raise jwt.InvalidTokenError("invalid subject")
        return subject
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "invalid sign-in token") from exc


async def current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user_email: Annotated[str | None, Header()] = None,
) -> User:
    settings = request.app.state.settings
    if settings.auth_mode == "clerk":
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "sign in required")
        subject = await run_in_threadpool(
            verify_token,
            token,
            settings.clerk_issuer,
            settings.clerk_jwks_url,
            settings.clerk_authorized_parties,
        )
        user = await db.scalar(select(User).where(User.clerk_user_id == subject))
        if user is not None and user.deleted_at is not None:
            raise HTTPException(401, "account deleted")
        if user is None:
            # Default Clerk session tokens do not carry email. Never link by an
            # unverified email claim; identity belongs to the verified subject.
            user = User(clerk_user_id=subject, email=f"{subject}@clerk.invalid", role="candidate")
            db.add(user)
            await db.commit()
        return user
    email = (x_dev_user_email or "").strip().lower()
    if not email or len(email) > 320 or not EMAIL_RE.match(email):
        raise HTTPException(401, "sign in required")
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None:
        user = User(email=email, role="candidate")
        db.add(user)
        await db.commit()
    return user
