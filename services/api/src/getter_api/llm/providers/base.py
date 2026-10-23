from __future__ import annotations

from typing import Protocol

from getter_api.llm.types import CompletionRequest, ProviderResponse


class Provider(Protocol):
    """One vendor API. Implementations translate our neutral types to theirs."""

    async def complete(self, model: str, request: CompletionRequest) -> ProviderResponse: ...
