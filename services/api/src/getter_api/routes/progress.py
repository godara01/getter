from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from getter_api.audit import audit
from getter_api.auth import current_user
from getter_api.db import get_db
from getter_api.interview.engine import InterviewEngine
from getter_api.models import InterviewSession, User
from getter_api.schemas import ProgressOut, ProgressPoint, RecurringGap, RoleProgress, SkillProgress

router = APIRouter()

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]

MAX_GAPS = 5


def engine_of(request: Request) -> InterviewEngine:
    engine: InterviewEngine = request.app.state.engine
    return engine


Engine = Annotated[InterviewEngine, Depends(engine_of)]


@router.get("/progress", response_model=ProgressOut)
async def get_progress(db: DB, user: CurrentUser, engine: Engine) -> ProgressOut:
    """The candidate's own score history. Only completed, graded sessions count: a failed
    or abandoned interview has no report, so it can never add a score."""
    result = await db.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id, InterviewSession.status == "completed")
        .order_by(InterviewSession.created_at, InterviewSession.id)
    )
    groups: dict[tuple[str, str], list[InterviewSession]] = {}
    for s in result:
        if s.report is not None:
            groups.setdefault((s.template_id, s.level), []).append(s)

    roles = []
    for (template_id, level), sessions in groups.items():
        template = engine.content.templates.get(template_id)
        rubric = engine.content.rubric_for(template) if template else None
        names = {k.id: k.name for k in rubric.skills} if rubric else {}
        points: dict[str, list[ProgressPoint]] = {}
        gap_titles: dict[str, str] = {}
        gap_sessions: dict[str, int] = {}
        for s in sessions:
            assert s.report is not None
            for score in s.report.skill_scores:
                if score.score is not None:
                    points.setdefault(score.skill_id, []).append(
                        ProgressPoint(session_id=s.id, date=s.created_at, score=score.score)
                    )
            for skill_id in {li.skill_id for li in s.report.learning_items}:
                gap_sessions[skill_id] = gap_sessions.get(skill_id, 0) + 1
            for li in s.report.learning_items:
                gap_titles[li.skill_id] = li.title  # sessions are oldest first: keep the latest
        order = list(names)
        skills = [
            SkillProgress(
                skill_id=skill_id,
                name=names.get(skill_id, skill_id),
                points=pts,
                latest=pts[-1].score,
                previous=pts[-2].score if len(pts) > 1 else None,
                delta=pts[-1].score - pts[-2].score if len(pts) > 1 else None,
            )
            for skill_id, pts in sorted(
                points.items(),
                key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order),
            )
        ]
        ranked = sorted(gap_sessions.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_GAPS]
        gaps = [
            RecurringGap(
                skill_id=skill_id,
                name=names.get(skill_id, skill_id),
                title=gap_titles[skill_id],
                sessions=n,
            )
            for skill_id, n in ranked
        ]
        roles.append(
            RoleProgress(
                template_id=template_id,
                title=template.title if template else template_id,
                level=level,
                sessions=len(sessions),
                skills=skills,
                gaps=gaps,
            )
        )
    roles.sort(key=lambda r: (r.title, r.level))
    audit(db, user, "progress.view", "user", user.id)
    await db.commit()
    return ProgressOut(roles=roles)
