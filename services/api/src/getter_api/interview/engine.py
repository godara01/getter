"""Runs a text practice interview: question plan, follow-ups, section timing.

The plan (sections, questions, time limits, follow-up budget) is enforced
here in code. The model only decides whether to probe deeper on the current
question and words the follow-up.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from getter_api.content import ContentLibrary, Question, Rubric, Section, Template
from getter_api.db import as_utc, utcnow
from getter_api.interview.prompts import PROMPT_VERSION, interviewer_messages
from getter_api.interview.schemas import InterviewerDecision
from getter_api.llm.gateway import LLMGateway
from getter_api.llm.types import AllModelsFailed, CompletionResult
from getter_api.models import InterviewSession, LLMCall, SessionTurn, User
from getter_api.settings import Settings

log = logging.getLogger(__name__)

CLOSING = (
    "That's the end of the interview. Thank you. Your feedback report is being "
    "prepared and will be ready in a minute or two."
)
MOVE_ON = "Thanks, let's move on."
SECTION_TIME_UP = "We're out of time for this section, so let's move on."


class InterviewError(Exception):
    """A request the interview can't accept in its current state."""


@dataclass
class Position:
    template: Template
    rubric: Rubric
    section: Section
    question: Question


def record_calls(
    db: AsyncSession,
    session: InterviewSession | None,
    task: str,
    calls: list[CompletionResult],
    *,
    ok: bool,
) -> None:
    for i, call in enumerate(calls):
        db.add(
            LLMCall(
                session_id=session.id if session else None,
                user_id=session.user_id if session else None,
                task=task,
                provider=call.provider,
                model=call.model,
                input_tokens=call.usage.input_tokens,
                output_tokens=call.usage.output_tokens,
                cost_inr=call.cost_inr,
                latency_ms=call.latency_ms,
                # Only the last call of a successful run produced the output.
                ok=ok and i == len(calls) - 1,
            )
        )
        if session is not None:
            session.ai_cost_inr += call.cost_inr
            session.input_tokens += call.usage.input_tokens
            session.output_tokens += call.usage.output_tokens


