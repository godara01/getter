"""Adapter for the OpenAI chat completions wire format.

Many vendors speak it (OpenAI, OpenRouter, Google Gemini's compatibility
endpoint, Groq, DeepSeek, Together, Ollama, vLLM), so one adapter covers them.
"""

from __future__ import annotations

from typing import Any

import httpx

from getter_api.llm.types import CompletionRequest, ProviderError, ProviderResponse, Usage

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        supports_json_mode: bool = False,
        timeout_seconds: float = 60.0,
        extra_headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._json_mode = supports_json_mode
        self._timeout = timeout_seconds
        self._headers = dict(extra_headers or {})
        self._transport = transport

    async def complete(self, model: str, request: CompletionRequest) -> ProviderResponse:
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.json_output and self._json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"content-type": "application/json", **self._headers}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"

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
            text = data["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"unexpected response shape: {resp.text[:300]}") from exc
        usage = data.get("usage") or {}
        return ProviderResponse(
            text=text,
            usage=Usage(
                input_tokens=int(usage.get("prompt_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or 0),
            ),
        )
