"""Offline stand-in for a real model, used in local development and tests.

It is not an AI. It reads the structured blocks our prompts already contain
and answers with simple rules, so the whole interview flow runs with no API
keys and no cost. Reports graded by it say so, because its scores only
reflect answer length.
"""

from __future__ import annotations

import json
import re
from typing import Any

from getter_api.llm.types import CompletionRequest, ProviderError, ProviderResponse, Usage

FOLLOW_UP_BELOW_WORDS = 25


def _block(text: str, tag: str) -> Any:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    if not match:
        raise ProviderError(f"dev provider: prompt has no <{tag}> block", retryable=False)
    return json.loads(match.group(1))


def _words(text: str) -> int:
    return len(text.split())


def _interview_turn(prompt: str) -> dict[str, Any]:
    context = _block(prompt, "turn_context")
    thread = _block(prompt, "conversation_json")
    answers = [t["text"] for t in thread if t["speaker"] == "candidate"]
    last = answers[-1] if answers else ""
    if context["followups_left"] > 0 and _words(last) < FOLLOW_UP_BELOW_WORDS:
        hints = context.get("interviewer_is_looking_for") or []
        hint = f" In particular: {hints[0].rstrip('.').lower()}." if hints else ""
        return {
            "action": "follow_up",
            "message": "Could you go a bit deeper on that and be more concrete?" + hint,
        }
    return {"action": "next", "message": "Thanks, let's move on."}


def _score_for(words: float) -> int:
    if words < 15:
        return 1
    if words < 40:
        return 2
    if words < 90:
        return 3
    return 4


def _grade(prompt: str) -> dict[str, Any]:
    rubric = _block(prompt, "rubric_json")
    transcript = _block(prompt, "transcript_json")
    target = rubric.get("target_score") or 2
    skills = []
    for skill in rubric["skills"]:
        turns = [
            t
            for t in transcript
            if t["speaker"] == "candidate" and t["section"] in skill["assessed_in_sections"]
        ]
        if not turns:
            skills.append(
                {
                    "skill_id": skill["skill_id"],
                    "score": None,
                    "evidence": [],
                    "rationale": "No answers in the sections that assess this skill.",
                }
            )
            continue
        avg = sum(_words(t["text"]) for t in turns) / len(turns)
        longest = max(turns, key=lambda t: _words(t["text"]))
        skills.append(
            {
                "skill_id": skill["skill_id"],
                "score": _score_for(avg),
                "evidence": [{"turn": longest["turn"], "quote": longest["text"][:120]}],
                "rationale": f"Dev grader: average answer length {avg:.0f} words.",
            }
        )
    names = {s["skill_id"]: s["name"] for s in rubric["skills"]}
    scored = sorted((s for s in skills if s["score"] is not None), key=lambda s: s["score"])
    gaps = [
        {
            "skill_id": s["skill_id"],
            "title": f"Go deeper on {names[s['skill_id']].lower()}",
            "detail": "Answers here were short. Explain your reasoning, trade-offs and a "
            "concrete example from your own work.",
            "practice": [
                f"Write a one-page explanation of a {names[s['skill_id']].lower()} problem "
                "you solved, including what you would do differently.",
            ],
        }
        for s in scored
        if s["score"] < max(target, 4)
    ][:3]
    strengths = [f"Most detailed answers on {names[s['skill_id']].lower()}." for s in scored[-1:]]
    return {
        "summary": "Graded by the offline dev grader, which only looks at answer length. "
        "Configure a real model for meaningful feedback.",
        "strengths": strengths,
        "skills": skills,
        "gaps": gaps,
    }


class DevProvider:
    async def complete(self, model: str, request: CompletionRequest) -> ProviderResponse:
        prompt = "\n".join(m.content for m in request.messages if m.role == "user")
        if request.task == "interview_turn":
            out = _interview_turn(prompt)
        elif request.task in ("grading", "grading_check"):
            out = _grade(prompt)
        else:
            raise ProviderError(f"dev provider has no handler for task {request.task!r}")
        text = json.dumps(out)
        return ProviderResponse(
            text=text,
            usage=Usage(input_tokens=len(prompt) // 4, output_tokens=len(text) // 4),
        )
