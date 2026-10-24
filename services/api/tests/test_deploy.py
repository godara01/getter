from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


async def test_readiness_checks_database(make_client):
    client = await make_client()
    assert (await client.get("/health/ready")).json() == {"status": "ok"}
    client._transport.app.state.sessionmaker = Mock(
        side_effect=RuntimeError("private connection URL")
    )
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
    assert (await client.get("/health")).status_code == 200
    await client.aclose()


@pytest.mark.parametrize("job", ["server", "web"])
def test_deploy_steps_skip_cleanly_without_secrets(tmp_path, job):
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy.yml").read_text())
    guard = next(step for step in workflow["jobs"][job]["steps"] if step.get("id") == "configured")
    output = tmp_path / "output"
    result = subprocess.run(
        ["bash", "-c", guard["run"]],
        env={
            "PATH": os.environ["PATH"],
            "GITHUB_OUTPUT": str(output),
            "GITHUB_REF": "refs/heads/master",
            "GITHUB_EVENT_NAME": "push",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Skipping" in result.stdout
    assert output.read_text().strip() == "ready=false"


@pytest.mark.parametrize("migration_fails", [False, True])
def test_deployment_migrates_before_restart_and_checks_health(tmp_path, migration_fails):
    binary = tmp_path / "bin"
    binary.mkdir()
    log = tmp_path / "commands"
    docker = binary / "docker"
    docker.write_text("""#!/usr/bin/env bash
printf 'docker %s\\n' "$*" >> "$COMMAND_LOG"
if [[ "$*" == *"alembic upgrade head"* && "$FAIL_MIGRATION" == 1 ]]; then exit 1; fi
if [[ "$*" == *"printenv GETTER_API_DOMAIN"* ]]; then echo api.example.test; fi
""")
    curl = binary / "curl"
    curl.write_text('#!/usr/bin/env bash\nprintf "curl %s\\n" "$*" >> "$COMMAND_LOG"\n')
    docker.chmod(0o755)
    curl.chmod(0o755)
    (tmp_path / ".env.staging").write_text("GETTER_API_DOMAIN=api.example.test\n")
    (tmp_path / ".current-image").write_text("old-image\n")
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "new-image"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{binary}:{os.environ['PATH']}",
            "COMMAND_LOG": str(log),
            "FAIL_MIGRATION": "1" if migration_fails else "0",
        },
        capture_output=True,
        text=True,
    )
    commands = log.read_text()
    if migration_fails:
        assert result.returncode != 0
        assert "up -d" not in commands
        assert (tmp_path / ".current-image").read_text() == "old-image\n"
    else:
        assert result.returncode == 0, result.stderr
        assert commands.index("alembic upgrade head") < commands.index("up -d")
        assert "https://api.example.test/health/ready" in commands
        assert (tmp_path / ".previous-image").read_text() == "old-image\n"
        assert (tmp_path / ".current-image").read_text() == "new-image\n"
