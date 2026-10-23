"""Provider-neutral request and response types.

Nothing outside `getter_api.llm.providers` knows which vendor serves a call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class CompletionRequest:
    """One chat completion, described without any vendor-specific fields."""

    messages: list[Message]
    max_tokens: int = 1024
    temperature: float = 0.2
    # Ask the provider for a JSON object when it supports a JSON mode. Our own
    # validation in `structured.py` is what we rely on; this is only a hint.
    json_output: bool = False
    # The task name lets the offline dev provider answer sensibly. Real
    # providers ignore it.
    task: str = ""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    usage: Usage = field(default_factory=Usage)


@dataclass(frozen=True)
class CompletionResult:
    text: str
    provider: str
    model: str
    usage: Usage
    cost_inr: float
    latency_ms: int
    # Models tried before this one succeeded, as "provider/model: reason".
    failed_attempts: tuple[str, ...] = ()


class ProviderError(Exception):
    """A provider call failed. `retryable` errors move on to the next model."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class AllModelsFailed(Exception):
    """Every model configured for a task failed."""

    def __init__(
        self, task: str, attempts: list[str], calls: list[CompletionResult] | None = None
    ) -> None:
        super().__init__(f"all models failed for task {task!r}: " + "; ".join(attempts))
        self.task = task
        self.attempts = attempts
        # Billable calls that returned unusable output; still count as cost.
        self.calls = calls or []
