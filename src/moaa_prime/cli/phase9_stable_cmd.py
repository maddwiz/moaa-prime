from __future__ import annotations

import json
from typing import Optional

from moaa_prime.sfc import StabilityFieldController
from moaa_prime.swarm import StableSwarmRunner, SwarmManager

try:
    from moaa_prime.oracle.verifier import OracleVerifier
except Exception:  # pragma: no cover
    OracleVerifier = None  # type: ignore


def run_stable_swarm(prompt: str, rounds: int = 6, min_stability: float = 0.3) -> dict:
    """
    Phase 9: SFC-gated swarm run (stable swarm).
    This is intentionally simple and testable.

    NOTE:
    - Uses SwarmManager with a direct agent list, so it does NOT depend on MetaRouter.
    - Later we can add router-based routing as an option.
    """

    class DummyAgent:
        def __init__(self, name: str) -> None:
            self.name = name

        def handle(self, prompt_in: str):
            class R:
                agent_name = "dummy"
                text = f"{prompt_in} -> {self.name}"
                meta = {}
            return R()

    agents = [DummyAgent("A"), DummyAgent("B")]

    oracle = OracleVerifier() if OracleVerifier else None
    swarm = SwarmManager(agents, oracle)  # direct list path (Phase 9 compatible)
    sfc = StabilityFieldController()

    runner = StableSwarmRunner(swarm=swarm, oracle=oracle, sfc=sfc, min_stability=min_stability)
    result = runner.run(prompt, rounds=rounds)

    return {
        "best": result.best,
        "candidates": result.candidates,
        "stopped_early": result.stopped_early,
        "sfc_value": result.sfc_value,
        "meta": result.meta,
    }


def main(argv: Optional[list[str]] = None) -> int:
    import sys

    args = sys.argv[1:] if argv is None else argv
    prompt = " ".join(args).strip()
    if not prompt:
        print('Usage: python -m moaa_prime.cli.phase9_stable_cmd "your prompt"')
        return 2

    out = run_stable_swarm(prompt)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
