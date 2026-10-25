"""LiveKit access tokens: a JWT signed with the project's API secret.

Written against LiveKit's documented token format so the voice test needs no extra
dependency. The grant lets one participant join one room; nothing else.
"""

from __future__ import annotations

import time
import uuid

import jwt

from getter_api.settings import Settings

TOKEN_TTL_SECONDS = 15 * 60


class VoiceNotConfiguredError(Exception):
    """LiveKit keys are not set."""


def voice_enabled(settings: Settings) -> bool:
    return bool(settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret)


def mint_token(
    settings: Settings,
    *,
    identity: str,
    room: str,
    now: float | None = None,
    ttl_seconds: int = TOKEN_TTL_SECONDS,
) -> str:
    if not voice_enabled(settings):
        raise VoiceNotConfiguredError("LiveKit is not configured")
    issued = int(now if now is not None else time.time())
    claims = {
        "iss": settings.livekit_api_key,
        "sub": identity,
        "jti": uuid.uuid4().hex,
        "nbf": issued,
        "iat": issued,
        "exp": issued + ttl_seconds,
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
    }
    return jwt.encode(claims, settings.livekit_api_secret, algorithm="HS256")
