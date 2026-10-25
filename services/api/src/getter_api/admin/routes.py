"""Admin API. Every route needs an admin; reads of candidate content are audited."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import delete, select

from getter_api.audit import audit
from getter_api.db import utcnow
from getter_api.models import AuditLog, Consent, InterviewSession, User, Waitlist
from getter_api.routes.sessions import DB, CurrentUser
from getter_api.voice.livekit_token import VoiceNotConfiguredError, mint_token, voice_enabled
from getter_api.worker import dispatch_grading

REGRADABLE = ("completed", "failed", "grading")


def is_admin(request: Request, user: User) -> bool:
    settings = request.app.state.settings
    if user.role == "admin":
        return True
    if settings.auth_mode == "clerk":
        return (
            user.clerk_user_id is not None and user.clerk_user_id in settings.admin_clerk_user_ids
        )
    return user.email in [e.strip().lower() for e in settings.admin_emails]


async def require_admin(request: Request, user: CurrentUser) -> User:
    if not is_admin(request, user):
        raise HTTPException(403, "admin access required")
    return user


Admin = Annotated[User, Depends(require_admin)]
router = APIRouter(prefix="/admin", tags=["admin"])


class AdminSessionRow(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    template_id: str
    level: str
    status: str
    created_at: datetime
    ended_at: datetime | None
    ai_cost_inr: float
    input_tokens: int
    output_tokens: int
    error: str | None
    verdict: str | None
    needs_review: bool | None


class AdminTurn(BaseModel):
    index: int
    speaker: str
    kind: str
    text: str


class AdminScore(BaseModel):
    skill_id: str
    score: int | None
    rationale: str
    evidence: list[dict[str, Any]]


class AdminSessionDetail(AdminSessionRow):
    turns: list[AdminTurn]
    summary: str | None
    mean_score: float | None
    scores: list[AdminScore]


class RegradeOut(BaseModel):
    session_id: uuid.UUID
    status: str


class DeletionOut(BaseModel):
    user_id: uuid.UUID
    already_deleted: bool
    sessions_deleted: int
    consents_deleted: int
    waitlist_deleted: int


class AuditRow(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: str
    details: dict[str, Any]


def row_out(s: InterviewSession) -> dict[str, Any]:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "template_id": s.template_id,
        "level": s.level,
        "status": s.status,
        "created_at": s.created_at,
        "ended_at": s.ended_at,
        "ai_cost_inr": s.ai_cost_inr,
        "input_tokens": s.input_tokens,
        "output_tokens": s.output_tokens,
        "error": s.error,
        "verdict": s.report.verdict if s.report else None,
        "needs_review": s.report.needs_review if s.report else None,
    }


@router.get("/sessions", response_model=list[AdminSessionRow])
async def list_sessions(
    db: DB,
    admin: Admin,
    status: str | None = None,
    user_id: uuid.UUID | None = None,
    template_id: str | None = None,
    min_cost_inr: Annotated[float | None, Query(ge=0)] = None,
    max_cost_inr: Annotated[float | None, Query(ge=0)] = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdminSessionRow]:
    """Metadata only: no transcript or scores. Ids, never emails, identify people."""
    query = select(InterviewSession)
    if status:
        query = query.where(InterviewSession.status == status)
    if user_id:
        query = query.where(InterviewSession.user_id == user_id)
    if template_id:
        query = query.where(InterviewSession.template_id == template_id)
    if min_cost_inr is not None:
        query = query.where(InterviewSession.ai_cost_inr >= min_cost_inr)
    if max_cost_inr is not None:
        query = query.where(InterviewSession.ai_cost_inr <= max_cost_inr)
    if created_after:
        query = query.where(InterviewSession.created_at >= created_after)
    if created_before:
        query = query.where(InterviewSession.created_at < created_before)
    rows = await db.scalars(
        query.order_by(InterviewSession.created_at.desc()).limit(limit).offset(offset)
    )
    return [AdminSessionRow(**row_out(s)) for s in rows]


@router.get("/sessions/{session_id}", response_model=AdminSessionDetail)
async def get_session(session_id: uuid.UUID, db: DB, admin: Admin) -> AdminSessionDetail:
    session = await db.get(InterviewSession, session_id)
    if session is None:
        raise HTTPException(404, "session not found")
    report = session.report
    audit(db, admin, "admin.session.view", "session", session.id)
    await db.commit()
    return AdminSessionDetail(
        **row_out(session),
        turns=[
            AdminTurn(index=t.index, speaker=t.speaker, kind=t.kind, text=t.text)
            for t in session.turns
        ],
        summary=report.summary if report else None,
        mean_score=report.mean_score if report else None,
        scores=[
            AdminScore(
                skill_id=s.skill_id,
                score=s.score,
                rationale=s.rationale,
                evidence=list(s.evidence.get("items", [])),
            )
            for s in (report.skill_scores if report else [])
        ],
    )


@router.post("/sessions/{session_id}/regrade", response_model=RegradeOut, status_code=202)
async def regrade_session(
    session_id: uuid.UUID,
    request: Request,
    background: BackgroundTasks,
    db: DB,
    admin: Admin,
) -> RegradeOut:
    """Grade again through the normal queue. The usual grading checks apply.

    Safe to repeat: a session already waiting for grading is only re-queued, and
    the queue's unique job id and the worker's status check prevent a second report.
    """
    session = await db.scalar(
        select(InterviewSession).where(InterviewSession.id == session_id).with_for_update()
    )
    if session is None:
        raise HTTPException(404, "session not found")
    if session.status not in REGRADABLE:
        raise HTTPException(409, f"cannot re-grade a session that is {session.status}")
    previous = session.status
    if session.report is not None:
        # The old score is replaced only by a new fully validated one, or by none.
        await db.delete(session.report)
        await db.flush()
        session.report = None
    session.status = "grading"
    session.error = None
    audit(db, admin, "admin.session.regrade", "session", session.id, {"previous": previous})
    await db.commit()
    await dispatch_grading(request, background, session.id)
    return RegradeOut(session_id=session.id, status="grading")


@router.post("/users/{user_id}/deletion", response_model=DeletionOut)
async def process_deletion(user_id: uuid.UUID, db: DB, admin: Admin) -> DeletionOut:
    """Erase a user's practice data and leave a tombstone with no personal data.

    Repeating it is harmless. Model-call cost rows stay, keyed by the anonymous id.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    if user.id == admin.id:
        raise HTTPException(409, "admins cannot delete their own account")
    if user.deleted_at is not None:
        return DeletionOut(
            user_id=user.id,
            already_deleted=True,
            sessions_deleted=0,
            consents_deleted=0,
            waitlist_deleted=0,
        )
    sessions = list(
        await db.scalars(select(InterviewSession).where(InterviewSession.user_id == user.id))
    )
    for session in sessions:
        await db.delete(session)  # turns, report, scores and learning items cascade
    consents = await db.execute(delete(Consent).where(Consent.user_id == user.id))
    waitlist = await db.execute(delete(Waitlist).where(Waitlist.email == user.email))
    counts = {
        "sessions": len(sessions),
        "consents": int(consents.rowcount or 0),  # type: ignore[attr-defined]
        "waitlist": int(waitlist.rowcount or 0),  # type: ignore[attr-defined]
    }
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.name = None
    user.clerk_user_id = None
    user.auth_subject = None
    user.role = "candidate"
    user.deleted_at = utcnow()
    audit(db, admin, "admin.user.deletion", "user", user.id, counts)
    await db.commit()
    return DeletionOut(
        user_id=user.id,
        already_deleted=False,
        sessions_deleted=counts["sessions"],
        consents_deleted=counts["consents"],
        waitlist_deleted=counts["waitlist"],
    )


