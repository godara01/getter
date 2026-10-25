from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CreditPack(BaseModel):
    """A pack of paid interviews. Prices are placeholders until Sanket sets them."""

    id: str
    title: str
    credits: int = Field(ge=1)
    amount_inr: int = Field(ge=1)


DEFAULT_PACKS = [
    CreditPack(id="pack-5", title="5 practice interviews", credits=5, amount_inr=499),
    CreditPack(id="pack-15", title="15 practice interviews", credits=15, amount_inr=1199),
]


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
    # Admin access. Never self-assignable: only these settings or users.role in
    # the database grant it. Emails are honoured in dev auth only, because Clerk
    # sessions carry no verified email; use Clerk user ids there.
    admin_emails: list[str] = []
    admin_clerk_user_ids: list[str] = []
    cors_origins: list[str] = ["http://localhost:3000"]

    # Empty keeps grading in-process for local use and tests.
    redis_url: str = ""

    # Monitoring. An empty DSN keeps Sentry off; JSON logs suit the deployed server.
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0, le=1)
    log_json: bool = False

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

    # Coding section. "disabled" needs no Docker (local, CI, e2e); "docker" runs
    # candidate code in a throwaway container with no network.
    code_runner: Literal["disabled", "docker"] = "disabled"
    code_runner_image: str = "python:3.12-slim"
    code_max_runs: int = Field(default=10, ge=1)
    code_max_chars: int = Field(default=8000, ge=1)
    code_timeout_seconds: float = Field(default=5, gt=0)
    code_memory_mb: int = Field(default=128, ge=16)
    code_cpus: float = Field(default=0.5, gt=0)
    code_output_limit_bytes: int = Field(default=16384, ge=256)

    # Scripted DevOps terminal: commands allowed per question (a scenario can set fewer).
    terminal_max_commands: int = Field(default=30, ge=1)

    # Razorpay. Empty keys keep payments off: the API says so and takes no orders.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_api_url: str = "https://api.razorpay.com/v1"
    credit_packs: list[CreditPack] = DEFAULT_PACKS

    # Report-ready email. An empty key logs instead of sending.
    resend_api_key: str = ""
    mail_from: str = "Getter <reports@getter.invalid>"
    web_base_url: str = "http://localhost:3000"

    terms_version: str = "practice-terms-draft-v2"
    waitlist_requests_per_hour: int = 5

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
