"""Compare grading models against expert-graded transcripts.

Each case is a transcript plus the scores an experienced interviewer gave it.
Every candidate model config grades every case, and we report how far its
scores are from the expert's and what it cost, so the cheapest model that is
close enough wins. Run:

    uv run python -m getter_api.evals --config a.yaml --config b.yaml [cases_dir]
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from getter_api.content import ContentLibrary, library
from getter_api.interview.grading import compute_verdict, grading_request
from getter_api.interview.schemas import GradeOutput
from getter_api.llm.gateway import LLMGateway
from getter_api.llm.types import AllModelsFailed

CASES_DIR = Path(__file__).parent / "cases"


class CaseTurn(BaseModel):
    speaker: Literal["interviewer", "candidate"]
    section: str
    text: str


class EvalCase(BaseModel):
    id: str
    template: str
    level: Literal["junior", "mid"]
    # Synthetic cases only check that the harness works. Model choice needs
    # real transcripts graded by an experienced interviewer.
    synthetic: bool = False
    turns: list[CaseTurn]
    expert_scores: dict[str, int | None]


@dataclass
class _Turn:
    index: int
    speaker: str
    kind: str
    section_id: str | None
    text: str


@dataclass
class CaseResult:
    case_id: str
    ok: bool
    model: str = ""
    abs_errors: list[int] = field(default_factory=list)
    assessed_mismatches: int = 0
    verdict_match: bool = False
    cost_inr: float = 0.0
    seconds: float = 0.0
    error: str = ""


@dataclass
class EvalSummary:
    label: str
    results: list[CaseResult]

    @property
    def graded(self) -> list[CaseResult]:
        return [r for r in self.results if r.ok]

    @property
    def mae(self) -> float | None:
        errors = [e for r in self.graded for e in r.abs_errors]
        return sum(errors) / len(errors) if errors else None

    @property
    def within_one(self) -> float | None:
        errors = [e for r in self.graded for e in r.abs_errors]
        return sum(e <= 1 for e in errors) / len(errors) if errors else None

    @property
    def verdict_agreement(self) -> float | None:
        g = self.graded
        return sum(r.verdict_match for r in g) / len(g) if g else None

    @property
    def cost_per_case(self) -> float:
        return sum(r.cost_inr for r in self.results) / max(1, len(self.results))


def load_cases(path: Path = CASES_DIR) -> list[EvalCase]:
    cases = []
    for f in sorted(path.glob("*.yaml")):
        with f.open() as fh:
            cases.append(EvalCase.model_validate(yaml.safe_load(fh)))
    return cases


async def grade_case(gateway: LLMGateway, case: EvalCase, content: ContentLibrary) -> CaseResult:
    template = content.templates[case.template]
    rubric = content.rubric_for(template)
    turns = [_Turn(i, t.speaker, "turn", t.section, t.text) for i, t in enumerate(case.turns)]
    messages, validate = grading_request(template, rubric, case.level, turns)
    started = time.perf_counter()
    try:
        result = await gateway.complete_json("grading", messages, GradeOutput, validate)
    except AllModelsFailed as exc:
        return CaseResult(
            case.id, ok=False, cost_inr=sum(c.cost_inr for c in exc.calls), error=str(exc)
        )
    model_scores = {s.skill_id: s.score for s in result.value.skills}
    out = CaseResult(
        case.id,
        ok=True,
        model=f"{result.final.provider}/{result.final.model}",
        cost_inr=result.cost_inr,
        seconds=time.perf_counter() - started,
    )
    for skill_id, expert in case.expert_scores.items():
        model = model_scores.get(skill_id)
        if expert is None or model is None:
            out.assessed_mismatches += (expert is None) != (model is None)
        else:
            out.abs_errors.append(abs(expert - model))
    bar = rubric.level_bars[case.level]
    expert_verdict = compute_verdict([case.expert_scores.get(s) for s in rubric.skill_ids], bar)
    model_verdict = compute_verdict([model_scores.get(s) for s in rubric.skill_ids], bar)
    out.verdict_match = expert_verdict.verdict == model_verdict.verdict
    return out


async def run_eval(
    label: str, gateway: LLMGateway, cases: list[EvalCase], content: ContentLibrary | None = None
) -> EvalSummary:
    content = content or library()
    return EvalSummary(label, [await grade_case(gateway, c, content) for c in cases])


def format_table(summaries: list[EvalSummary]) -> str:
    def pct(v: float | None) -> str:
        return "-" if v is None else f"{v:.0%}"

    rows = [("config", "graded", "MAE", "within 1", "verdict agree", "INR/case")]
    for s in summaries:
        rows.append(
            (
                s.label,
                f"{len(s.graded)}/{len(s.results)}",
                "-" if s.mae is None else f"{s.mae:.2f}",
                pct(s.within_one),
                pct(s.verdict_agreement),
                f"{s.cost_per_case:.2f}",
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)) for r in rows)
