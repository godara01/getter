"""Small, shared audit writer; commits belong to the route transaction."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from getter_api.models import AuditLog, User


def audit(
    db: AsyncSession, user: User, action: str, target_type: str, target_id: uuid.UUID
) -> None:
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            details={},
        )
    )