class InterviewEngine:
    def __init__(
        self,
        gateway: LLMGateway,
        content: ContentLibrary,
        settings: Settings,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.gateway = gateway
        self.content = content
        self.settings = settings
        self.clock = clock

    # -- helpers ---------------------------------------------------------

    def template(self, template_id: str) -> Template:
        try:
            return self.content.templates[template_id]
        except KeyError:
            raise InterviewError(f"unknown template {template_id!r}") from None

    def position(self, session: InterviewSession) -> Position:
        template = self.template(session.template_id)
        section = template.sections[session.section_index]
        return Position(
            template=template,
            rubric=self.content.rubric_for(template),
            section=section,
            question=section.questions[session.question_index],
        )

    def section_seconds_left(self, session: InterviewSession) -> int | None:
        if session.status != "in_progress":
            return None
        pos = self.position(session)
        elapsed = (self.clock() - as_utc(session.section_started_at)).total_seconds()
        return max(0, int(pos.section.time_limit_minutes * 60 - elapsed))

    def _add_turn(
        self,
        session: InterviewSession,
        *,
        speaker: str,
        kind: str,
        text: str,
        section_id: str | None = None,
        question_id: str | None = None,
    ) -> SessionTurn:
        turn = SessionTurn(
            index=len(session.turns),
            speaker=speaker,
            kind=kind,
            text=text,
            section_id=section_id,
            question_id=question_id,
        )
        session.turns.append(turn)
        return turn

    def _ask_current_question(self, session: InterviewSession, preface: str = "") -> None:
        pos = self.position(session)
        text = pos.question.prompt.strip()
        if session.question_index == 0:
            n, total = session.section_index + 1, len(pos.template.sections)
            text = f"Section {n} of {total}: {pos.section.title}.\n\n{text}"
        if preface:
            text = f"{preface}\n\n{text}"
        self._add_turn(
            session,
            speaker="interviewer",
            kind="question",
            text=text,
            section_id=pos.section.id,
            question_id=pos.question.id,
        )

    def _finish(self, session: InterviewSession, preface: str = "") -> None:
        text = f"{preface}\n\n{CLOSING}" if preface else CLOSING
        self._add_turn(session, speaker="interviewer", kind="closing", text=text)
        session.status = "grading"
        session.ended_at = self.clock()

    def _advance(self, session: InterviewSession, *, preface: str, skip_section: bool) -> None:
        """Move to the next question, or the next section, or finish."""
        template = self.template(session.template_id)
        section = template.sections[session.section_index]
        session.followups_used = 0
        if not skip_section and session.question_index + 1 < len(section.questions):
            session.question_index += 1
        elif session.section_index + 1 < len(template.sections):
            session.section_index += 1
            session.question_index = 0
            session.section_started_at = self.clock()
        else:
            self._finish(session, preface)
            return
        self._ask_current_question(session, preface)

    # -- public API ------------------------------------------------------

    def start(self, user: User, template_id: str, level: str) -> InterviewSession:
        template = self.template(template_id)
        if level not in template.levels:
            raise InterviewError(f"level must be one of {template.levels}")
        rubric = self.content.rubric_for(template)
        session = InterviewSession(
            user_id=user.id,
            template_id=template.id,
            template_version=template.version,
            rubric_id=rubric.id,
            rubric_version=rubric.version,
            prompt_version=PROMPT_VERSION,
            created_at=self.clock(),
            level=level,
            kind="practice",
            status="in_progress",
            section_index=0,
            question_index=0,
            followups_used=0,
            section_started_at=self.clock(),
            ai_cost_inr=0.0,
            input_tokens=0,
            output_tokens=0,
            turns=[],
        )
        self._add_turn(session, speaker="interviewer", kind="intro", text=template.intro.strip())
        self._ask_current_question(session)
        return session

    async def answer(self, db: AsyncSession, session: InterviewSession, text: str) -> None:
        """Record the candidate's answer and add the interviewer's next turn."""
        if session.status != "in_progress":
            raise InterviewError("this interview is not in progress")
        text = text.strip()
        if not text:
            raise InterviewError("answer is empty")
        if len(text) > self.settings.max_answer_chars:
            raise InterviewError(
                f"answer is longer than {self.settings.max_answer_chars} characters"
            )

        pos = self.position(session)
        self._add_turn(
            session,
            speaker="candidate",
            kind="answer",
            text=text,
            section_id=pos.section.id,
            question_id=pos.question.id,
        )

        answers = sum(1 for t in session.turns if t.speaker == "candidate")
        if answers >= self.settings.max_candidate_turns:
            self._finish(session, "We've reached the length limit for this interview.")
            return

        if self.section_seconds_left(session) == 0:
            self._advance(session, preface=SECTION_TIME_UP, skip_section=True)
            return

        followups_left = pos.section.max_followups - session.followups_used
        decision = InterviewerDecision(action="next", message=MOVE_ON)
        if followups_left > 0:
            decision = await self._decide(db, session, pos, followups_left)

        if decision.action == "follow_up":
            session.followups_used += 1
            self._add_turn(
                session,
                speaker="interviewer",
                kind="follow_up",
                text=decision.message.strip(),
                section_id=pos.section.id,
                question_id=pos.question.id,
            )
        else:
            self._advance(session, preface=decision.message.strip(), skip_section=False)

    async def _decide(
        self, db: AsyncSession, session: InterviewSession, pos: Position, followups_left: int
    ) -> InterviewerDecision:
        thread = [
            {"speaker": t.speaker, "text": t.text}
            for t in session.turns
            if t.question_id == pos.question.id
        ]
        messages = interviewer_messages(
            template=pos.template,
            rubric=pos.rubric,
            level=session.level,
            section=pos.section,
            question_prompt=pos.question.prompt,
            look_for=pos.question.look_for,
            followups_left=followups_left,
            thread=thread,
        )
        try:
            result = await self.gateway.complete_json(
                "interview_turn", messages, InterviewerDecision
            )
        except AllModelsFailed as exc:
            # Keep the interview going on the scripted plan rather than lose it.
            log.warning("interviewer model failed, moving on: %s", exc)
            record_calls(db, session, "interview_turn", exc.calls, ok=False)
            return InterviewerDecision(action="next", message=MOVE_ON)
        record_calls(db, session, "interview_turn", result.calls, ok=True)
        return result.value

    def end_early(self, session: InterviewSession) -> None:
        if session.status != "in_progress":
            raise InterviewError("this interview is not in progress")
        if any(t.speaker == "candidate" for t in session.turns):
            self._finish(session, "Ending the interview here, as you asked.")
        else:
            session.status = "abandoned"
            session.ended_at = self.clock()
