"""Turn a spoken test call's measurements into latency, cost per minute and a verdict.

Latency is what the candidate feels: from the end of their speech to the first audio of the
reply. It is the sum of the pipeline stages for each turn. Cost is vendor usage times the
prices entered from the vendors' own pricing pages. Thresholds are proposals for Sanket to
change; they are inputs here, not facts.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from pydantic import BaseModel, Field

STAGES = ("endpointing_ms", "stt_ms", "llm_first_token_ms", "tts_first_audio_ms", "network_ms")


class Turn(BaseModel):
    """Milliseconds spent in each stage of one reply. Unmeasured stages count as zero."""

    endpointing_ms: float = Field(default=0, ge=0)  # waiting to be sure the speaker stopped
    stt_ms: float = Field(default=0, ge=0)  # final transcript after the speech ended
    llm_first_token_ms: float = Field(default=0, ge=0)
    tts_first_audio_ms: float = Field(default=0, ge=0)
    network_ms: float = Field(default=0, ge=0)  # round trips between browser, room and agent

    @property
    def total_ms(self) -> float:
        return float(sum(getattr(self, s) for s in STAGES))


class Usage(BaseModel):
    stt_audio_minutes: float = Field(default=0, ge=0)
    llm_input_tokens: int = Field(default=0, ge=0)
    llm_output_tokens: int = Field(default=0, ge=0)
    tts_characters: int = Field(default=0, ge=0)
    other_inr: float = Field(default=0, ge=0)  # for example LiveKit minutes beyond the free tier


class Prices(BaseModel):
    stt_inr_per_minute: float = Field(ge=0)
    llm_inr_per_million_input: float = Field(ge=0)
    llm_inr_per_million_output: float = Field(ge=0)
    tts_inr_per_1k_characters: float = Field(ge=0)


class Thresholds(BaseModel):
    p50_ms: float = 1500
    p95_ms: float = 3000
    max_inr_per_minute: float = 10  # about INR 400 for a 40 minute interview


class Measurement(BaseModel):
    label: str
    duration_minutes: float = Field(gt=0)
    turns: list[Turn] = Field(min_length=1)
    usage: Usage
    prices: Prices


class Summary(BaseModel):
    label: str
    turns: int
    p50_ms: float
    p95_ms: float
    stage_p50_ms: dict[str, float]
    slowest_stage: str
    cost_inr: float
    cost_breakdown: dict[str, float]
    cost_per_minute_inr: float
    projected_40_min_inr: float
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile; simple and the same on every platform."""
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def summarize(m: Measurement, limits: Thresholds | None = None) -> Summary:
    limits = limits or Thresholds()
    totals = [t.total_ms for t in m.turns]
    stage_p50 = {s: percentile([getattr(t, s) for t in m.turns], 50) for s in STAGES}
    breakdown = {
        "speech_to_text": m.usage.stt_audio_minutes * m.prices.stt_inr_per_minute,
        "llm": (
            m.usage.llm_input_tokens * m.prices.llm_inr_per_million_input
            + m.usage.llm_output_tokens * m.prices.llm_inr_per_million_output
        )
        / 1_000_000,
        "text_to_speech": m.usage.tts_characters / 1000 * m.prices.tts_inr_per_1k_characters,
        "other": m.usage.other_inr,
    }
    cost = sum(breakdown.values())
    per_minute = cost / m.duration_minutes
    p50, p95 = percentile(totals, 50), percentile(totals, 95)
    failures = []
    if p50 > limits.p50_ms:
        failures.append(f"median delay {p50:.0f} ms is over {limits.p50_ms:.0f} ms")
    if p95 > limits.p95_ms:
        failures.append(
            f"slow replies (95th percentile) {p95:.0f} ms are over {limits.p95_ms:.0f} ms"
        )
    if per_minute > limits.max_inr_per_minute:
        failures.append(
            f"cost INR {per_minute:.2f} a minute is over INR {limits.max_inr_per_minute:.2f}"
        )
    return Summary(
        label=m.label,
        turns=len(m.turns),
        p50_ms=p50,
        p95_ms=p95,
        stage_p50_ms=stage_p50,
        slowest_stage=max(stage_p50, key=lambda s: stage_p50[s]),
        cost_inr=cost,
        cost_breakdown=breakdown,
        cost_per_minute_inr=per_minute,
        projected_40_min_inr=per_minute * 40,
        failures=failures,
    )


def load(path: Path) -> Measurement:
    return Measurement.model_validate(json.loads(path.read_text()))


def format_table(summaries: list[Summary]) -> str:
    head = f"{'setup':<28}{'turns':>6}{'p50 ms':>9}{'p95 ms':>9}{'INR/min':>9}{'40 min':>9}  result"
    lines = [head, "-" * len(head)]
    for s in summaries:
        result = "pass" if s.passed else "fail: " + "; ".join(s.failures)
        lines.append(
            f"{s.label[:27]:<28}{s.turns:>6}{s.p50_ms:>9.0f}{s.p95_ms:>9.0f}"
            f"{s.cost_per_minute_inr:>9.2f}{s.projected_40_min_inr:>9.0f}  {result}"
        )
        lines.append(
            f"{'':<28}slowest stage: {s.slowest_stage.removesuffix('_ms')}; cost split: "
            + ", ".join(f"{k} {v:.2f}" for k, v in s.cost_breakdown.items())
        )
    return "\n".join(lines)
