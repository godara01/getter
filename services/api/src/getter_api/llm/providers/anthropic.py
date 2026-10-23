"""Adapter for Anthropic's Messages API."""

from __future__ import annotations

from typing import Any

import httpx

from getter_api.llm.providers.openai_compat import RETRYABLE_STATUS
from getter_api.llm.types import CompletionRequest, ProviderError, ProviderResponse, Usage

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None = None,
        timeout_seconds: float = 60.0,
        extra_headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = (base_url.rstrip("/") + "/v1/messages") if base_url else API_URL
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._headers = dict(extra_headers or {})
        self._transport = transport

    async def complete(self, model: str, request: CompletionRequest) -> ProviderResponse:
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        messages: list[dict[str, str]] = []
        for m in request.messages:
            if m.role == "system":
                continue
            # The API needs alternating turns; merge consecutive same-role ones.
            if messages and messages[-1]["role"] == m.role:
                messages[-1]["content"] += "\n\n" + m.content
            else:
                messages.append({"role": m.role, "content": m.content})
        if not messages or messages[0]["role"] != "user":
            messages.insert(0, {"role": "user", "content": "Begin."})

        body: dict[str, Any] = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": messages,
        }
        if system:
            body["system"] = system
        headers = {
            "content-type": "application/json",
            "anthropic-version": API_VERSION,
            **self._headers,
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key

        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as c:
                resp = await c.post(self._url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise ProviderError(f"network error: {exc.__class__.__name__}") from exc

        if resp.status_code != 200:
            raise ProviderError(
                f"HTTP {resp.status_code}: {resp.text[:300]}",
                retryable=resp.status_code in RETRYABLE_STATUS,
            )
        try:
            data = resp.json()
            text = "".join(
                block.get("text", "") for block in data["content"] if block.get("type") == "text"
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError(f"unexpected response shape: {resp.text[:300]}") from exc
        if data.get("stop_reason") == "refusal":
            raise ProviderError("model refused", retryable=False)
        usage = data.get("usage") or {}
        return ProviderResponse(
            text=text,
            usage=Usage(
                input_tokens=int(usage.get("input_tokens") or 0)
                + int(usage.get("cache_read_input_tokens") or 0)
                + int(usage.get("cache_creation_input_tokens") or 0),
                output_tokens=int(usage.get("output_tokens") or 0),
            ),
        )
