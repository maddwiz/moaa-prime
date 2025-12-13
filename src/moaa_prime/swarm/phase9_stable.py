from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from moaa_prime.sfc import StabilityFieldController
from moaa_prime.swarm.manager import SwarmManager

try:
    from moaa_prime.oracle.verifier import OracleVerifier
except Exception:  # pragma: no cover
    OracleVerifier = None  # type: ignore


@dataclass
class StableRunResult:
    best: str
    candidates: List[str]
    sfc_value: float
    stopped_early: bool
    meta: Dict[str, Any]


class StableSwarmRunner:
    """
    Phase 9:
    A wrapper around SwarmManager that applies SFC gating.

    IMPORTANT:
    - Does not change Phase 4–8 SwarmManager behavior.
    - Adds "stop early" safety when the swarm becomes unstable.
    """

    def __init__(
        self,
        swarm: SwarmManager,
        oracle: Optional[OracleVerifier] = None,
        sfc: Optional[StabilityFieldController] = None,
        min_stability: float = 0.3,
    ) -> None:
        self.swarm = swarm
        self.oracle = oracle
        self.sfc = sfc or StabilityFieldController()
        self.min_stability = min_stability

    def run(self, prompt: str, rounds: int = 3) -> StableRunResult:
        """
        Runs swarm deliberation in small steps and applies SFC gating.
        """
        stopped_early = False
        candidates: List[str] = []

        # We iterate one round at a time so we can stop if stability collapses.
        for r in range(rounds):
            out = self.swarm.run(prompt, rounds=1)
            best = out["best"]
            candidates = out.get("candidates", [])

            # --- Metrics (v0 heuristics) ---
            oracle_score = 0.5
            if self.oracle is not None:
                try:
                    oracle_score = float(self.oracle.score(prompt, best))
                except Exception:
                    oracle_score = 0.5

            # Energy (if your energy_fusion exists, use it; else assume calm)
            energy = 0.0
            try:
                if getattr(self.swarm, "energy_fusion", None) is not None and self.oracle is not None:
                    # EnergyFusion in your repo is Phase 7/8. We treat higher disagreement as higher energy.
                    # If your EnergyFusion API differs, this stays safely in the try/except.
                    energy = float(self.swarm.energy_fusion.energy(prompt, candidates))  # type: ignore[attr-defined]
            except Exception:
                energy = 0.0

            # kl_like novelty proxy (cheap + stable): more candidates -> more novelty/chaos
            kl_like = min(1.0, max(0.0, (len(candidates) - 1) / 5.0))

            sfc_value = float(self.sfc.update(oracle_score=oracle_score, energy=energy, kl_like=kl_like))

            if sfc_value < self.min_stability:
                stopped_early = True
                break

        meta = {
            "oracle_score": oracle_score,
            "energy": energy,
            "kl_like": kl_like,
            "rounds_attempted": (r + 1),
        }

        return StableRunResult(
            best=best,
            candidates=candidates,
            sfc_value=float(self.sfc.state.value),
            stopped_early=stopped_early,
            meta=meta,
        )
