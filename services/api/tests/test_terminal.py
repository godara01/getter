"""The scripted DevOps terminal: simulator rules, limits, saved turns and evidence."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from getter_api.content import library
from getter_api.interview.grading import grading_request
from getter_api.llm.config import load_llm_config
from getter_api.llm.gateway import LLMGateway
from getter_api.llm.providers.dev import DevProvider, _block
from getter_api.llm.types import CompletionRequest, ProviderResponse
from getter_api.terminal import CommandRejected, replay, respond
from tests.conftest import FakeClock
from tests.test_interview_api import ALICE, BOB, LONG_ANSWER, answer, start

DEVOPS = "devops-junior-mid"


def task(question_id: str) -> Any:
    for section in library().templates[DEVOPS].sections:
        for q in section.questions:
            if q.id == question_id:
                assert q.terminal is not None
                return q.terminal
    raise KeyError(question_id)


def out(question_id: str, command: str, flags: frozenset[str] = frozenset()) -> str:
    return respond(task(question_id), flags, command).output


# -- simulator -------------------------------------------------------------


def test_rules_match_the_whole_command_with_spaces_collapsed() -> None:
    assert "LISTEN" in out("port_443", "  ss   -tlnp ")
    assert "LISTEN" not in out("port_443", "ss -tlnp extra-words")
    assert "(no output" in out("port_443", "ss -tlnp extra-words")


def test_sudo_prefix_is_ignored() -> None:
    assert out("port_443", "sudo ufw status") == out("port_443", "ufw status")


def test_pipes_filter_the_first_command_output() -> None:
    assert out("port_443", "ss -tlnp | grep 443").count("\n") == 0
    assert "0.0.0.0:443" in out("port_443", "ss -tlnp | grep 443")
    assert out("port_443", "ss -tlnp | wc -l") == "4"
    assert out("port_443", "ss -tlnp | grep -v LISTEN | head -n 5").startswith("State")
    assert "not supported after a pipe" in out("port_443", "ss -tlnp | awk '{print $1}'")
    assert "syntax error" in out("port_443", "ss -tlnp |")


def test_unknown_program_versus_known_program_without_script() -> None:
    assert out("port_443", "frobnicate --now") == "bash: frobnicate: command not found"
    assert "nothing scripted" in out("port_443", "ls -la")


def test_help_explains_the_simulation() -> None:
    assert "simulated terminal" in out("port_443", "help")


def test_flags_change_later_output_and_are_rebuilt_from_history() -> None:
    t = task("port_443")
    before = respond(t, frozenset(), "nc -vz web-01 443").output
    assert "timed out" in before
    history = ["ufw status", "ufw allow 443/tcp"]
    flags = replay(t, history)
    assert flags == {"ufw_443_open"}
    assert "succeeded" in respond(t, flags, "nc -vz web-01 443").output
    assert "443/tcp" in respond(t, flags, "ufw status").output


def test_rejected_commands() -> None:
    t = task("port_443")
    for bad in ("", "   ", "ls\nrm -rf /", "x" * 201):
        with pytest.raises(CommandRejected):
            respond(t, frozenset(), bad)


def test_every_scenario_can_reach_its_fix() -> None:
    """The scripted walk-throughs the questions are written around."""
    port = task("port_443")
    flags = replay(port, ["ufw allow 443"])
    assert "succeeded" in respond(port, flags, "nc -zv web-01 443").output

    disk = task("disk_full")
    assert "100%" in out("disk_full", "df -h")
    assert "(deleted)" in out("disk_full", "lsof +L1")
    flags = replay(disk, ["kill -HUP 2210"])
    assert "38%" in respond(disk, flags, "df -h").output

    assert "missing required environment variable" in out(
        "container_restarting", "docker logs payments-api"
    )


# -- content ---------------------------------------------------------------


def test_devops_template_has_terminal_scenarios() -> None:
    template = library().templates[DEVOPS]
    ids = [q.id for s in template.sections for q in s.questions if q.terminal]
    assert ids == ["port_443", "disk_full", "container_restarting"]


def test_question_cannot_have_both_code_and_terminal() -> None:
    from getter_api.content import Question

    with pytest.raises(ValueError, match="either coding or terminal"):
        Question.model_validate(
            {
                "id": "q",
                "prompt": "p",
                "coding": {
                    "starter_code": "x",
                    "tests": [{"name": "t", "expression": "1", "expected": "1"}],
                },
                "terminal": {"hostname": "h", "rules": [{"pattern": "ls"}]},
            }
        )


def test_bad_terminal_pattern_is_rejected() -> None:
    from getter_api.content import Question

    with pytest.raises(ValueError, match="bad terminal pattern"):
        Question.model_validate(
            {"id": "q", "prompt": "p", "terminal": {"hostname": "h", "rules": [{"pattern": "("}]}}
        )


# -- API -------------------------------------------------------------------


async def to_terminal(client: httpx.AsyncClient) -> dict[str, Any]:
    session = await start(client, DEVOPS, "junior")
    assert session["terminal"] is None
    while session["terminal"] is None:
        session = await answer(client, session["id"], LONG_ANSWER)
    return session


async def cmd(client: httpx.AsyncClient, sid: str, command: str, headers: Any = ALICE) -> Any:
    body = {"command": command}
    return await client.post(f"/sessions/{sid}/terminal", json=body, headers=headers)


async def test_terminal_is_offered_only_on_scenario_questions(make_client: Any) -> None:
    client = await make_client()
    session = await to_terminal(client)
    terminal = session["terminal"]
    assert terminal["question_id"] == "port_443"
    assert (terminal["hostname"], terminal["commands_used"], terminal["max_commands"]) == (
        "web-01",
        0,
        30,
    )


async def test_command_and_output_are_saved_as_turns(make_client: Any) -> None:
    client = await make_client()
    session = await to_terminal(client)
    resp = await cmd(client, session["id"], "ss -tlnp | grep 443")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "0.0.0.0:443" in body["output"]
    command_turn, output_turn = body["session"]["turns"][-2:]
    assert (command_turn["speaker"], command_turn["kind"], command_turn["text"]) == (
        "candidate",
        "command",
        "ss -tlnp | grep 443",
    )
    assert (output_turn["speaker"], output_turn["kind"]) == ("interviewer", "command_output")
    assert command_turn["question_id"] == "port_443"
    assert body["session"]["terminal"]["commands_used"] == 1
    # Commands are not answers: the interview has not advanced.
    assert body["session"]["progress"]["section_number"] == session["progress"]["section_number"]


async def test_scenario_state_carries_across_commands(make_client: Any) -> None:
    client = await make_client()
    sid = (await to_terminal(client))["id"]
    assert "timed out" in (await cmd(client, sid, "nc -vz web-01 443")).json()["output"]
    await cmd(client, sid, "sudo ufw allow 443/tcp")
    assert "succeeded" in (await cmd(client, sid, "nc -vz web-01 443")).json()["output"]


async def test_command_budget_is_enforced_in_the_api(make_client: Any) -> None:
    client = await make_client(terminal_max_commands=2)
    sid = (await to_terminal(client))["id"]
    assert (await cmd(client, sid, "ufw status")).status_code == 200
    assert (await cmd(client, sid, "ufw status")).status_code == 200
    resp = await cmd(client, sid, "ufw status")
    assert resp.status_code == 429
    assert "all 2 commands" in resp.json()["detail"]


async def test_budget_is_per_question(make_client: Any) -> None:
    client = await make_client(terminal_max_commands=1)
    session = await to_terminal(client)
    sid = session["id"]
    assert (await cmd(client, sid, "ufw status")).status_code == 200
    session = await answer(client, sid, LONG_ANSWER)
    while session["terminal"] and session["terminal"]["question_id"] == "port_443":
        session = await answer(client, sid, LONG_ANSWER)
    assert session["terminal"]["question_id"] == "disk_full"
    assert session["terminal"]["commands_used"] == 0
    assert (await cmd(client, sid, "df -h")).status_code == 200


async def test_rejects_bad_commands_and_non_terminal_questions(make_client: Any) -> None:
    client = await make_client()
    session = await start(client, DEVOPS, "junior")
    resp = await cmd(client, session["id"], "ls")
    assert resp.status_code == 422 and "no terminal" in resp.json()["detail"]
    session = await to_terminal(client)
    assert (await cmd(client, session["id"], "a\nb")).status_code == 422
    assert (await cmd(client, session["id"], "x" * 201)).status_code == 422
    assert (await cmd(client, session["id"], "   ")).status_code == 422


async def test_terminal_respects_section_time_and_ownership(
    make_client: Any, clock: FakeClock
) -> None:
    client = await make_client()
    sid = (await to_terminal(client))["id"]
    assert (await cmd(client, sid, "ufw status", BOB)).status_code == 404
    clock.advance(minutes=30)
    resp = await cmd(client, sid, "ufw status")
    assert resp.status_code == 422 and "time is up" in resp.json()["detail"]


async def test_terminal_unavailable_after_the_interview_ends(make_client: Any) -> None:
    client = await make_client()
    sid = (await to_terminal(client))["id"]
    await client.post(f"/sessions/{sid}/end", headers=ALICE)
    assert (await cmd(client, sid, "ufw status")).status_code == 409


class CommandQuoter(DevProvider):
    """A fake grader that quotes a turn of the given kind, to test what counts as evidence."""

    def __init__(self, kind: str) -> None:
        self.kind = kind

    async def complete(self, model: str, request: CompletionRequest) -> ProviderResponse:
        if not request.task.startswith("grading"):
            return await super().complete(model, request)
        prompt = "\n".join(m.content for m in request.messages if m.role == "user")
        transcript = _block(prompt, "transcript_json")
        rubric = _block(prompt, "rubric_json")
        turn = next(t for t in transcript if t["kind"] == self.kind)
        skills = [
            {
                "skill_id": s["skill_id"],
                "score": 3,
                "evidence": [{"turn": turn["turn"], "quote": turn["text"][:40]}],
                "rationale": "quotes the terminal",
            }
            for s in rubric["skills"]
        ]
        reply = {"summary": "x", "strengths": [], "skills": skills, "gaps": []}
        return ProviderResponse(json.dumps(reply))


async def finished_with_commands(client: httpx.AsyncClient) -> str:
    sid = (await to_terminal(client))["id"]
    await cmd(client, sid, "ss -tlnp | grep 443")
    resp = await client.post(f"/sessions/{sid}/end", headers=ALICE)
    assert resp.json()["status"] == "grading"
    return str(sid)


async def test_grader_can_quote_commands(make_client: Any) -> None:
    gateway = LLMGateway(load_llm_config(), {"dev": CommandQuoter("command")})
    client = await make_client()
    client._transport.app.state.grader.gateway = gateway  # type: ignore[attr-defined]
    sid = await finished_with_commands(client)
    resp = await client.get(f"/sessions/{sid}/report", headers=ALICE)
    assert resp.status_code == 200, resp.text
    quote = resp.json()["skills"][0]["evidence"][0]
    turns = (await client.get(f"/sessions/{sid}", headers=ALICE)).json()["turns"]
    cited = next(t for t in turns if t["index"] == quote["turn"])
    assert cited["kind"] == "command"


async def test_terminal_output_is_not_evidence(make_client: Any) -> None:
    gateway = LLMGateway(load_llm_config(), {"dev": CommandQuoter("command_output")})
    client = await make_client()
    client._transport.app.state.grader.gateway = gateway  # type: ignore[attr-defined]
    sid = await finished_with_commands(client)
    assert (await client.get(f"/sessions/{sid}/report", headers=ALICE)).status_code == 409


def test_grader_prompt_explains_terminal_turns() -> None:
    lib = library()
    template = lib.templates[DEVOPS]
    rubric = lib.rubric_for(template)

    class T:
        def __init__(self, index: int, speaker: str, kind: str, text: str) -> None:
            self.index, self.speaker, self.kind, self.text = index, speaker, kind, text
            self.section_id = "linux"

    turns = [T(0, "candidate", "command", "ss -tlnp"), T(1, "interviewer", "command_output", "x")]
    messages, _ = grading_request(template, rubric, "junior", turns)
    assert "command_output" in messages[0].content
    assert '"kind": "command"' in messages[-1].content
