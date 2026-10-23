from __future__ import annotations

import pytest

from getter_api.content import library
from getter_api.interview.grading import (
    compute_verdict,
    disagreement,
    make_validator,
    quote_in_text,
)
from getter_api.interview.schemas import GradeOutput
from getter_api.llm.gateway import OutputInvalid


def test_quote_matching_is_whitespace_and_case_insensitive() -> None:
    text = "I would add a UNIQUE index on the code column.\nThen return 409."
    assert quote_in_text("unique index on the code   column", text)
    assert quote_in_text("I would add ... return 409", text)
    assert quote_in_text("“Then return 409.”", text)
    assert not quote_in_text("use a bloom filter", text)
    assert not quote_in_text("...", text)


@pytest.mark.parametrize(
    ("scores", "bar", "verdict"),
    [
        ([2, 2, 2, 2], 2, "meets"),
        ([3, 3, 1, 3], 2, "meets"),
        ([3, 3, 1, 3], 3, "below"),
        ([3, 3, 3, 3], 2, "above"),
        ([2, 2, 1, 1], 2, "below"),
        ([4, None, None, None], 2, "insufficient_evidence"),
        ([2, 3, None, None], 2, "meets"),
    ],
)
def test_verdict_is_computed_from_scores(scores: list[int | None], bar: int, verdict: str) -> None:
    assert compute_verdict(scores, bar).verdict == verdict


def _grade(rubric_skills: list[str], score: int, turn: int, quote: str) -> GradeOutput:
    return GradeOutput.model_validate(
        {
            "summary": "s",
            "skills": [
                {
                    "skill_id": s,
                    "score": score,
                    "evidence": [{"turn": turn, "quote": quote}],
                    "rationale": "r",
                }
                for s in rubric_skills
            ],
        }
    )


def test_validator_rejects_fabricated_quotes_and_wrong_turns() -> None:
    rubric = library().rubrics["backend-junior-mid"]
    validate = make_validator(rubric, {3: "I used Postgres with a unique index."})
    validate(_grade(rubric.skill_ids, 3, 3, "unique index"))
    with pytest.raises(OutputInvalid, match="not in turn 3"):
        validate(_grade(rubric.skill_ids, 3, 3, "I used sharding"))
    with pytest.raises(OutputInvalid, match="not a candidate turn"):
        validate(_grade(rubric.skill_ids, 3, 2, "unique index"))
    with pytest.raises(OutputInvalid, match="exactly once"):
        validate(_grade(rubric.skill_ids[:-1], 3, 3, "unique index"))


def test_validator_requires_evidence_for_scores() -> None:
    rubric = library().rubrics["backend-junior-mid"]
    validate = make_validator(rubric, {1: "x"})
    out = GradeOutput.model_validate(
        {
            "summary": "s",
            "skills": [{"skill_id": s, "score": 2, "rationale": "r"} for s in rubric.skill_ids],
        }
    )
    with pytest.raises(OutputInvalid, match="no evidence"):
        validate(out)


def test_disagreement_flags_large_differences_only() -> None:
    skills = ["a", "b"]
    a = _grade(skills, 2, 1, "q")
    assert disagreement(a, _grade(skills, 3, 1, "q"), 2) is None
    assert "a: 2 vs 4" in (disagreement(a, _grade(skills, 4, 1, "q"), 2) or "")
