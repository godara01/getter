from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from getter_api.llm.config import LLMConfig, load_llm_config
from getter_api.llm.gateway import LLMGateway, OutputInvalid, extract_json
from getter_api.llm.providers.anthropic import AnthropicProvider
from getter_api.llm.providers.openai_compat import OpenAICompatibleProvider
from getter_api.llm.types import (
    AllModelsFailed,
    CompletionRequest,
    Message,
    ProviderError,
    ProviderResponse,
    Usage,
)

LLM_DIR = Path(__file__).parents[1] / "src" / "getter_api" / "llm"


class Scripted:
    """A provider that replays canned replies or errors, and records requests."""

    def __init__(self, *replies: str | Exception) -> None:
        self.replies = list(replies)
        self.requests: list[tuple[str, CompletionRequest]] = []

    async def complete(self, model: str, request: CompletionRequest) -> ProviderResponse:
        self.requests.append((model, request))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return ProviderResponse(reply, Usage(input_tokens=1000, output_tokens=500))


def two_model_config(**task: object) -> LLMConfig:
    return LLMConfig.model_validate(
        {
            "usd_to_inr": 100,
            "providers": {"a": {"kind": "dev"}, "b": {"kind": "dev"}},
            "tasks": {
                "t": {
                    "models": [
                        {
                            "provider": "a",
                            "model": "a-1",
                            "input_usd_per_mtok": 1,
                            "output_usd_per_mtok": 4,
                        },
                        {"provider": "b", "model": "b-1"},
                    ],
                    **task,
                }
            },
        }
    )


class Answer(BaseModel):
    answer: int


MSGS = [Message("system", "s"), Message("user", "u")]


async def test_falls_back_to_next_model_on_provider_error() -> None:
    a, b = Scripted(ProviderError("HTTP 429")), Scripted("hello")
    gw = LLMGateway(two_model_config(), {"a": a, "b": b})
    result = await gw.complete("t", MSGS)
    assert result.text == "hello"
    assert (result.provider, result.model) == ("b", "b-1")
    assert result.failed_attempts == ("a/a-1: HTTP 429",)


async def test_all_models_failing_raises() -> None:
    gw = LLMGateway(
        two_model_config(), {"a": Scripted(ProviderError("x")), "b": Scripted(ProviderError("y"))}
    )
    with pytest.raises(AllModelsFailed) as info:
        await gw.complete("t", MSGS)
    assert len(info.value.attempts) == 2


async def test_cost_is_computed_from_config_prices() -> None:
    gw = LLMGateway(two_model_config(), {"a": Scripted("ok"), "b": Scripted()})
    result = await gw.complete("t", MSGS)
    # 1000 in * $1/M + 500 out * $4/M = $0.003, at 100 INR per USD.
    assert result.cost_inr == pytest.approx(0.3)


async def test_task_settings_reach_the_provider() -> None:
    a = Scripted("ok")
    gw = LLMGateway(two_model_config(max_tokens=77, temperature=0.9), {"a": a, "b": Scripted()})
    await gw.complete("t", MSGS)
    _model, request = a.requests[0]
    assert (request.max_tokens, request.temperature, request.task) == (77, 0.9, "t")


async def test_missing_api_key_falls_through_to_next_model() -> None:
    config = LLMConfig.model_validate(
        {
            "providers": {
                "paid": {
                    "kind": "openai_compatible",
                    "base_url": "http://x",
                    "api_key_env": "NOPE_KEY",
                },
                "dev": {"kind": "dev"},
            },
            "tasks": {
                "t": {
                    "models": [
                        {"provider": "paid", "model": "m"},
                        {"provider": "dev", "model": "d"},
                    ]
                }
            },
        }
    )
    gw = LLMGateway(config, {"dev": Scripted("fine")}, env={})
    result = await gw.complete("t", MSGS)
    assert result.provider == "dev"
    assert "NOPE_KEY" in result.failed_attempts[0]


async def test_structured_output_repairs_invalid_json_once() -> None:
    a = Scripted("not json at all", '```json\n{"answer": 42}\n```')
    gw = LLMGateway(two_model_config(), {"a": a, "b": Scripted()})
    result = await gw.complete_json("t", MSGS, Answer)
    assert result.value.answer == 42
    assert len(result.calls) == 2
    assert result.cost_inr == pytest.approx(0.6)
    # The repair request shows the model its bad reply and the problem.
    repair = a.requests[1][1].messages
    assert repair[-2] == Message("assistant", "not json at all")
    assert "could not be used" in repair[-1].content
    assert a.requests[0][1].json_output is True


