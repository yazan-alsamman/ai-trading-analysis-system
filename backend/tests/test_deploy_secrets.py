"""Y14 deploy: GEMINI_API_KEY reaches the server .env like the cTrader secrets.

``infra/deploy/set-env-secrets.sh`` writes a key only when it is missing or empty (an existing
value is never overwritten) and never prints a value. The Deploy workflow step skips an unset
GitHub secret ("GEMINI_API_KEY not set in GitHub: skipped") and pipes the value over SSH stdin.
The step's own shell script is run here with a fake ``ssh`` on PATH."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra" / "deploy" / "set-env-secrets.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy.yml"
BASH = shutil.which("bash")
KEY = "AIzaFAKE0000000000000000000000000000000"

pytestmark = pytest.mark.skipif(BASH is None, reason="bash is needed")


def run_script(app: Path, stdin: str) -> str:
    result = subprocess.run(  # bytes: no newline translation (CRLF on Windows)
        [BASH, SCRIPT.as_posix()],
        input=stdin.encode(),
        capture_output=True,
        env={**os.environ, "TRADING_DIR": app.as_posix()},
        check=True,
    )
    return (result.stdout + result.stderr).decode()


def test_written_only_when_missing_or_empty(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("JWT_SECRET=s\nGEMINI_API_KEY=\nOTHER=1\n", encoding="utf-8")
    out = run_script(tmp_path, f"GEMINI_API_KEY={KEY}\n")
    assert "set-env-secrets: GEMINI_API_KEY written" in out and KEY not in out
    lines = env.read_text(encoding="utf-8").splitlines()
    assert f"GEMINI_API_KEY={KEY}" in lines and "GEMINI_API_KEY=" not in lines
    assert "JWT_SECRET=s" in lines and "OTHER=1" in lines

    out = run_script(tmp_path, "GEMINI_API_KEY=AIzaANOTHER000000000000000000000000000\n")
    assert "GEMINI_API_KEY already set on the server: kept" in out and "ANOTHER" not in out
    assert f"GEMINI_API_KEY={KEY}" in env.read_text(encoding="utf-8")  # never overwritten


def test_missing_key_is_appended_and_empty_value_skipped(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("JWT_SECRET=s\n", encoding="utf-8")
    out = run_script(tmp_path, "GEMINI_API_KEY=\n")  # an empty secret: nothing
    assert "written" not in out and env.read_text(encoding="utf-8") == "JWT_SECRET=s\n"
    run_script(tmp_path, f"GEMINI_API_KEY={KEY}\n")
    assert env.read_text(encoding="utf-8").splitlines()[-1] == f"GEMINI_API_KEY={KEY}"
    no_env = tmp_path / "fresh"
    no_env.mkdir()
    assert "no .env yet" in run_script(no_env, f"GEMINI_API_KEY={KEY}\n")


def _step() -> dict:
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    steps = [s for job in jobs.values() for s in job.get("steps", [])]
    names = [s.get("name", "") for s in steps]
    gemini = next(i for i, n in enumerate(names) if n.startswith("Gemini API key"))
    restart = names.index("Pull images and restart the trading stack")
    assert gemini < restart  # written before the stack is (re)started
    return steps[gemini]


def test_workflow_step(tmp_path: Path) -> None:
    step = _step()
    assert step["env"] == {"GEMINI_API_KEY": "${{ secrets.GEMINI_API_KEY }}"}
    script = step["run"]
    assert 'echo "::add-mask::$GEMINI_API_KEY"' in script
    # the value is only ever masked or piped, never echoed
    echoed = [line for line in script.splitlines() if "echo" in line and "GEMINI_API_KEY" in line]
    assert all("::add-mask::" in line or "not set in GitHub" in line for line in echoed)

    calls = tmp_path / "ssh-calls"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_ssh = bin_dir / "ssh"
    fake_ssh.write_text(
        f'#!/usr/bin/env bash\necho "$@" >> "{calls.as_posix()}"\ncat >> "{calls.as_posix()}"\n',
        encoding="utf-8",
    )
    fake_ssh.chmod(0o755)

    def run_step(value: str) -> str:
        result = subprocess.run(
            [BASH, "-e", "-c", script],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GEMINI_API_KEY": value,
                "PATH": f"{bin_dir.as_posix()}{os.pathsep if os.name != 'nt' else ':'}"
                + os.environ.get("PATH", ""),
            },
            check=True,
        )
        return result.stdout

    out = run_step("")
    assert out.strip() == "GEMINI_API_KEY not set in GitHub: skipped"
    assert not calls.exists()  # nothing sent, and the deploy goes on (exit 0)

    out = run_step(KEY)
    sent = calls.read_text(encoding="utf-8")
    assert "bash /opt/trading/set-env-secrets.sh" in sent and f"GEMINI_API_KEY={KEY}" in sent
    assert out.strip() == f"::add-mask::{KEY}"  # only the mask command (hidden by Actions)
