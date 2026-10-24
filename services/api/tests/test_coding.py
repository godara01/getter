"""The coding section: run limits, snapshot turns and evidence, with a fake runner."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from getter_api.code_runner import RunResult, TestResult
from getter_api.content import CodingTask, library
from getter_api.interview.grading import grading_request, quote_in_text
from getter_api.llm.config import load_llm_config
from getter_api.llm.gateway import LLMGateway
from getter_api.llm.providers.dev import DevProvider, _block
from getter_api.llm.types import CompletionRequest, ProviderResponse
from tests.conftest import FakeClock, as_user
from tests.test_interview_api import ALICE, BOB, LONG_ANSWER, answer, start

CODE = (
    "def latest_per_user(events):\n    out = {}\n"
    "    for u, t, v in events:\n        out[u] = v\n    return out\n"
)


class FakeRunner:
    def __init__(self, result: RunResult | None = None) -> None:
        self.result = result or RunResult(
            "ok", [TestResult("empty list", True), TestResult("two users", False, "expected 1")]
        )
        self.calls: list[str] = []

    async def run(self, task: CodingTask, code: str) -> RunResult:
        self.calls.append(code)
        return self.result


async def coding_client(make_client: Any, runner: Any = None, **overrides: Any) -> Any:
    overrides.setdefault("code_runner", "docker")  # enabled; the fake replaces the real runner
    client = await make_client(**overrides)
    client._transport.app.state.runner = runner or FakeRunner()  # type: ignore[attr-defined]
    return client


async def to_coding(client: httpx.AsyncClient) -> dict[str, Any]:
    session = await start(client)
    for _ in range(5):  # one answer for each earlier question
        session = await answer(client, session["id"], LONG_ANSWER)
    assert session["progress"]["section_title"] == "Coding task"
    return session


async def run(client: httpx.AsyncClient, sid: str, code: str = CODE, headers: Any = ALICE) -> Any:
    return await client.post(f"/sessions/{sid}/runs", json={"code": code}, headers=headers)


async def test_coding_task_is_only_offered_on_the_coding_question(make_client: Any) -> None:
    client = await coding_client(make_client)
    session = await start(client)
    assert session["coding"] is None
    session = await to_coding(client)
    coding = session["coding"]
    assert "def latest_per_user" in coding["starter_code"]
    assert coding["test_names"][0] == "empty list"
    assert coding["runner_enabled"] is True
    assert (coding["max_runs"], coding["runs_used"]) == (10, 0)


async def test_run_saves_snapshot_and_result_as_turns(make_client: Any) -> None:
    runner = FakeRunner()
    client = await coding_client(make_client, runner)
    session = await to_coding(client)
    resp = await run(client, session["id"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["result"]["status"] == "ok"
    assert [t["passed"] for t in body["result"]["tests"]] == [True, False]
    code_turn, result_turn = body["session"]["turns"][-2:]
    assert (code_turn["speaker"], code_turn["kind"], code_turn["text"]) == (
        "candidate",
        "code",
        CODE,
    )
    assert (result_turn["speaker"], result_turn["kind"]) == ("interviewer", "run_result")
    assert "1 of 2 tests passed" in result_turn["text"]
    assert "FAIL: two users (expected 1)" in result_turn["text"]
    assert body["session"]["coding"]["runs_used"] == 1
    assert runner.calls == [CODE]


@pytest.mark.parametrize("status", ["timeout", "output_limit"])
async def test_runner_limit_results_are_recorded_and_use_a_run(
    make_client: Any, status: str
) -> None:
    result = RunResult(status, message=f"limit hit: {status}")  # type: ignore[arg-type]
    client = await coding_client(make_client, FakeRunner(result))
    session = await to_coding(client)
    body = (await run(client, session["id"])).json()
    assert body["result"]["status"] == status
    assert f"limit hit: {status}" in body["session"]["turns"][-1]["text"]
    assert body["session"]["coding"]["runs_used"] == 1


async def test_disabled_runner_says_so_and_records_nothing(make_client: Any) -> None:
    client = await make_client()  # default settings: runner disabled
    session = await to_coding(client)
    assert session["coding"]["runner_enabled"] is False
    resp = await run(client, session["id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["status"] == "not_configured"
    assert "not configured" in body["result"]["message"]
    assert len(body["session"]["turns"]) == len(session["turns"])
    assert body["session"]["coding"]["runs_used"] == 0


async def test_run_count_limit_is_enforced(make_client: Any) -> None:
    runner = FakeRunner()
    client = await coding_client(make_client, runner, code_max_runs=2)
    session = await to_coding(client)
    for _ in range(2):
        assert (await run(client, session["id"])).status_code == 200
    resp = await run(client, session["id"])
    assert resp.status_code == 429
    assert "used all 2 runs" in resp.json()["detail"]
    assert len(runner.calls) == 2


async def test_section_time_limit_stops_runs(make_client: Any, clock: FakeClock) -> None:
    runner = FakeRunner()
    client = await coding_client(make_client, runner)
    session = await to_coding(client)
    assert (await run(client, session["id"])).status_code == 200
    clock.advance(minutes=13)
    resp = await run(client, session["id"])
    assert resp.status_code == 422
    assert "time is up" in resp.json()["detail"]
    assert len(runner.calls) == 1


async def test_run_is_refused_outside_the_coding_question(make_client: Any) -> None:
    runner = FakeRunner()
    client = await coding_client(make_client, runner)
    session = await start(client)
    resp = await run(client, session["id"])
    assert resp.status_code == 422
    assert "no code to run" in resp.json()["detail"]
    assert runner.calls == []


async def test_run_input_and_ownership_checks(make_client: Any) -> None:
    runner = FakeRunner()
    client = await coding_client(make_client, runner, code_max_chars=100)
    session = await to_coding(client)
    assert (await run(client, session["id"], "x = 1\n" * 50)).status_code == 422
    assert (await run(client, session["id"], "   \n")).status_code == 422
    assert (await run(client, session["id"], headers=BOB)).status_code == 404
    assert (
        await run(client, session["id"], headers=as_user("nobody@example.com"))
    ).status_code == 404
    assert runner.calls == []
    await client.post(f"/sessions/{session['id']}/end", headers=ALICE)
    assert (await run(client, session["id"], "x = 1")).status_code == 409


async def test_code_snapshots_do_not_use_up_the_answer_limit(make_client: Any) -> None:
    client = await coding_client(make_client, max_candidate_turns=7)
    session = await to_coding(client)
    for _ in range(3):
        await run(client, session["id"])
    # Six answers so far: a short one still gets its follow-up instead of an early end.
    session = await answer(client, session["id"], "ok")
    assert session["status"] == "in_progress"
    assert session["turns"][-1]["kind"] == "follow_up"


class CodeQuoter(DevProvider):
    """A grader that quotes `quote_kind` turns, to test what counts as evidence."""

    def __init__(self, quote_kind: str) -> None:
        self.quote_kind = quote_kind

    async def complete(self, model: str, request: CompletionRequest) -> ProviderResponse:
        if not request.task.startswith("grading"):
            return await super().complete(model, request)
        prompt = "\n".join(m.content for m in request.messages if m.role == "user")
        transcript = _block(prompt, "transcript_json")
        rubric = _block(prompt, "rubric_json")
        turn = next(t for t in transcript if t["kind"] == self.quote_kind)
        quote = "def latest_per_user(events):\n    out = {}"  # multi-line, verbatim
        skills = [
            {
                "skill_id": s["skill_id"],
                "score": 3,
                "evidence": [{"turn": turn["turn"], "quote": quote}],
                "rationale": "quotes the submitted code",
            }
            for s in rubric["skills"]
        ]
        reply = {"summary": "x", "strengths": [], "skills": skills, "gaps": []}
        return ProviderResponse(json.dumps(reply))


async def finish_with_code(client: httpx.AsyncClient) -> str:
    session = await to_coding(client)
    await run(client, session["id"])
    session = await answer(client, session["id"], LONG_ANSWER)
    assert session["status"] == "grading"
    return str(session["id"])


async def test_grader_can_quote_code_snapshots_verbatim(make_client: Any) -> None:
    gateway = LLMGateway(load_llm_config(), {"dev": CodeQuoter("code")})
    client = await coding_client(make_client)
    client._transport.app.state.engine.gateway = gateway  # type: ignore[attr-defined]
    app = client._transport.app  # type: ignore[attr-defined]
    app.state.grader.gateway = gateway
    sid = await finish_with_code(client)
    resp = await client.get(f"/sessions/{sid}/report", headers=ALICE)
    assert resp.status_code == 200, resp.text
    quote = resp.json()["skills"][0]["evidence"][0]
    turns = (await client.get(f"/sessions/{sid}", headers=ALICE)).json()["turns"]
    cited = next(t for t in turns if t["index"] == quote["turn"])
    assert cited["kind"] == "code"
    assert quote["quote"] in cited["text"]


async def test_run_results_are_not_evidence(make_client: Any) -> None:
    gateway = LLMGateway(load_llm_config(), {"dev": CodeQuoter("run_result")})
    client = await coding_client(make_client)
    app = client._transport.app  # type: ignore[attr-defined]
    app.state.grader.gateway = gateway
    sid = await finish_with_code(client)
    resp = await client.get(f"/sessions/{sid}/report", headers=ALICE)
    assert resp.status_code == 409  # grading failed: no score from a runner turn


def test_grading_request_marks_turn_kinds_and_accepts_code_quotes() -> None:
    lib = library()
    template = lib.templates["backend-junior-mid"]
    rubric = lib.rubric_for(template)

    class T:
        def __init__(self, index: int, speaker: str, kind: str, text: str) -> None:
            self.index, self.speaker, self.kind, self.text = index, speaker, kind, text
            self.section_id = "coding"

    turns = [T(0, "interviewer", "intro", "hi"), T(1, "candidate", "code", CODE)]
    messages, validate = grading_request(template, rubric, "mid", turns)
    assert '"kind": "code"' in messages[-1].content
    assert '"kind": "intro"' not in messages[-1].content
    assert "verbatim" in messages[0].content and "run_result" in messages[0].content
    # Indentation and line breaks may differ from what the model copies back.
    assert quote_in_text("for u, t, v in events: out[u] = v", CODE)
    assert not quote_in_text("return sorted(events)", CODE)
