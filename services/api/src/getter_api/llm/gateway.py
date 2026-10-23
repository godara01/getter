"""The one place the product calls AI models.

Each task (live interview turns, grading, the grading check) names an ordered
list of models in config. The gateway tries them in order, so a provider
outage or rate limit falls through to the next model instead of losing an
interview. Structured outputs are validated by our own Pydantic schemas with
one repair attempt per model, because providers differ in how reliably they
follow a JSON schema.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from getter_api.llm.config import LLMConfig, ModelRef, ProviderConfig
from getter_api.llm.providers.anthropic import AnthropicProvider
from getter_api.llm.providers.base import Provider
from getter_api.llm.providers.dev import DevProvider
from getter_api.llm.providers.openai_compat import OpenAICompatibleProvider
from getter_api.llm.types import (
    AllModelsFailed,
    CompletionRequest,
    CompletionResult,
    Message,
    ProviderError,
    Usage,
)

T = TypeVar("T", bound=BaseModel)


class OutputInvalid(Exception):
    """Raised by a semantic validator when parsed output breaks a rule."""


@dataclass
class StructuredResult[T: BaseModel]:
    value: T
    # Every billable call made to get the value, including failed repairs.
    calls: list[CompletionResult] = field(default_factory=list)

    @property
    def final(self) -> CompletionResult:
        return self.calls[-1]

    @property
    def cost_inr(self) -> float:
        return sum(c.cost_inr for c in self.calls)


class _MissingKeyProvider:
    def __init__(self, env_name: str) -> None:
        self._env_name = env_name

    async def complete(self, model: str, request: CompletionRequest) -> None:
        raise ProviderError(f"environment variable {self._env_name} is not set", retryable=False)


def build_provider(cfg: ProviderConfig, env: Mapping[str, str]) -> Provider:
    api_key = env.get(cfg.api_key_env) if cfg.api_key_env else None
    if cfg.api_key_env and not api_key:
        return _MissingKeyProvider(cfg.api_key_env)  # type: ignore[return-value]
    if cfg.kind == "dev":
        return DevProvider()
    if cfg.kind == "anthropic":
        return AnthropicProvider(
            api_key=api_key,
            base_url=cfg.base_url,
            timeout_seconds=cfg.timeout_seconds,
            extra_headers=cfg.extra_headers,
        )
    if not cfg.base_url:
        raise ValueError("openai_compatible providers need a base_url")
    return OpenAICompatibleProvider(
        base_url=cfg.base_url,
        api_key=api_key,
        supports_json_mode=cfg.supports_json_mode,
        timeout_seconds=cfg.timeout_seconds,
        extra_headers=cfg.extra_headers,
    )


def extract_json(text: str) -> str:
    """Pull the JSON object out of a reply that may wrap it in prose or fences."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in reply")
    return text[start : end + 1]


class LLMGateway:
    def __init__(
        self,
        config: LLMConfig,
        providers: Mapping[str, Provider] | None = None,
        *,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.config = config
        env = os.environ if env is None else env
        self._providers: dict[str, Provider] = dict(providers or {})
        for name, pcfg in config.providers.items():
            if name not in self._providers:
                self._providers[name] = build_provider(pcfg, env)

    def _cost(self, ref: ModelRef, usage: Usage) -> float:
        usd = (
            usage.input_tokens * ref.input_usd_per_mtok
            + usage.output_tokens * ref.output_usd_per_mtok
        ) / 1_000_000
        return round(usd * self.config.usd_to_inr, 6)

    async def _call(
        self, ref: ModelRef, request: CompletionRequest, failed: list[str]
    ) -> CompletionResult:
        started = time.perf_counter()
        resp = await self._providers[ref.provider].complete(ref.model, request)
        return CompletionResult(
            text=resp.text,
            provider=ref.provider,
            model=ref.model,
            usage=resp.usage,
            cost_inr=self._cost(ref, resp.usage),
            latency_ms=int((time.perf_counter() - started) * 1000),
            failed_attempts=tuple(failed),
        )

    def _request(self, task: str, messages: list[Message], json_output: bool) -> CompletionRequest:
        tcfg = self.config.task(task)
        return CompletionRequest(
            messages=messages,
            max_tokens=tcfg.max_tokens,
            temperature=tcfg.temperature,
            json_output=json_output,
            task=task,
        )

    async def complete(self, task: str, messages: list[Message]) -> CompletionResult:
        request = self._request(task, messages, json_output=False)
        failed: list[str] = []
        for ref in self.config.task(task).models:
            try:
                return await self._call(ref, request, failed)
            except ProviderError as exc:
                failed.append(f"{ref.provider}/{ref.model}: {exc}")
        raise AllModelsFailed(task, failed)

    async def complete_json(
        self,
        task: str,
        messages: list[Message],
        schema: type[T],
        validate: Callable[[T], None] | None = None,
    ) -> StructuredResult[T]:
        """Get a reply that parses into `schema` and passes `validate`.

        `validate` raises OutputInvalid for rules a JSON schema can't express,
        such as "every evidence quote must appear in the transcript".
        """
        failed: list[str] = []
        calls: list[CompletionResult] = []
        for ref in self.config.task(task).models:
            attempt_messages = list(messages)
            for attempt in range(2):
                request = self._request(task, attempt_messages, json_output=True)
                try:
                    result = await self._call(ref, request, failed)
                except ProviderError as exc:
                    failed.append(f"{ref.provider}/{ref.model}: {exc}")
                    break
                calls.append(result)
                try:
                    value = schema.model_validate(json.loads(extract_json(result.text)))
                    if validate:
                        validate(value)
                    return StructuredResult(value=value, calls=calls)
                except (ValueError, ValidationError, OutputInvalid) as exc:
                    problem = str(exc)[:1500]
                    failed.append(
                        f"{ref.provider}/{ref.model} attempt {attempt + 1}: invalid output"
                    )
                    attempt_messages = [
                        *messages,
                        Message("assistant", result.text),
                        Message(
                            "user",
                            "That reply could not be used: "
                            f"{problem}\nReply again with only the corrected JSON object.",
                        ),
                    ]
        raise AllModelsFailed(task, failed, calls)
