from __future__ import annotations

import json
import logging
import subprocess
import sys
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from getter_api.monitoring import (
    REDACTED,
    JsonFormatter,
    init_sentry,
    request_id_var,
    scrub_event,
)
from getter_api.settings import Settings
from tests.conftest import as_user

ANSWER = "I would shard the orders table by customer because of hot partitions"
JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyXzEyMyJ9.c2lnbmF0dXJlYnl0ZXM"


def test_nothing_starts_without_a_dsn() -> None:
    assert init_sentry(Settings(environment="test"), "api") is False
    # The SDK is not even imported, so the default install pays nothing at runtime.
    code = (
        "import sys; from getter_api.monitoring import init_sentry; "
        "from getter_api.settings import Settings; "
        "init_sentry(Settings(environment='test'), 'api'); "
        "assert 'sentry_sdk' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_sentry_starts_with_a_dsn_and_no_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    import sentry_sdk

    seen: dict[str, Any] = {}
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: seen.update(kw))
    monkeypatch.setattr(sentry_sdk, "set_tag", lambda *a: None)
    settings = Settings(environment="test", sentry_dsn="https://key@example.invalid/1")
    assert init_sentry(settings, "worker") is True
    assert seen["send_default_pii"] is False
    assert seen["include_local_variables"] is False
    assert seen["max_request_body_size"] == "never"
    assert seen["before_send"] is scrub_event


def test_scrub_event_removes_answers_transcripts_and_tokens() -> None:
    event = {
        "message": f"failed on {ANSWER}",
        "request": {
            "url": "http://test/sessions/1/answer",
            "query_string": "email=a@b.co",
            "data": {"text": ANSWER},
            "cookies": {"sid": "abc"},
            "headers": {
                "Authorization": f"Bearer {JWT}",
                "x-dev-user-email": "a@b.co",
                "user-agent": "pytest",
            },
        },
        "user": {"email": "a@b.co", "ip_address": "1.2.3.4"},
        "extra": {
            "transcript": [{"speaker": "candidate", "text": ANSWER}],
            "turns": [ANSWER],
            "note": f"token {JWT} for a@b.co",
            "attempt": 2,
        },
    }
    out = json.dumps(scrub_event(event))
    assert ANSWER not in out.replace("failed on " + ANSWER, "")
    assert JWT not in out
    assert "a@b.co" not in out
    assert "1.2.3.4" not in out
    assert "sid" not in out
    scrubbed = scrub_event(event)
    assert scrubbed["extra"]["transcript"] == REDACTED
    assert scrubbed["extra"]["attempt"] == 2
    assert scrubbed["request"]["headers"]["user-agent"] == "pytest"


def test_json_formatter_never_logs_exception_text_or_tokens() -> None:
    try:
        raise ValueError(ANSWER)
    except ValueError:
        record = logging.LogRecord(
            "x", logging.ERROR, __file__, 1, f"grading failed {JWT}", None, sys.exc_info()
        )
    token = request_id_var.set("req-12345678")
    try:
        line = JsonFormatter().format(record)
    finally:
        request_id_var.reset(token)
    data = json.loads(line)
    assert data["exc_type"] == "ValueError"
    assert data["request_id"] == "req-12345678"
    assert ANSWER not in line
    assert JWT not in line


async def test_request_id_header_and_logs_without_answer_text(
    make_client: Callable[..., httpx.AsyncClient], caplog: pytest.LogCaptureFixture
) -> None:
    client = await make_client()
    caplog.set_level(logging.INFO, logger="getter_api.access")
    # Format at emit time, as a real handler does, while the request id is still set.
    caplog.handler.setFormatter(JsonFormatter())
    headers = as_user("cand@example.com")
    templates = (await client.get("/templates")).json()
    created = await client.post(
        "/sessions",
        json={"template_id": templates[0]["id"], "level": "junior", "accept_terms": True},
        headers=headers,
    )
    session_id = created.json()["id"]
    sent = await client.post(
        f"/sessions/{session_id}/answers?email=cand@example.com",
        json={"text": ANSWER},
        headers={**headers, "x-request-id": "trace-abcdef12"},
    )
    assert sent.headers["x-request-id"] == "trace-abcdef12"
    generated = (await client.get("/health", headers={"x-request-id": "bad id!"})).headers
    assert generated["x-request-id"] not in ("bad id!", "")

    line = caplog.text
    assert "getter_api.access" in line
    assert ANSWER not in line
    assert "cand@example.com" not in line
    assert '"request_id": "trace-abcdef12"' in line
