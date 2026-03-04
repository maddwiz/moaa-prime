from __future__ import annotations

import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from moaa_prime.cli.main import main


def _run_cli(argv: list[str]) -> tuple[int, str]:
    buf = StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def _run_module(argv: list[str]) -> tuple[int, str, str]:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join([src_path, existing_pythonpath] if existing_pythonpath else [src_path])

    proc = subprocess.run(
        [sys.executable, "-m", "moaa_prime", *argv],
        capture_output=True,
        cwd=repo_root,
        env=env,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_cli_shorthand_prompt_routes_once() -> None:
    code, out = _run_cli(["Solve: 2x + 3 = 7. Return only x."])
    payload = json.loads(out)

    assert code == 0
    assert "decision" in payload
    assert "result" in payload
    assert "oracle" in payload


def test_cli_swarm_subcommand_returns_candidates() -> None:
    code, out = _run_cli(["swarm", "Explain why 1/0 is undefined."])
    payload = json.loads(out)

    assert code == 0
    assert "candidates" in payload


def test_module_entrypoint_hello_dispatches_cli() -> None:
    code, out, err = _run_module(["hello"])

    assert code == 0
    assert out.strip() == "moaa-prime says hello"
    assert err == ""


def test_module_entrypoint_shorthand_prompt_routes_once() -> None:
    code, out, err = _run_module(["Solve: 2x + 3 = 7. Return only x."])
    payload = json.loads(out)

    assert code == 0
    assert err == ""
    assert "decision" in payload
    assert "result" in payload
    assert "oracle" in payload
