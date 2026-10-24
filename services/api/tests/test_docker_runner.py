"""The Docker runner: limits handled with a stub `docker` binary, plus a real run if possible."""

from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from getter_api.code_runner import DisabledRunner, DockerRunner, make_runner, parse_output
from getter_api.content import CodingTask, CodingTest
from getter_api.settings import Settings

TASK = CodingTask(
    starter_code="",
    tests=[
        CodingTest(name="adds", expression="add(1, 2)", expected="3"),
        CodingTest(name="adds negatives", expression="add(-1, -2)", expected="-3"),
        CodingTest(name="wrong on purpose", expression="add(2, 2)", expected="5"),
    ],
)
GOOD = "print('hello')\ndef add(a, b):\n    return a + b\n"

STUB = """#!/usr/bin/env python3
import json, sys, time
args = sys.argv[1:]
with open(sys.argv[0] + ".log", "a") as log:
    log.write(" ".join(args[:2]) + "\\n")
if args[0] == "kill":
    sys.exit(0)
mode = open(sys.argv[0] + ".mode").read().strip()
work = args[args.index("-v") + 1].split(":")[0]
sentinel = json.load(open(work + "/tests.json"))["sentinel"]
if mode == "hang":
    time.sleep(30)
elif mode == "flood":
    sys.stdout.write("x" * 100000)
    sys.stdout.flush()
    time.sleep(30)
elif mode == "ok":
    print("hello")
    tests = [{"name": "adds", "passed": True, "detail": ""},
             {"name": "wrong on purpose", "passed": False, "detail": "expected 5, got 4"}]
    print(sentinel + json.dumps({"error": "", "tests": tests}))
elif mode == "oom":
    sys.exit(137)
"""


@pytest.fixture
def fake_docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    stub = tmp_path / "docker"
    stub.write_text(STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    return stub


def set_mode(stub: Path, mode: str) -> None:
    Path(f"{stub}.mode").write_text(mode)


def runner(**overrides: object) -> DockerRunner:
    return DockerRunner(Settings(environment="test", code_runner="docker", **overrides))  # type: ignore[arg-type]


def test_default_is_disabled_and_docker_is_opt_in() -> None:
    assert isinstance(make_runner(Settings(environment="test")), DisabledRunner)
    assert isinstance(make_runner(Settings(environment="test", code_runner="docker")), DockerRunner)


def test_container_is_locked_down(tmp_path: Path) -> None:
    args = runner(code_memory_mb=64, code_cpus=0.25).docker_args("n", tmp_path)
    joined = " ".join(args)
    for flag in ("--network none", "--read-only", "--user 65534:65534", "--cap-drop ALL"):
        assert flag in joined
    assert "no-new-privileges" in joined and "--pids-limit" in joined
    assert "--memory 64m" in joined and "--memory-swap 64m" in joined and "--cpus 0.25" in joined
    assert f"{tmp_path}:/work:ro" in joined


def test_parse_output_separates_prints_from_result() -> None:
    out = 'hi\n@@s:{"error": "", "tests": [{"name": "a", "passed": true}]}\n'
    result = parse_output(out, "@@s:")
    assert (result.status, result.stdout, result.passed) == ("ok", "hi", 1)
    assert parse_output("hi\n", "@@s:").status == "error"
    assert parse_output("@@s:not json", "@@s:").status == "error"
    crashed = parse_output('@@s:{"error": "Traceback", "tests": []}', "@@s:")
    assert (crashed.status, crashed.stderr) == ("error", "Traceback")


async def test_ok_run(fake_docker: Path) -> None:
    set_mode(fake_docker, "ok")
    result = await runner().run(TASK, GOOD)
    assert result.status == "ok"
    assert result.stdout == "hello"
    assert [(t.name, t.passed) for t in result.tests] == [
        ("adds", True),
        ("wrong on purpose", False),
    ]


async def test_time_limit_kills_the_container(fake_docker: Path) -> None:
    set_mode(fake_docker, "hang")
    result = await runner(code_timeout_seconds=0.5).run(TASK, "while True: pass")
    assert result.status == "timeout"
    assert "0.5 seconds" in result.message
    assert "kill getter-run-" in Path(f"{fake_docker}.log").read_text()


async def test_output_limit_kills_the_container(fake_docker: Path) -> None:
    set_mode(fake_docker, "flood")
    result = await runner(code_output_limit_bytes=1024).run(TASK, "print('x' * 10**9)")
    assert result.status == "output_limit"
    assert len(result.stdout) == 1024
    assert "kill getter-run-" in Path(f"{fake_docker}.log").read_text()


async def test_memory_kill_is_explained(fake_docker: Path) -> None:
    set_mode(fake_docker, "oom")
    result = await runner().run(TASK, "x = bytearray(10**10)")
    assert result.status == "error"
    assert "memory" in result.message


async def test_missing_docker_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    result = await runner().run(TASK, GOOD)
    assert result.status == "unavailable"


def docker_ready() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        image = Settings().code_runner_image
        done = subprocess.run(
            ["docker", "image", "inspect", image], capture_output=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


needs_docker = pytest.mark.skipif(
    not docker_ready(), reason="Docker or the runner image (python:3.12-slim) is not available"
)


@needs_docker
async def test_real_container_runs_tests_and_enforces_limits() -> None:
    r = runner(code_timeout_seconds=10)
    result = await r.run(TASK, GOOD)
    assert result.status == "ok", result
    assert [t.passed for t in result.tests] == [True, True, False]

    assert (await r.run(TASK, "def add(:\n")).status == "error"

    loop = await runner(code_timeout_seconds=2).run(TASK, "while True: pass")
    assert loop.status == "timeout"

    flood = await r.run(TASK, "import sys\nwhile True: sys.stdout.write('x' * 4096)")
    assert flood.status in ("output_limit", "timeout")

    probe = (
        "import socket, os\n"
        "def add(a, b):\n"
        "    try:\n"
        "        socket.create_connection(('1.1.1.1', 80), timeout=2)\n"
        "        net = 'network'\n"
        "    except OSError:\n"
        "        net = 'blocked'\n"
        "    try:\n"
        "        open('/work/x', 'w')\n"
        "        fs = 'writable'\n"
        "    except OSError:\n"
        "        fs = 'readonly'\n"
        "    print(net, fs, os.getuid())\n"
        "    return a + b\n"
    )
    isolated = await r.run(TASK, probe)
    assert "blocked readonly 65534" in isolated.stdout
