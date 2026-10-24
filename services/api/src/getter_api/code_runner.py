"""Runs a candidate's code against a coding question's visible tests.

The API only talks to the CodeRunner interface. GETTER_CODE_RUNNER picks the
implementation: "disabled" (default) returns a clear "not configured" result so
local runs, CI and e2e need no Docker, and "docker" runs the code in a
throwaway container (no network, read-only filesystem, non-root, memory, CPU,
process, time and output limits). Python only.

Test results come from inside the sandbox, so a candidate can forge them. They
are practice feedback and a hint for the grader; the grader judges the code it
quotes, and the verdict is never computed from test results.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from getter_api.content import CodingTask
from getter_api.settings import Settings

RunStatus = Literal["ok", "error", "timeout", "output_limit", "not_configured", "unavailable"]


@dataclass
class TestResult:
    __test__ = False  # not a pytest class

    name: str
    passed: bool
    detail: str = ""


@dataclass
class RunResult:
    status: RunStatus
    tests: list[TestResult] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    message: str = ""
    duration_ms: int = 0

    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.passed)


class CodeRunner(Protocol):
    async def run(self, task: CodingTask, code: str) -> RunResult: ...


class DisabledRunner:
    async def run(self, task: CodingTask, code: str) -> RunResult:
        return RunResult(
            status="not_configured",
            message=(
                "Running code is not configured on this server (GETTER_CODE_RUNNER=disabled). "
                "Your code is not run or recorded; explain your approach in your answer."
            ),
        )


# Runs inside the container as `python harness.py`. Last stdout line is the result.
HARNESS = r"""
import ast, json, sys, traceback

spec = json.load(open("/work/tests.json"))
sentinel = spec["sentinel"]
results = []
ns = {"__name__": "solution"}
try:
    exec(compile(open("/work/solution.py").read(), "solution.py", "exec"), ns)
except BaseException:
    print(sentinel + json.dumps({"error": traceback.format_exc(limit=3)[-1500:], "tests": []}))
    sys.exit(0)
for t in spec["tests"]:
    try:
        got = eval(t["expression"], ns)
        want = ast.literal_eval(t["expected"])
        ok = got == want
        detail = "" if ok else f"expected {want!r}, got {got!r}"
    except BaseException as exc:
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    results.append({"name": t["name"], "passed": ok, "detail": detail[:300]})
print(sentinel + json.dumps({"error": "", "tests": results}))
"""


def parse_output(stdout: str, sentinel: str) -> RunResult:
    """Split the candidate's own prints from the harness result line."""
    lines = stdout.rstrip("\n").split("\n")
    if lines and lines[-1].startswith(sentinel):
        try:
            data = json.loads(lines[-1][len(sentinel) :])
        except ValueError:
            data = None
        if isinstance(data, dict):
            tests = [
                TestResult(str(t["name"]), bool(t["passed"]), str(t.get("detail", "")))
                for t in data.get("tests", [])
            ]
            printed = "\n".join(lines[:-1])
            if data.get("error"):
                return RunResult("error", tests, printed, str(data["error"]))
            return RunResult("ok", tests, printed)
    return RunResult("error", [], stdout, "The run ended without a test result.")


class DockerRunner:
    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def docker_args(self, name: str, workdir: Path) -> list[str]:
        s = self.s
        return [
            "docker", "run", "--rm", "--name", name,
            "--network", "none",
            "--memory", f"{s.code_memory_mb}m", "--memory-swap", f"{s.code_memory_mb}m",
            "--cpus", str(s.code_cpus),
            "--pids-limit", "64",
            "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=8m",
            "--user", "65534:65534",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "-v", f"{workdir}:/work:ro",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            s.code_runner_image,
            "python", "-I", "/work/harness.py",
        ]  # fmt: skip

    async def run(self, task: CodingTask, code: str) -> RunResult:
        sentinel = "@@getter:" + secrets.token_hex(8) + ":"
        name = f"getter-run-{uuid.uuid4().hex[:12]}"
        with tempfile.TemporaryDirectory(prefix="getter-run-") as tmp:
            work = Path(tmp)
            work.chmod(0o755)  # the container user is not the owner
            files = {
                "solution.py": code,
                "harness.py": HARNESS,
                "tests.json": json.dumps(
                    {"sentinel": sentinel, "tests": [t.model_dump() for t in task.tests]}
                ),
            }
            for fname, text in files.items():
                (work / fname).write_text(text)
                (work / fname).chmod(0o644)
            return await self._run_container(name, work, sentinel)

    async def _run_container(self, name: str, work: Path, sentinel: str) -> RunResult:
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                *self.docker_args(name, work),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError:
            return RunResult("unavailable", message="Docker is not available on this server.")

        limit = self.s.code_output_limit_bytes

        cut = False

        async def read(stream: asyncio.StreamReader | None) -> bytes:
            nonlocal cut
            buf = b""
            while stream is not None:
                chunk = await stream.read(4096)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > limit:
                    # Kill at once: the other stream stays open until the process ends.
                    cut = True
                    await self._kill(name, proc)
                    return buf[:limit]
            return buf

        async def collect() -> tuple[bytes, bytes]:
            out, err = await asyncio.gather(read(proc.stdout), read(proc.stderr))
            await proc.wait()
            return out, err

        try:
            out, err = await asyncio.wait_for(collect(), self.s.code_timeout_seconds)
        except TimeoutError:
            await self._kill(name, proc)
            await proc.wait()
            ms = int((loop.time() - started) * 1000)
            return RunResult(
                "timeout",
                message=f"Stopped after {self.s.code_timeout_seconds:g} seconds.",
                duration_ms=ms,
            )
        ms = int((loop.time() - started) * 1000)
        stdout, stderr = out.decode(errors="replace"), err.decode(errors="replace")
        if cut:
            return RunResult(
                "output_limit",
                stdout=stdout,
                stderr=stderr,
                message=f"Stopped: more than {limit} bytes of output.",
                duration_ms=ms,
            )
        result = parse_output(stdout, sentinel)
        result.stderr = result.stderr or stderr
        if proc.returncode == 137 and not result.tests:
            result.message = "The program was killed, probably for using too much memory."
        if proc.returncode not in (0, None) and not result.tests and not result.message:
            result.message = stderr[-500:] or f"Exited with code {proc.returncode}."
        result.duration_ms = ms
        return result

    @staticmethod
    async def _kill(name: str, proc: asyncio.subprocess.Process) -> None:
        # Killing the docker client alone would leave the container running.
        killer = await asyncio.create_subprocess_exec(
            "docker", "kill", name,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )  # fmt: skip
        await killer.wait()
        if proc.returncode is None:
            proc.kill()


def make_runner(settings: Settings) -> CodeRunner:
    if settings.code_runner == "docker":
        return DockerRunner(settings)
    return DisabledRunner()


def format_result(result: RunResult, run_number: int, max_runs: int) -> str:
    """The text saved as the run_result turn and shown to the candidate."""
    head = f"Run {run_number} of {max_runs}."
    if result.tests:
        head += f" {result.passed} of {len(result.tests)} tests passed."
    lines = [head]
    if result.status != "ok" and result.message:
        lines.append(result.message)
    for t in result.tests:
        lines.append(
            f"- {'pass' if t.passed else 'FAIL'}: {t.name}" + (f" ({t.detail})" if t.detail else "")
        )
    if result.stdout.strip():
        lines.append("Output:\n" + result.stdout.strip()[:1000])
    if result.stderr.strip() and result.status != "ok":
        lines.append("Errors:\n" + result.stderr.strip()[-1000:])
    return "\n".join(lines)
