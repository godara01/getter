"""Optional error tracking, request ids and JSON logs.

Everything here is inert without configuration: Sentry is only imported and
started when GETTER_SENTRY_DSN is set. Logs and events never carry candidate
answers, transcripts, report text or tokens.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import time
import traceback
import uuid
from datetime import UTC, datetime
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from getter_api.settings import Settings

REDACTED = "[redacted]"
# Keys whose values may hold candidate content, credentials or personal data.
SENSITIVE_KEYS = frozenset(
    {
        "answer",
        "answers",
        "text",
        "transcript",
        "turns",
        "quote",
        "quotes",
        "evidence",
        "summary",
        "rationale",
        "strengths",
        "learning_plan",
        "message",
        "messages",
        "prompt",
        "content",
        "email",
        "token",
        "access_token",
        "id_token",
        "authorization",
        "cookie",
        "set-cookie",
        "password",
        "secret",
        "api_key",
        "x-dev-user-email",
    }
)
# Tokens and emails that slip into free-form strings (messages, URLs, breadcrumbs).
_STRING_PATTERNS = (
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
)
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def _scrub_string(value: str) -> str:
    for pattern in _STRING_PATTERNS:
        value = pattern.sub(REDACTED, value)
    return value


def scrub(value: Any, key: str | None = None) -> Any:
    if key is not None and key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, dict):
        return {k: scrub(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return _scrub_string(value)
    return value


def scrub_event(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sentry before_send: drop request bodies, cookies and user data, redact the rest."""
    request = event.get("request")
    if isinstance(request, dict):
        for field in ("data", "cookies", "query_string"):
            request.pop(field, None)
    event.pop("user", None)
    return scrub(event)  # type: ignore[no-any-return]


def scrub_breadcrumb(crumb: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    return scrub(crumb)  # type: ignore[no-any-return]


def init_sentry(settings: Settings, component: str) -> bool:
    """Start Sentry when a DSN is set. Returns whether it started."""
    if not settings.sentry_dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=settings.sentry_traces_sample_rate,
        before_send=scrub_event,  # type: ignore[arg-type]
        before_breadcrumb=scrub_breadcrumb,
    )
    sentry_sdk.set_tag("component", component)
    return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Exceptions log their type and stack, never their message."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": _scrub_string(record.getMessage()),
        }
        request_id = request_id_var.get()
        if request_id:
            entry["request_id"] = request_id
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            entry.update(scrub(fields))
        if record.exc_info and record.exc_info[0] is not None:
            entry["exc_type"] = record.exc_info[0].__name__
            entry["stack"] = [
                f"{f.filename}:{f.lineno} in {f.name}"
                for f in traceback.extract_tb(record.exc_info[2])
            ]
        return json.dumps(entry, default=str)


def configure_logging(settings: Settings) -> None:
    """Switch the root logger to JSON lines when GETTER_LOG_JSON is on."""
    if not settings.log_json:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


class RequestIdMiddleware:
    """Tag each request with an id, return it as X-Request-Id and log one line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.access_log = logging.getLogger("getter_api.access")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            # Path only: query strings and bodies can carry personal data.
            self.access_log.info(
                "request",
                extra={
                    "fields": {
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                },
            )
            request_id_var.reset(token)
