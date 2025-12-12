from __future__ import annotations

import argparse
import json

from moaa_prime.core.app import MoAAPrime


def main() -> None:
    parser = argparse.ArgumentParser(prog="moaa-prime")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("hello")

    p_route = sub.add_parser("route")
    p_route.add_argument("prompt", type=str)

    p_swarm = sub.add_parser("swarm")
    p_swarm.add_argument("prompt", type=str)

    args = parser.parse_args()
    app = MoAAPrime()

    if args.cmd == "hello":
        print(app.hello())
        return

    if args.cmd == "route":
        out = app.run_once(args.prompt)
        print(json.dumps(out, indent=2))
        return

    if args.cmd == "swarm":
        out = app.run_swarm(args.prompt)
        print(json.dumps(out, indent=2))
        return


if __name__ == "__main__":
    main()