class VoiceTokenIn(BaseModel):
    room: str = "voice-test"


class VoiceTokenOut(BaseModel):
    url: str
    room: str
    identity: str
    token: str


@router.post("/voice/token", response_model=VoiceTokenOut)
async def voice_token(body: VoiceTokenIn, request: Request, admin: Admin) -> VoiceTokenOut:
    """A short-lived LiveKit token for the phase 0 voice test (see docs/voice-test.md)."""
    settings = request.app.state.settings
    if not voice_enabled(settings):
        raise HTTPException(503, "LiveKit is not set up yet")
    room = "".join(c for c in body.room if c.isalnum() or c in "-_")[:64] or "voice-test"
    identity = f"admin-{admin.id.hex[:12]}"
    try:
        token = mint_token(settings, identity=identity, room=room)
    except VoiceNotConfiguredError as exc:  # raced with a config change
        raise HTTPException(503, "LiveKit is not set up yet") from exc
    return VoiceTokenOut(url=settings.livekit_url, room=room, identity=identity, token=token)


@router.get("/audit", response_model=list[AuditRow])
async def list_audit(
    db: DB,
    admin: Admin,
    action: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditRow]:
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if actor_user_id:
        query = query.where(AuditLog.actor_user_id == actor_user_id)
    if target_type:
        query = query.where(AuditLog.target_type == target_type)
    if target_id:
        query = query.where(AuditLog.target_id == target_id)
    rows = await db.scalars(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id).limit(limit).offset(offset)
    )
    return [AuditRow.model_validate(r, from_attributes=True) for r in rows]
