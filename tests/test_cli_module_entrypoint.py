from __future__ import annotations

import json
from importlib.util import find_spec
from contextlib import redirect_stdout
from io import StringIO

from moaa_prime.cli.main import main


def _run_cli(argv: list[str]) -> tuple[int, str]:
    buf = StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


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


def test_module_entrypoint_exists() -> None:
    assert find_spec("moaa_prime.__main__") is not None
