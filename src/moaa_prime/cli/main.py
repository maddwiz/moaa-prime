from __future__ import annotations

import argparse
import sys
from typing import Sequence

from moaa_prime.core.app import MoAAPrime
from moaa_prime.util.json_safe import dumps_pretty


def _run_cmd(app: MoAAPrime, cmd: str, prompt: str | None = None) -> int:
    if cmd == "hello":
        print(app.hello())
        return 0

    if cmd == "route":
        if not prompt:
            raise ValueError("route requires a prompt")
        out = app.run_once(prompt)
        print(dumps_pretty(out))
        return 0

    if cmd == "swarm":
        if not prompt:
            raise ValueError("swarm requires a prompt")
        out = app.run_swarm(prompt)
        print(dumps_pretty(out))
        return 0

    raise ValueError(f"unknown command: {cmd}")


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    app = MoAAPrime()

    # Shorthand: `python -m moaa_prime "prompt"` routes once by default.
    if argv and argv[0] not in {"hello", "route", "swarm", "-h", "--help"}:
        return _run_cmd(app, "route", " ".join(argv))

    parser = argparse.ArgumentParser(prog="moaa-prime")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("hello")

    p_route = sub.add_parser("route")
    p_route.add_argument("prompt", type=str)

    p_swarm = sub.add_parser("swarm")
    p_swarm.add_argument("prompt", type=str)

    args = parser.parse_args(argv)
    return _run_cmd(app, args.cmd, getattr(args, "prompt", None))


if __name__ == "__main__":
    raise SystemExit(main())
