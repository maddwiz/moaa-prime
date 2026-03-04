from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Mapping, Sequence
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

    reliability = _clamp((float(a.reliability) * w) + (float(b.reliability) * (1.0 - w)), 0.05, 0.99)
    cost_prior = _clamp((float(a.cost_prior) * w) + (float(b.cost_prior) * (1.0 - w)), 0.01, 0.99)
    tags = sorted(set((a.tags or []) + (b.tags or [])))
    description = a.description if len(a.description) >= len(b.description) else b.description
    embedding = list(a.embedding or b.embedding or [])

    return Contract(
        name=a.name,
        domains=domains,
        tools=tools,
        competence=float(comp),
        reliability=float(reliability),
        cost_prior=float(cost_prior),
        tags=tags,
        description=description,
        embedding=embedding,
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


@dataclass(frozen=True)
class GCELV2Outcome:
    contracts: List[Contract]
    accepted: bool
    baseline_score: float
    candidate_score: float
    fitness: Dict[str, float]


class GCELV2:
    """
    Cycle 2 contract evolution loop.

    Features:
    - uses reliability and cost priors
    - budget-aware fitness aggregation
    - bounded deterministic mutation
    - acceptance gate only when eval score improves
    """

    def __init__(
        self,
        *,
        mutation_step: float = 0.03,
        reliability_step: float = 0.03,
        cost_step: float = 0.03,
        min_improvement: float = 1.0e-6,
        seed: int = 0,
    ) -> None:
        self.mutation_step = float(mutation_step)
        self.reliability_step = float(reliability_step)
        self.cost_step = float(cost_step)
        self.min_improvement = float(min_improvement)
        self.rng = random.Random(int(seed))

    def _clamped_contract(self, c: Contract) -> Contract:
        return replace(
            c,
            competence=float(_clamp(float(c.competence), 0.05, 0.99)),
            reliability=float(_clamp(float(c.reliability), 0.05, 0.99)),
            cost_prior=float(_clamp(float(c.cost_prior), 0.01, 0.99)),
        )

    def _mutate(self, c: Contract) -> Contract:
        return replace(
            c,
            competence=float(_clamp(float(c.competence) + self.rng.uniform(-self.mutation_step, self.mutation_step), 0.05, 0.99)),
            reliability=float(
                _clamp(float(c.reliability) + self.rng.uniform(-self.reliability_step, self.reliability_step), 0.05, 0.99)
            ),
            cost_prior=float(_clamp(float(c.cost_prior) + self.rng.uniform(-self.cost_step, self.cost_step), 0.01, 0.99)),
        )

    def compute_fitness(self, metrics: Mapping[str, Mapping[str, float] | float]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for name, value in metrics.items():
            if isinstance(value, Mapping):
                oracle_score = _clamp(float(value.get("oracle_score", 0.0)), 0.0, 1.0)
                eval_success = _clamp(float(value.get("eval_success", oracle_score)), 0.0, 1.0)
                budget_efficiency = _clamp(float(value.get("budget_efficiency", 0.5)), 0.0, 1.0)
            else:
                oracle_score = _clamp(float(value), 0.0, 1.0)
                eval_success = oracle_score
                budget_efficiency = 0.5

            score = (0.45 * oracle_score) + (0.35 * eval_success) + (0.20 * budget_efficiency)
            out[str(name)] = float(_clamp(score, 0.0, 1.0))
        return out

    def _evaluate(
        self,
        contracts: Sequence[Contract],
        metrics: Mapping[str, Mapping[str, float] | float],
        evaluator: Callable[[Sequence[Contract], Dict[str, float]], float] | None,
    ) -> tuple[float, Dict[str, float]]:
        fitness = self.compute_fitness(metrics)
        if evaluator is not None:
            return float(evaluator(contracts, fitness)), fitness

        if not contracts:
            return 0.0, fitness

        accum = 0.0
        for c in contracts:
            base = float(fitness.get(c.name, 0.0))
            value = (0.75 * base) + (0.15 * float(c.reliability)) + (0.10 * (1.0 - float(c.cost_prior)))
            accum += _clamp(value, 0.0, 1.0)
        return float(accum / float(len(contracts))), fitness

    def evolve(
        self,
        contracts: Sequence[Contract],
        metrics: Mapping[str, Mapping[str, float] | float],
        *,
        evaluator: Callable[[Sequence[Contract], Dict[str, float]], float] | None = None,
    ) -> GCELV2Outcome:
        baseline = [self._clamped_contract(c) for c in contracts]
        baseline_score, fitness = self._evaluate(baseline, metrics, evaluator)

        candidate = [self._mutate(c) for c in baseline]
        candidate_score, _ = self._evaluate(candidate, metrics, evaluator)

        accepted = bool(candidate_score >= (baseline_score + self.min_improvement))
        final_contracts = candidate if accepted else baseline

        return GCELV2Outcome(
            contracts=list(final_contracts),
            accepted=accepted,
            baseline_score=float(baseline_score),
            candidate_score=float(candidate_score),
            fitness=fitness,
        )
