"""Structured outputs we ask models for. Validated in our code, whatever the vendor."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class InterviewerDecision(BaseModel):
    action: Literal["follow_up", "next"]
    # For follow_up: the follow-up question. For next: an optional short,
    # neutral acknowledgement; the code adds the next question itself.
    message: str = Field(default="", max_length=1200)

    @model_validator(mode="after")
    def _follow_up_needs_question(self) -> InterviewerDecision:
        if self.action == "follow_up" and not self.message.strip():
            raise ValueError("a follow_up needs a message with the question")
        return self


class Evidence(BaseModel):
    turn: int
    quote: str = Field(min_length=1, max_length=400)


class SkillGrade(BaseModel):
    skill_id: str
    # None means the transcript holds no evidence for this skill.
    score: int | None = Field(default=None, ge=1, le=4)
    evidence: list[Evidence] = Field(default_factory=list, max_length=4)
    rationale: str = Field(max_length=1500)


class Gap(BaseModel):
    skill_id: str
    title: str = Field(max_length=200)
    detail: str = Field(max_length=1500)
    practice: list[str] = Field(min_length=1, max_length=4)


class GradeOutput(BaseModel):
    summary: str = Field(max_length=2000)
    strengths: list[str] = Field(default_factory=list, max_length=3)
    skills: list[SkillGrade]
    gaps: list[Gap] = Field(default_factory=list, max_length=3)
