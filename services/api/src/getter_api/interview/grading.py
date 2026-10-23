"""Grades a finished session against its rubric and writes the feedback report.

Scores must be traceable: every score quotes the candidate's own words from a
specific turn, and records the rubric version and model that produced it.
A session whose grading fails gets no score at all.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from getter_api.content import ContentLibrary, Rubric, Template
from getter_api.interview.engine import record_calls
from getter_api.interview.prompts import PROMPT_VERSION, grader_messages
from getter_api.interview.schemas import GradeOutput
from getter_api.llm.gateway import LLMGateway, OutputInvalid, StructuredResult
from getter_api.llm.types import AllModelsFailed, Message
from getter_api.models import FeedbackReport, InterviewSession, LearningItem, SkillScore
from getter_api.settings import Settings

log = logging.getLogger(__name__)


def _normalise(text: str) -> str:
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().casefold()


def quote_in_text(quote: str, text: str) -> bool:
    """True if every part of the quote (split on ellipses) appears in the text."""
    haystack = _normalise(text)
    parts = [p.strip(" \"'") for p in re.split(r"\.\.\.|…", _normalise(quote))]
    parts = [p for p in parts if p]
    return bool(parts) and all(p in haystack for p in parts)


def make_validator(
    rubric: Rubric, candidate_turns: dict[int, str]
) -> Callable[[GradeOutput], None]:
    def validate(out: GradeOutput) -> None:
        problems: list[str] = []
        ids = [s.skill_id for s in out.skills]
        expected = set(rubric.skill_ids)
        if set(ids) != expected or len(ids) != len(expected):
            problems.append(
                f"'skills' must contain each of {sorted(expected)} exactly once; got {ids}"
            )
        for s in out.skills:
            if s.score is not None and not s.evidence:
                problems.append(f"skill {s.skill_id} has a score but no evidence")
            for e in s.evidence:
                if e.turn not in candidate_turns:
                    problems.append(f"skill {s.skill_id}: turn {e.turn} is not a candidate turn")
                elif not quote_in_text(e.quote, candidate_turns[e.turn]):
                    problems.append(
                        f"skill {s.skill_id}: quote {e.quote[:60]!r} is not in turn {e.turn}; "
                        "copy the candidate's words exactly"
                    )
        for g in out.gaps:
            if g.skill_id not in expected:
                problems.append(f"gap uses unknown skill_id {g.skill_id}")
        if problems:
            raise OutputInvalid("; ".join(problems))

    return validate


@dataclass
class Verdict:
    verdict: str
    mean: float | None


def compute_verdict(scores: list[int | None], bar: int) -> Verdict:
    """Decided in code from the scores, never by the model."""
    assessed = [s for s in scores if s is not None]
    if not scores or len(assessed) * 2 < len(scores):
        return Verdict("insufficient_evidence", None)
    mean = sum(assessed) / len(assessed)
    lowest = min(assessed)
    if mean >= bar + 1 and lowest >= bar:
        verdict = "above"
    elif mean >= bar and lowest >= bar - 1:
        verdict = "meets"
    else:
        verdict = "below"
    return Verdict(verdict, round(mean, 2))


def disagreement(a: GradeOutput, b: GradeOutput, threshold: int) -> str | None:
    b_scores = {s.skill_id: s.score for s in b.skills}
    diffs = []
    for s in a.skills:
        other = b_scores.get(s.skill_id)
        if s.score is not None and other is not None and abs(s.score - other) >= threshold:
            diffs.append(f"{s.skill_id}: {s.score} vs {other}")
    return ("graders disagree on " + ", ".join(diffs)) if diffs else None


class TurnLike(Protocol):
    index: int
    speaker: str
    kind: str
    section_id: str | None
    text: str


def grading_request(
    template: Template, rubric: Rubric, level: str, turns: Sequence[TurnLike]
) -> tuple[list[Message], Callable[[GradeOutput], None]]:
    """The grading prompt and its output validator; shared by the app and the evals."""
    transcript = [
        {"turn": t.index, "speaker": t.speaker, "section": t.section_id, "text": t.text}
        for t in turns
        if t.kind != "intro"
    ]
    candidate_turns = {t.index: t.text for t in turns if t.speaker == "candidate"}
    messages = grader_messages(template=template, rubric=rubric, level=level, transcript=transcript)
    return messages, make_validator(rubric, candidate_turns)


class Grader:
    def __init__(self, gateway: LLMGateway, content: ContentLibrary, settings: Settings) -> None:
        self.gateway = gateway
        self.content = content
        self.settings = settings

    async def _run(
        self,
        db: AsyncSession,
        session: InterviewSession,
        task: str,
        messages: Any,
        validate: Any,
    ) -> StructuredResult[GradeOutput]:
        try:
            result = await self.gateway.complete_json(task, messages, GradeOutput, validate)
        except AllModelsFailed as exc:
            record_calls(db, session, task, exc.calls, ok=False)
            raise
        record_calls(db, session, task, result.calls, ok=True)
        return result

    async def grade(self, db: AsyncSession, session: InterviewSession) -> None:
        template = self.content.templates[session.template_id]
        rubric = self.content.rubric_for(template)
        if rubric.version != session.rubric_version:
            log.warning(
                "session %s used rubric v%s, grading with v%s",
                session.id,
                session.rubric_version,
                rubric.version,
            )
        messages, validate = grading_request(template, rubric, session.level, session.turns)

        try:
            primary = await self._run(db, session, "grading", messages, validate)
        except AllModelsFailed as exc:
            session.status = "failed"
            session.error = f"grading failed: {exc}"[:2000]
            await db.commit()
            return

        review_reason: str | None = None
        check_model: str | None = None
        if self.settings.grading_consistency_check and "grading_check" in self.gateway.config.tasks:
            try:
                check = await self._run(db, session, "grading_check", messages, validate)
                check_model = f"{check.final.provider}/{check.final.model}"
                review_reason = disagreement(
                    primary.value, check.value, self.settings.consistency_flag_difference
                )
            except AllModelsFailed:
                review_reason = "consistency check could not run"

        grader_model = f"{primary.final.provider}/{primary.final.model}"
        out = primary.value
        order = {sid: i for i, sid in enumerate(rubric.skill_ids)}
        skills = sorted(out.skills, key=lambda s: order[s.skill_id])
        verdict = compute_verdict([s.score for s in skills], rubric.level_bars[session.level])  # type: ignore[index]

        report = FeedbackReport(
            session_id=session.id,
            summary=out.summary,
            strengths={"items": out.strengths},
            verdict=verdict.verdict,
            mean_score=verdict.mean,
            needs_review=review_reason is not None,
            review_reason=review_reason,
            grader_model=grader_model,
            check_model=check_model,
            prompt_version=PROMPT_VERSION,
            skill_scores=[
                SkillScore(
                    skill_id=s.skill_id,
                    score=s.score,
                    evidence={"items": [e.model_dump() for e in s.evidence]},
                    rationale=s.rationale,
                    rubric_id=rubric.id,
                    rubric_version=rubric.version,
                    grader_model=grader_model,
                )
                for s in skills
            ],
            learning_items=[
                LearningItem(
                    position=i,
                    skill_id=g.skill_id,
                    title=g.title,
                    detail=g.detail,
                    practice={"items": g.practice},
                )
                for i, g in enumerate(out.gaps)
            ],
        )
        db.add(report)
        session.status = "completed"
        await db.commit()
