"""LLM routing config: which provider and model serves each task.

Switching a task to another vendor is a YAML change, never a code change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

ProviderKind = Literal["openai_compatible", "anthropic", "dev"]

DEFAULT_CONFIG_PATH = Path(__file__).parent / "llm.dev.yaml"


class ProviderConfig(BaseModel):
    kind: ProviderKind
    # openai_compatible covers OpenAI, OpenRouter, Google Gemini's OpenAI
    # endpoint, Groq, DeepSeek, Together, Ollama and vLLM.
    base_url: str | None = None
    api_key_env: str | None = None
    supports_json_mode: bool = False
    timeout_seconds: float = 60.0
    extra_headers: dict[str, str] = Field(default_factory=dict)


class ModelRef(BaseModel):
    provider: str
    model: str
    # List prices in US dollars per million tokens, used for cost tracking.
    input_usd_per_mtok: float = 0.0
    output_usd_per_mtok: float = 0.0


class TaskConfig(BaseModel):
    # Tried in order; later entries are fallbacks.
    models: list[ModelRef] = Field(min_length=1)
    max_tokens: int = 1024
    temperature: float = 0.2


class LLMConfig(BaseModel):
    usd_to_inr: float = 88.0
    providers: dict[str, ProviderConfig]
    tasks: dict[str, TaskConfig]

    @model_validator(mode="after")
    def _models_reference_known_providers(self) -> LLMConfig:
        for task_name, task in self.tasks.items():
            for ref in task.models:
                if ref.provider not in self.providers:
                    raise ValueError(f"task {task_name!r} uses unknown provider {ref.provider!r}")
        return self

    def task(self, name: str) -> TaskConfig:
        try:
            return self.tasks[name]
        except KeyError:
            raise KeyError(f"no LLM task named {name!r} in config") from None


def load_llm_config(path: str | Path | None = None) -> LLMConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open() as f:
        data = yaml.safe_load(f)
    return LLMConfig.model_validate(data)
