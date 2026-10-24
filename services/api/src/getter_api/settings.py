from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
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
    auth_mode: Literal["dev", "clerk"] = "dev"
    clerk_issuer: str = ""
    clerk_jwks_url: str = ""
    clerk_authorized_parties: list[str] = []
    cors_origins: list[str] = ["http://localhost:3000"]

    # Empty keeps grading in-process for local use and tests.
    redis_url: str = ""

    # Cost controls.
    free_sessions_per_day: int = 3
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
        if self.auth_mode == "clerk" and not (
            self.clerk_issuer and self.clerk_jwks_url and self.clerk_authorized_parties
        ):
            raise ValueError("Clerk issuer, JWKS URL and authorized parties are required")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
