from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from getter_api.audit import audit
from getter_api.auth import current_user
from getter_api.code_runner import CodeRunner, format_result
from getter_api.consents import accept_signup_terms
from getter_api.cost_controls import check_free_limits
from getter_api.db import get_db
from getter_api.interview.engine import InterviewEngine, InterviewError, RunLimitError
from getter_api.models import Consent, FeedbackReport, InterviewSession, ReportRating, User
from getter_api.schemas import (
    AnswerIn,
    CodingOut,
    EvidenceOut,
    LearningItemOut,
    Progress,
    RatingIn,
    RatingOut,
    ReportOut,
    ReportPending,
    RunIn,
    RunOut,
    RunResponse,
    SectionSummary,
    SessionCreate,
    SessionListItem,
    SessionOut,
    SkillScoreOut,
    TemplateOut,
    TestResultOut,
    TurnOut,
)
from getter_api.worker import dispatch_grading

router = APIRouter()

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


def engine_of(request: Request) -> InterviewEngine:
    engine: InterviewEngine = request.app.state.engine
    return engine


Engine = Annotated[InterviewEngine, Depends(engine_of)]


def runner_of(request: Request) -> CodeRunner:
    runner: CodeRunner = request.app.state.runner
    return runner


Runner = Annotated[CodeRunner, Depends(runner_of)]


def session_out(engine: InterviewEngine, s: InterviewSession) -> SessionOut:
    template = engine.template(s.template_id)
    progress = None
    coding = None
    if s.status == "in_progress":
        task = engine.position(s).question.coding
        if task is not None:
            coding = CodingOut(
                language=task.language,
                starter_code=task.starter_code,
                test_names=[t.name for t in task.tests],
                runner_enabled=engine.settings.code_runner != "disabled",
                max_runs=engine.settings.code_max_runs,
                runs_used=engine.run_count(s),
            )
        progress = Progress(
            section_number=s.section_index + 1,
            section_count=len(template.sections),
            section_title=template.sections[s.section_index].title,
            section_seconds_left=engine.section_seconds_left(s),
        )
    return SessionOut(
        id=s.id,
        template_id=s.template_id,
        title=template.title,
        level=s.level,
        status=s.status,
        created_at=s.created_at,
        ended_at=s.ended_at,
        progress=progress,
        coding=coding,
        turns=[
            TurnOut(
                index=t.index,
                speaker=t.speaker,
                kind=t.kind,
                section_id=t.section_id,
                text=t.text,
                created_at=t.created_at,
            )
            for t in s.turns
        ],
    )


async def owned_session(
    db: AsyncSession, user: User, session_id: uuid.UUID, *, for_update: bool = False
) -> InterviewSession:
    query = select(InterviewSession).where(InterviewSession.id == session_id)
    if for_update:
        query = query.with_for_update()
    session = await db.scalar(query)
    # Same answer for "missing" and "not yours", so ids can't be probed.
    if session is None or session.user_id != user.id:
        raise HTTPException(404, "session not found")
    return session


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(engine: Engine) -> list[TemplateOut]:
    out = []
    for t in engine.content.templates.values():
        rubric = engine.content.rubric_for(t)
        out.append(
            TemplateOut(
                id=t.id,
                title=t.title,
                role_title=rubric.title,
                levels=list(t.levels),
                minutes=sum(s.time_limit_minutes for s in t.sections),
                sections=[
                    SectionSummary(id=s.id, title=s.title, minutes=s.time_limit_minutes)
                    for s in t.sections
                ],
                skills=[s.name for s in rubric.skills],
            )
        )
    return out


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionCreate, db: DB, user: CurrentUser, engine: Engine
) -> SessionOut:
    if not body.accept_terms:
        raise HTTPException(422, "you need to accept the practice terms to start")
    await check_free_limits(db, user, engine.settings, engine.clock())
    try:
        session = engine.start(user, body.template_id, body.level)
    except InterviewError as exc:
        raise HTTPException(422, str(exc)) from exc
    await accept_signup_terms(db, user, engine.settings.terms_version, engine.clock())
    db.add(
        Consent(
            user_id=user.id,
            kind="practice_terms",
            text_version=engine.settings.terms_version,
            granted=True,
        )
    )
    db.add(session)
    await db.commit()
    return session_out(engine, session)


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(db: DB, user: CurrentUser, engine: Engine) -> list[SessionListItem]:
    result = await db.scalars(
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.created_at.desc())
        .limit(100)
    )
    rows = list(result)
    for session in rows:
        if session.report is not None:
            audit(db, user, "score.view", "session", session.id)
    await db.commit()
    return [
        SessionListItem(
            id=s.id,
            title=engine.template(s.template_id).title,
            level=s.level,
            status=s.status,
            created_at=s.created_at,
            verdict=s.report.verdict if s.report else None,
            mean_score=s.report.mean_score if s.report else None,
        )
        for s in rows
    ]


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: uuid.UUID, db: DB, user: CurrentUser, engine: Engine
) -> SessionOut:
    return session_out(engine, await owned_session(db, user, session_id))


