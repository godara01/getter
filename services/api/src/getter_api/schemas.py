"""Request and response bodies of the public API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SectionSummary(BaseModel):
    id: str
    title: str
    minutes: float


class TemplateOut(BaseModel):
    id: str
    title: str
    role_title: str
    levels: list[str]
    minutes: float
    sections: list[SectionSummary]
    skills: list[str]


class SessionCreate(BaseModel):
    template_id: str
    level: Literal["junior", "mid"]
    accept_terms: bool = Field(
        description="Candidate accepts the practice terms, including storing the transcript."
    )


class AnswerIn(BaseModel):
    text: str = Field(min_length=1)


class TurnOut(BaseModel):
    index: int
    speaker: str
    kind: str
    section_id: str | None
    text: str
    created_at: datetime


class Progress(BaseModel):
    section_number: int
    section_count: int
    section_title: str
    section_seconds_left: int | None


class SessionOut(BaseModel):
    id: uuid.UUID
    template_id: str
    title: str
    level: str
    status: str
    created_at: datetime
    ended_at: datetime | None
    progress: Progress | None
    turns: list[TurnOut]


class SessionListItem(BaseModel):
    id: uuid.UUID
    title: str
    level: str
    status: str
    created_at: datetime
    verdict: str | None
    mean_score: float | None


class EvidenceOut(BaseModel):
    turn: int
    quote: str


class SkillScoreOut(BaseModel):
    skill_id: str
    name: str
    score: int | None
    level_description: str | None
    evidence: list[EvidenceOut]
    rationale: str


class LearningItemOut(BaseModel):
    skill_id: str
    title: str
    detail: str
    practice: list[str]


class ReportOut(BaseModel):
    session_id: uuid.UUID
    title: str
    level: str
    target_score: int
    scale: dict[int, str]
    verdict: str
    mean_score: float | None
    summary: str
    strengths: list[str]
    skills: list[SkillScoreOut]
    learning_plan: list[LearningItemOut]
    needs_review: bool
    graded_by: str
    checked_by: str | None
    rubric: str
    created_at: datetime


class ReportPending(BaseModel):
    status: str


class ProgressPoint(BaseModel):
    session_id: uuid.UUID
    date: datetime
    score: int


class SkillProgress(BaseModel):
    skill_id: str
    name: str
    points: list[ProgressPoint]  # oldest first
    latest: int
    previous: int | None
    delta: int | None


class RecurringGap(BaseModel):
    skill_id: str
    name: str
    title: str  # title of the most recent learning item for this skill
    sessions: int  # in how many graded sessions it came up


class RoleProgress(BaseModel):
    template_id: str
    title: str
    level: str
    sessions: int
    skills: list[SkillProgress]
    gaps: list[RecurringGap]


class ProgressOut(BaseModel):
    roles: list[RoleProgress]
