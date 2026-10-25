"""The candidate's own data, as a download."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select

from getter_api.audit import audit
from getter_api.models import Consent, CreditEntry, InterviewSession, Payment
from getter_api.routes.sessions import DB, CurrentUser, Engine

router = APIRouter()


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


@router.get("/account/export")
async def export_account(db: DB, user: CurrentUser, engine: Engine) -> JSONResponse:
    """Everything stored about the signed-in candidate: profile, consents, interviews with
    transcripts and reports, payments and credits. Never includes other people's data or
    internal model-call records."""
    sessions = list(
        await db.scalars(
            select(InterviewSession)
            .where(InterviewSession.user_id == user.id)
            .order_by(InterviewSession.created_at)
        )
    )
    consents = list(
        await db.scalars(
            select(Consent).where(Consent.user_id == user.id).order_by(Consent.created_at)
        )
    )
    payments = list(
        await db.scalars(
            select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at)
        )
    )
    credits = list(
        await db.scalars(
            select(CreditEntry)
            .where(CreditEntry.user_id == user.id)
            .order_by(CreditEntry.created_at)
        )
    )
    data: dict[str, Any] = {
        "exported_at": engine.clock().isoformat(),
        "account": {"email": user.email, "name": user.name, "created_at": _iso(user.created_at)},
        "consents": [
            {
                "kind": c.kind,
                "text_version": c.text_version,
                "granted": c.granted,
                "created_at": _iso(c.created_at),
                "updated_at": _iso(c.updated_at),
            }
            for c in consents
        ],
        "interviews": [_session_data(engine, s) for s in sessions],
        "payments": [
            {
                "pack": p.pack_id,
                "interviews": p.credits,
                "amount_inr": p.amount_paise / 100,
                "status": p.status,
                "paid_at": _iso(p.paid_at),
            }
            for p in payments
        ],
        "credit_ledger": [
            {"change": c.delta, "reason": c.reason, "at": _iso(c.created_at)} for c in credits
        ],
    }
    audit(db, user, "account.export", "user", user.id)
    await db.commit()
    return JSONResponse(
        data, headers={"content-disposition": 'attachment; filename="getter-export.json"'}
    )


def _session_data(engine: Any, s: InterviewSession) -> dict[str, Any]:
    template = engine.content.templates.get(s.template_id)
    report = s.report
    return {
        "id": str(s.id),
        "role": template.title if template else s.template_id,
        "level": s.level,
        "status": s.status,
        "started_at": _iso(s.created_at),
        "ended_at": _iso(s.ended_at),
        "transcript": [
            {"speaker": t.speaker, "kind": t.kind, "text": t.text, "at": _iso(t.created_at)}
            for t in s.turns
        ],
        "report": None
        if report is None
        else {
            "verdict": report.verdict,
            "mean_score": report.mean_score,
            "summary": report.summary,
            "strengths": report.strengths.get("items", []),
            "skills": [
                {
                    "skill": k.skill_id,
                    "score": k.score,
                    "rationale": k.rationale,
                    "evidence": k.evidence.get("items", []),
                }
                for k in report.skill_scores
            ],
            "learning_plan": [
                {"skill": i.skill_id, "title": i.title, "detail": i.detail}
                for i in report.learning_items
            ],
        },
    }
