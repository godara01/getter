"""Database tables. Change only through Alembic migrations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from getter_api.db import utcnow

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True), dict[str, Any]: JSONType}


class TimestampMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    clerk_user_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str | None] = mapped_column(String(200))
    # candidate, company_member, reviewer, admin
    role: Mapped[str] = mapped_column(String(32), default="candidate")
    # Subject id from the auth provider, once real sign-in is wired up.
    auth_subject: Mapped[str | None] = mapped_column(String(200), unique=True)
    deleted_at: Mapped[datetime | None]


class Consent(TimestampMixin, Base):
    __tablename__ = "consents"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(64))
    text_version: Mapped[str] = mapped_column(String(64))
    granted: Mapped[bool]


class InterviewSession(TimestampMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    template_id: Mapped[str] = mapped_column(String(100))
    template_version: Mapped[int]
    rubric_id: Mapped[str] = mapped_column(String(100))
    rubric_version: Mapped[int]
    prompt_version: Mapped[str] = mapped_column(String(32))
    level: Mapped[str] = mapped_column(String(16))
    # practice now; certified arrives with the secure app.
    kind: Mapped[str] = mapped_column(String(16), default="practice")
    # in_progress, grading, completed, failed, abandoned
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    section_index: Mapped[int] = mapped_column(default=0)
    question_index: Mapped[int] = mapped_column(default=0)
    followups_used: Mapped[int] = mapped_column(default=0)
    section_started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ended_at: Mapped[datetime | None]
    ai_cost_inr: Mapped[float] = mapped_column(default=0.0)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)

    turns: Mapped[list[SessionTurn]] = relationship(
        back_populates="session",
        order_by="SessionTurn.index",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    report: Mapped[FeedbackReport | None] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class SessionTurn(TimestampMixin, Base):
    __tablename__ = "session_turns"
    __table_args__ = (UniqueConstraint("session_id", "index"),)

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    index: Mapped[int]
    speaker: Mapped[str] = mapped_column(String(16))  # interviewer or candidate
    # intro, question, follow_up, answer, closing
    kind: Mapped[str] = mapped_column(String(16))
    section_id: Mapped[str | None] = mapped_column(String(100))
    question_id: Mapped[str | None] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)

    session: Mapped[InterviewSession] = relationship(back_populates="turns")


class FeedbackReport(TimestampMixin, Base):
    __tablename__ = "feedback_reports"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), unique=True
    )
    summary: Mapped[str] = mapped_column(Text)
    strengths: Mapped[dict[str, Any]]  # {"items": [...]}
    # below, meets, above, insufficient_evidence
    verdict: Mapped[str] = mapped_column(String(32))
    mean_score: Mapped[float | None]
    needs_review: Mapped[bool] = mapped_column(default=False)
    review_reason: Mapped[str | None] = mapped_column(Text)
    grader_model: Mapped[str] = mapped_column(String(200))
    check_model: Mapped[str | None] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(32))

    session: Mapped[InterviewSession] = relationship(back_populates="report")
    skill_scores: Mapped[list[SkillScore]] = relationship(
        back_populates="report", cascade="all, delete-orphan", lazy="selectin"
    )
    learning_items: Mapped[list[LearningItem]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="LearningItem.position",
        lazy="selectin",
    )


class SkillScore(TimestampMixin, Base):
    __tablename__ = "skill_scores"

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feedback_reports.id", ondelete="CASCADE")
    )
    skill_id: Mapped[str] = mapped_column(String(100))
    score: Mapped[int | None]
    evidence: Mapped[dict[str, Any]]  # {"items": [{"turn": n, "quote": "..."}]}
    rationale: Mapped[str] = mapped_column(Text)
    rubric_id: Mapped[str] = mapped_column(String(100))
    rubric_version: Mapped[int]
    grader_model: Mapped[str] = mapped_column(String(200))

    report: Mapped[FeedbackReport] = relationship(back_populates="skill_scores")


class LearningItem(TimestampMixin, Base):
    __tablename__ = "learning_items"

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feedback_reports.id", ondelete="CASCADE")
    )
    position: Mapped[int]
    skill_id: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text)
    practice: Mapped[dict[str, Any]]  # {"items": [...]}

    report: Mapped[FeedbackReport] = relationship(back_populates="learning_items")


class LLMCall(TimestampMixin, Base):
    """One billable model call, for cost tracking and model comparison."""

    __tablename__ = "llm_calls"

    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), index=True
    )
    task: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(200))
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    cost_inr: Mapped[float]
    latency_ms: Mapped[int]
    ok: Mapped[bool]


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_log"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Waitlist(TimestampMixin, Base):
    __tablename__ = "waitlist"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    role_interest: Mapped[str] = mapped_column(String(32))


class WaitlistAttempt(TimestampMixin, Base):
    __tablename__ = "waitlist_attempts"

    ip_hash: Mapped[str] = mapped_column(String(64), index=True)