@router.post("/sessions/{session_id}/answers", response_model=SessionOut)
async def post_answer(
    session_id: uuid.UUID,
    body: AnswerIn,
    request: Request,
    background: BackgroundTasks,
    db: DB,
    user: CurrentUser,
    engine: Engine,
) -> SessionOut:
    session = await owned_session(db, user, session_id, for_update=True)
    try:
        await engine.answer(db, session, body.text)
    except InterviewError as exc:
        raise HTTPException(409 if "not in progress" in str(exc) else 422, str(exc)) from exc
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "another answer was saved at the same time; reload") from exc
    if session.status == "grading":
        await dispatch_grading(request, background, session.id)
    return session_out(engine, session)


@router.post("/sessions/{session_id}/runs", response_model=RunResponse)
async def run_code(
    session_id: uuid.UUID,
    body: RunIn,
    db: DB,
    user: CurrentUser,
    engine: Engine,
    runner: Runner,
) -> RunResponse:
    """Run code for the current coding question and save snapshot and result as turns.

    The session row stays locked while the code runs, so runs never overlap.
    """
    session = await owned_session(db, user, session_id, for_update=True)
    try:
        task = engine.check_run_allowed(session, body.code)
    except RunLimitError as exc:
        raise HTTPException(429, str(exc)) from exc
    except InterviewError as exc:
        raise HTTPException(409 if "not in progress" in str(exc) else 422, str(exc)) from exc
    result = await runner.run(task, body.code)
    # With no runner nothing ran, so nothing is recorded and no run is used.
    if result.status not in ("not_configured", "unavailable"):
        engine.add_run_turns(
            session,
            body.code,
            format_result(result, engine.run_count(session) + 1, engine.settings.code_max_runs),
        )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "another change was saved at the same time; reload") from exc
    return RunResponse(
        result=RunOut(
            status=result.status,
            message=result.message,
            tests=[
                TestResultOut(name=t.name, passed=t.passed, detail=t.detail) for t in result.tests
            ],
            stdout=result.stdout[:2000],
            stderr=result.stderr[-2000:],
            duration_ms=result.duration_ms,
        ),
        session=session_out(engine, session),
    )


@router.post("/sessions/{session_id}/end", response_model=SessionOut)
async def end_session(
    session_id: uuid.UUID,
    request: Request,
    background: BackgroundTasks,
    db: DB,
    user: CurrentUser,
    engine: Engine,
) -> SessionOut:
    session = await owned_session(db, user, session_id, for_update=True)
    try:
        engine.end_early(session)
    except InterviewError as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    if session.status == "grading":
        await dispatch_grading(request, background, session.id)
    return session_out(engine, session)