async def test_structured_output_moves_to_next_model_after_two_bad_replies() -> None:
    a = Scripted('{"answer": "x"}', '{"wrong": 1}')
    b = Scripted('{"answer": 7}')
    gw = LLMGateway(two_model_config(), {"a": a, "b": b})
    result = await gw.complete_json("t", MSGS, Answer)
    assert result.value.answer == 7
    assert result.final.provider == "b"
    assert len(result.calls) == 3


async def test_semantic_validator_triggers_repair() -> None:
    def must_be_even(v: Answer) -> None:
        if v.answer % 2:
            raise OutputInvalid("answer must be even")

    a = Scripted('{"answer": 3}', '{"answer": 4}')
    gw = LLMGateway(two_model_config(), {"a": a, "b": Scripted()})
    result = await gw.complete_json("t", MSGS, Answer, must_be_even)
    assert result.value.answer == 4
    assert "answer must be even" in a.requests[1][1].messages[-1].content


async def test_structured_failure_reports_billable_calls() -> None:
    gw = LLMGateway(
        two_model_config(), {"a": Scripted("x", "y"), "b": Scripted(ProviderError("down"))}
    )
    with pytest.raises(AllModelsFailed) as info:
        await gw.complete_json("t", MSGS, Answer)
    assert len(info.value.calls) == 2


def test_extract_json_handles_prose_and_fences() -> None:
    assert json.loads(extract_json('Sure! {"a": {"b": 1}} hope that helps')) == {"a": {"b": 1}}
    assert json.loads(extract_json('```\n{"a": 1}\n```')) == {"a": 1}
    with pytest.raises(ValueError):
        extract_json("no braces")


def test_config_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        LLMConfig.model_validate(
            {"providers": {}, "tasks": {"t": {"models": [{"provider": "x", "model": "m"}]}}}
        )


def test_shipped_configs_load() -> None:
    dev = load_llm_config()
    assert {"interview_turn", "grading", "grading_check"} <= set(dev.tasks)
    example = load_llm_config(LLM_DIR / "llm.example.yaml")
    kinds = {p.kind for p in example.providers.values()}
    # The example shows several vendors behind the same interface.
    assert {"openai_compatible", "anthropic"} <= kinds
    assert len({m.provider for t in example.tasks.values() for m in t.models}) >= 3


async def test_openai_compatible_adapter_wire_format() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            },
        )

    provider = OpenAICompatibleProvider(
        base_url="https://example.test/v1/",
        api_key="k",
        supports_json_mode=True,
        transport=httpx.MockTransport(handler),
    )
    resp = await provider.complete(
        "m-1", CompletionRequest(messages=MSGS, max_tokens=50, json_output=True)
    )
    assert resp.text == "hi" and resp.usage == Usage(12, 3)
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "m-1" and body["max_tokens"] == 50
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0] == {"role": "system", "content": "s"}


@pytest.mark.parametrize(("status", "retryable"), [(429, True), (503, True), (400, False)])
async def test_openai_compatible_adapter_errors(status: int, retryable: bool) -> None:
    provider = OpenAICompatibleProvider(
        base_url="https://example.test",
        api_key=None,
        transport=httpx.MockTransport(lambda r: httpx.Response(status, text="nope")),
    )
    with pytest.raises(ProviderError) as info:
        await provider.complete("m", CompletionRequest(messages=MSGS))
    assert info.value.retryable is retryable


async def test_anthropic_adapter_wire_format() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 2},
            },
        )

    provider = AnthropicProvider(api_key="k", transport=httpx.MockTransport(handler))
    msgs = [Message("system", "rules"), Message("user", "one"), Message("user", "two")]
    resp = await provider.complete("claude-x", CompletionRequest(messages=msgs))
    assert resp.text == "ab" and resp.usage == Usage(15, 2)
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["system"] == "rules"
    assert body["messages"] == [{"role": "user", "content": "one\n\ntwo"}]
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert headers["x-api-key"] == "k" and headers["anthropic-version"] == "2023-06-01"


async def test_anthropic_adapter_refusal_is_an_error() -> None:
    provider = AnthropicProvider(
        api_key="k",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"content": [], "stop_reason": "refusal"})
        ),
    )
    with pytest.raises(ProviderError, match="refused"):
        await provider.complete("m", CompletionRequest(messages=MSGS))
