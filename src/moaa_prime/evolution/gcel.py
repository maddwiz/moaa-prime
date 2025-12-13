from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Sequence
import random

from moaa_prime.contracts import Contract


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def mutate_competence(
    contract: Contract,
    *,
    step: float,
    rng: random.Random,
    min_comp: float = 0.05,
    max_comp: float = 0.99,
) -> Contract:
    # Always clamp even if delta is 0, so low values get lifted into bounds.
    delta = rng.uniform(-step, step)
    new_comp = _clamp(float(contract.competence) + float(delta), min_comp, max_comp)
    return replace(contract, competence=float(new_comp))


def crossover_contracts(a: Contract, b: Contract, *, rng: random.Random) -> Contract:
    w = rng.uniform(0.35, 0.65)
    comp = _clamp((a.competence * w) + (b.competence * (1.0 - w)), 0.05, 0.99)

    domains = sorted(set((a.domains or []) + (b.domains or [])))
    tools = sorted(set((a.tools or []) + (b.tools or [])))

    # Light random drop to avoid “always accumulating”
    if domains and rng.random() < 0.20:
        domains.pop(rng.randrange(len(domains)))
    if tools and rng.random() < 0.20:
        tools.pop(rng.randrange(len(tools)))

    return Contract(
        name=a.name,
        domains=domains,
        tools=tools,
        competence=float(comp),
    )


class GCEL:
    """
    Phase 11: Genetic Contract Evolution Loop (minimal, testable)

    Guarantees:
    - Preserves ordering and names
    - Always clamps competence to [0.05, 0.99] (even if untouched)
    """

    def __init__(self, mutation_step: float = 0.04, elite_frac: float = 0.50, seed: int = 0) -> None:
        self.mutation_step = float(mutation_step)
        self.elite_frac = float(elite_frac)
        self.rng = random.Random(int(seed))

    def evolve(self, contracts: Sequence[Contract], fitness: Dict[str, float]) -> List[Contract]:
        cs = list(contracts)
        if not cs:
            return []

        # Clamp ALL competences up-front so even “untouched” contracts are valid.
        cs = [replace(c, competence=float(_clamp(float(c.competence), 0.05, 0.99))) for c in cs]

        scored = sorted(cs, key=lambda c: float(fitness.get(c.name, 0.0)), reverse=True)
        elite_n = max(1, int(round(len(scored) * self.elite_frac)))
        elites = scored[:elite_n]

        out: List[Contract] = []
        for i, c in enumerate(cs):
            if i < elite_n:
                # Keep elite, but mutate slightly (still clamped).
                out.append(mutate_competence(c, step=self.mutation_step, rng=self.rng))
            else:
                a = self.rng.choice(elites)
                b = self.rng.choice(elites)
                child = crossover_contracts(a, b, rng=self.rng)
                child = mutate_competence(child, step=self.mutation_step, rng=self.rng)
                # Preserve original name so the system stays stable.
                out.append(replace(child, name=c.name))

        # Ensure ordering and names preserved exactly
        by_name = {c.name: c for c in out}
        return [by_name.get(c.name, c) for c in cs]