@router.get(
    "/sessions/{session_id}/report",
    response_model=ReportOut,
    responses={202: {"model": ReportPending}},
)
async def get_report(
    session_id: uuid.UUID, db: DB, user: CurrentUser, engine: Engine
) -> ReportOut | JSONResponse:
    session = await owned_session(db, user, session_id)
    if session.status in ("in_progress", "grading"):
        return JSONResponse(ReportPending(status=session.status).model_dump(), status_code=202)
    if session.report is None:
        # failed or abandoned: never show a score for a broken interview.
        raise HTTPException(409, f"no report: the interview is {session.status}")

    audit(db, user, "report.view", "session", session.id)
    await db.commit()
    template = engine.template(session.template_id)
    rubric = engine.content.rubric_for(template)
    r = session.report
    names = {s.id: s.name for s in rubric.skills}
    return ReportOut(
        session_id=session.id,
        title=template.title,
        level=session.level,
        target_score=rubric.level_bars[session.level],  # type: ignore[index]
        scale=rubric.scale,
        verdict=r.verdict,
        mean_score=r.mean_score,
        summary=r.summary,
        strengths=list(r.strengths.get("items", [])),
        skills=[
            SkillScoreOut(
                skill_id=s.skill_id,
                name=names.get(s.skill_id, s.skill_id),
                score=s.score,
                level_description=(
                    rubric.skill(s.skill_id).levels.get(s.score)
                    if s.score is not None and s.skill_id in names
                    else None
                ),
                evidence=[EvidenceOut(**e) for e in s.evidence.get("items", [])],
                rationale=s.rationale,
            )
            for s in r.skill_scores
        ],
        learning_plan=[
            LearningItemOut(
                skill_id=li.skill_id,
                title=li.title,
                detail=li.detail,
                practice=list(li.practice.get("items", [])),
            )
            for li in r.learning_items
        ],
        needs_review=r.needs_review,
        graded_by=r.grader_model,
        checked_by=r.check_model,
        rubric=f"{session.rubric_id}@{session.rubric_version}",
        created_at=r.created_at,
    )


async def reported_session(db: AsyncSession, user: User, session_id: uuid.UUID) -> FeedbackReport:
    session = await owned_session(db, user, session_id)
    if session.report is None:
        raise HTTPException(409, "there is no report to rate")
    return session.report


@router.get("/sessions/{session_id}/report/rating", response_model=RatingOut | None)
async def get_rating(session_id: uuid.UUID, db: DB, user: CurrentUser) -> RatingOut | None:
    report = await reported_session(db, user, session_id)
    row = await db.scalar(select(ReportRating).where(ReportRating.report_id == report.id))
    return RatingOut(rating=row.rating, comment=row.comment) if row else None


@router.put("/sessions/{session_id}/report/rating", response_model=RatingOut)
async def put_rating(
    session_id: uuid.UUID, body: RatingIn, db: DB, user: CurrentUser, engine: Engine
) -> RatingOut:
    """One rating per report; sending it again replaces the earlier one."""
    report = await reported_session(db, user, session_id)
    comment = (body.comment or "").strip() or None
    row = await db.scalar(select(ReportRating).where(ReportRating.report_id == report.id))
    if row is None:
        db.add(
            ReportRating(
                report_id=report.id, rating=body.rating, comment=comment, created_at=engine.clock()
            )
        )
    else:
        row.rating = body.rating
        row.comment = comment
        row.updated_at = engine.clock()
    try:
        await db.commit()
    except IntegrityError:
        # A concurrent first rating won the race; apply ours on top of it.
        await db.rollback()
        row = await db.scalar(select(ReportRating).where(ReportRating.report_id == report.id))
        if row is None:
            raise
        row.rating = body.rating
        row.comment = comment
        row.updated_at = engine.clock()
        await db.commit()
    return RatingOut(rating=body.rating, comment=comment)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: uuid.UUID, db: DB, user: CurrentUser) -> Response:
    """Candidates can erase any of their sessions, transcript and report included."""
    session = await owned_session(db, user, session_id)
    await db.delete(session)
    audit(db, user, "session.delete", "session", session_id)
    await db.commit()
    return Response(status_code=204)
