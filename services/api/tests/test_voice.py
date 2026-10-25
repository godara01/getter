"""Voice test kit: LiveKit tokens and the latency and cost scorecard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jwt
import pytest

from getter_api.settings import Settings
from getter_api.voice.livekit_token import VoiceNotConfiguredError, mint_token, voice_enabled
from getter_api.voice.scorecard import (
    Measurement,
    Thresholds,
    Turn,
    format_table,
    load,
    percentile,
    summarize,
)
from tests.conftest import as_user

LIVEKIT = {
    "livekit_url": "wss://example.livekit.cloud",
    "livekit_api_key": "APIkey123",
    "livekit_api_secret": "s" * 40,
}
EXAMPLE = Path(__file__).parents[3] / "docs" / "voice-test" / "example-measurement.json"


def test_token_is_a_room_scoped_signed_jwt() -> None:
    settings = Settings(environment="test", **LIVEKIT)
    token = mint_token(settings, identity="alice", room="r1", now=1_000_000)
    claims = jwt.decode(
        token, LIVEKIT["livekit_api_secret"], algorithms=["HS256"], options={"verify_exp": False}
    )
    assert claims["iss"] == "APIkey123" and claims["sub"] == "alice"
    assert claims["video"]["room"] == "r1" and claims["video"]["roomJoin"] is True
    assert claims["exp"] - claims["iat"] == 15 * 60
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(
            token,
            "wrong-secret-wrong-secret-wrong-secret",
            algorithms=["HS256"],
            options={"verify_exp": False},
        )


def test_token_needs_configuration() -> None:
    settings = Settings(environment="test")
    assert voice_enabled(settings) is False
    with pytest.raises(VoiceNotConfiguredError):
        mint_token(settings, identity="a", room="r")


async def test_admin_token_endpoint(make_client: Any) -> None:
    off = await make_client(admin_emails=["admin@example.com"])
    assert (
        await off.post("/admin/voice/token", json={}, headers=as_user("admin@example.com"))
    ).status_code == 503

    client = await make_client(admin_emails=["admin@example.com"], **LIVEKIT)
    denied = await client.post("/admin/voice/token", json={}, headers=as_user("bob@example.com"))
    assert denied.status_code == 403
    ok = await client.post(
        "/admin/voice/token", json={"room": "my room!/../x"}, headers=as_user("admin@example.com")
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["url"] == LIVEKIT["livekit_url"] and body["room"] == "myroomx"
    assert LIVEKIT["livekit_api_secret"] not in ok.text
    claims = jwt.decode(
        body["token"],
        LIVEKIT["livekit_api_secret"],
        algorithms=["HS256"],
        options={"verify_exp": False},
    )
    assert claims["video"]["room"] == "myroomx"


def test_percentile_nearest_rank() -> None:
    assert percentile([5, 1, 3, 2, 4], 50) == 3
    assert percentile([5, 1, 3, 2, 4], 95) == 5
    assert percentile([7], 95) == 7


def test_example_measurement_summary() -> None:
    summary = summarize(load(EXAMPLE))
    assert summary.turns == 3
    # Totals per turn: 1720, 1890, 2130 ms.
    assert summary.p50_ms == 1890 and summary.p95_ms == 2130
    assert summary.slowest_stage == "llm_first_token_ms"
    # STT 1.00 + LLM (3.0 + 0.6) + TTS 18.00
    assert summary.cost_breakdown["speech_to_text"] == pytest.approx(1.0)
    assert summary.cost_breakdown["llm"] == pytest.approx(3.6)
    assert summary.cost_breakdown["text_to_speech"] == pytest.approx(18.0)
    assert summary.cost_per_minute_inr == pytest.approx(22.6 / 5)
    assert summary.projected_40_min_inr == pytest.approx(180.8)
    assert summary.failures == ["median delay 1890 ms is over 1500 ms"]
    assert not summary.passed


def test_thresholds_decide_pass_and_fail() -> None:
    m = load(EXAMPLE)
    relaxed = summarize(m, Thresholds(p50_ms=2000, p95_ms=3000, max_inr_per_minute=10))
    assert relaxed.passed
    strict = summarize(m, Thresholds(p50_ms=2000, p95_ms=2000, max_inr_per_minute=2))
    assert len(strict.failures) == 2
    assert any("95th percentile" in f for f in strict.failures)
    assert any("a minute" in f for f in strict.failures)


def test_unmeasured_stages_count_as_zero_and_bad_input_is_rejected() -> None:
    assert Turn(stt_ms=100, tts_first_audio_ms=50).total_ms == 150
    data = json.loads(EXAMPLE.read_text())
    data["turns"] = []
    with pytest.raises(ValueError):
        Measurement.model_validate(data)
    data["turns"] = [{"stt_ms": -1}]
    with pytest.raises(ValueError):
        Measurement.model_validate(data)


def test_table_lists_every_setup() -> None:
    a = summarize(load(EXAMPLE))
    b = summarize(load(EXAMPLE), Thresholds(p50_ms=5000))
    table = format_table([a, b])
    assert table.count("example only") == 2
    assert "fail: median delay" in table and "pass" in table
