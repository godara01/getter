from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GETTER_", env_file=".env", extra="ignore")

    environment: Literal["local", "test", "staging", "production"] = "local"
    # Async SQLAlchemy URL. Postgres: postgresql+psycopg://user:pass@host/db
    database_url: str = "sqlite+aiosqlite:///./getter-dev.db"
    # Path to the LLM routing YAML; empty means the offline dev config.
    llm_config: str = ""
    # "dev" trusts an X-Dev-User-Email header. Only for local use and tests;
    # real sign-in (Clerk) replaces it before anything is deployed.
    auth_mode: Literal["dev"] = "dev"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Cost controls.
    free_sessions_per_day: int = Field(default=3, ge=1)
    free_account_cost_inr: float = Field(default=100, gt=0)
    free_cost_window_hours: int = Field(default=24, ge=1)
    global_daily_cost_inr: float = Field(default=300, gt=0)
    session_cost_warning_inr: float = Field(default=50, gt=0)
    max_answer_chars: int = 4000
    max_candidate_turns: int = 30
    # A second, independent grading pass; disagreements flag the report.
    grading_consistency_check: bool = True
    consistency_flag_difference: int = 2

    terms_version: str = "practice-terms-v1"

    @model_validator(mode="after")
    def _no_dev_auth_when_deployed(self) -> Settings:
        if self.auth_mode == "dev" and self.environment in ("staging", "production"):
            raise ValueError("dev auth must not run in staging or production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
