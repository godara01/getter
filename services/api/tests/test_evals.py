from __future__ import annotations

import json

from getter_api.content import library
from getter_api.evals import format_table, load_cases, run_eval
from getter_api.llm.config import load_llm_config
from getter_api.llm.gateway import LLMGateway
from getter_api.llm.types import CompletionRequest, ProviderResponse


def test_cases_match_their_rubrics() -> None:
    cases = load_cases()
    assert cases
    for case in cases:
        rubric = library().rubric_for(library().templates[case.template])
        assert set(case.expert_scores) == set(rubric.skill_ids), case.id
        sections = {s.id for s in library().templates[case.template].sections}
        assert {t.section for t in case.turns} <= sections


async def test_eval_measures_distance_from_expert_scores() -> None:
    cases = [c for c in load_cases() if c.id == "synthetic-devops-junior-weak"]

    class AlwaysThree:
        async def complete(self, model: str, request: CompletionRequest) -> ProviderResponse:
            turn = 1  # first candidate answer
            quote = cases[0].turns[turn].text[:20]
            skills = [
                {
                    "skill_id": s,
                    "score": 3,
                    "evidence": [{"turn": turn, "quote": quote}],
                    "rationale": "r",
                }
                for s in cases[0].expert_scores
            ]
            return ProviderResponse(json.dumps({"summary": "s", "skills": skills}))

    summary = await run_eval(
        "generous", LLMGateway(load_llm_config(), {"dev": AlwaysThree()}), cases
    )
    # Expert gave 1 everywhere; this grader says 3.
    assert summary.mae == 2.0
    assert summary.within_one == 0.0
    assert summary.verdict_agreement == 0.0
    assert "generous" in format_table([summary])


async def test_dev_config_runs_all_cases() -> None:
    summary = await run_eval("dev", LLMGateway(load_llm_config()), load_cases())
    assert len(summary.graded) == len(summary.results)
