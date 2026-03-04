from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from moaa_prime.agents import CodeAgent, MathAgent
from moaa_prime.contracts import Contract
from moaa_prime.router import MetaRouter, RouterV2

from moaa_prime.oracle.verifier import OracleV2, OracleVerifier
from moaa_prime.swarm.manager import SwarmManager

from moaa_prime.memory import ReasoningBank

from moaa_prime.evolution.gcel import GCEL, GCELV2


class MoAAPrime:
    """
    MoAA-Prime app object.

    IMPORTANT:
    This file remains backward-compatible with Phase 1–12 tests,
    while adding Cycle 2 A/B execution paths.
    """

    def __init__(self, *, mode: str | None = None, seed: int = 0, oracle_rubric_path: str | None = None) -> None:
        self.seed = int(seed)
        self.default_mode = self._normalize_mode(mode or os.getenv("MOAA_AB_MODE") or "v1")

        # Phase 5+: global memory bank
        self.bank = ReasoningBank()

        # Phase 2 + Cycle 2 priors
        self.math_contract = Contract(
            name="math-agent",
            domains=["math"],
            competence=0.80,
            reliability=0.83,
            cost_prior=0.28,
            tools=["sympy"],
        )
        self.code_contract = Contract(
            name="code-agent",
            domains=["code"],
            competence=0.78,
            reliability=0.81,
            cost_prior=0.34,
            tools=["exec"],
        )

        # Agents (wired to bank)
        self.math = MathAgent(self.math_contract, bank=self.bank)
        self.code = CodeAgent(self.code_contract, bank=self.bank)
        self.agents = [self.math, self.code]

        # Routers
        self.router_v1 = MetaRouter(self.agents)
        self.router_v2 = RouterV2(self.agents, seed=self.seed)

        # Oracles
        self.oracle_v1 = OracleVerifier()
        self.oracle_v2 = OracleV2(rubric_path=oracle_rubric_path, seed=self.seed)

        # Swarm managers
        self.swarm_v1 = SwarmManager(self.router_v1, self.oracle_v1, mode="v1", seed=self.seed)
        self.swarm_v2 = SwarmManager(self.router_v2, self.oracle_v2, mode="v2", seed=self.seed)

        # GCEL evolvers
        self.gcel_v1 = GCEL(mutation_step=0.04, elite_frac=0.50, seed=self.seed)
        self.gcel_v2 = GCELV2(seed=self.seed)

        # Backward-compatible aliases
        self.router = self.router_v1
        self.oracle = self.oracle_v1
        self.swarm = self.swarm_v1
        self.gcel = self.gcel_v1

    def _normalize_mode(self, mode: str) -> str:
        m = (mode or "v1").strip().lower()
        return "v2" if m == "v2" else "v1"

    def _resolve_mode(self, mode: str | None) -> str:
        if mode is None:
            return self.default_mode
        return self._normalize_mode(mode)

    def _components_for_mode(self, mode: str):
        if mode == "v2":
            return self.router_v2, self.oracle_v2, self.swarm_v2, self.gcel_v2
        return self.router_v1, self.oracle_v1, self.swarm_v1, self.gcel_v1

    def _write_trace_file(self, run_id: str, mode: str, prompt: str, task_id: str, trace: Mapping[str, Any]) -> str:
        reports = Path("reports")
        reports.mkdir(parents=True, exist_ok=True)

        payload = {
            "run_id": run_id,
            "mode": mode,
            "task_id": task_id,
            "prompt": prompt,
            "router": trace.get("router", {}),
            "swarm": trace.get("swarm", {}),
            "oracle": trace.get("oracle", {}),
            "final": trace.get("final", {}),
        }

        path = reports / f"trace_{run_id}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(path)

    def hello(self) -> str:
        return "moaa-prime says hello"

    def run_once(
        self,
        prompt: str,
        task_id: str = "default",
        *,
        mode: str | None = None,
        task_metadata: Optional[Mapping[str, Any]] = None,
        memory_hints: Optional[Mapping[str, Any]] = None,
        budget: Optional[Mapping[str, Any]] = None,
        history_stats: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Phase 2/3/5 contract:
        - accepts task_id
        - returns decision + result
        - includes top-level "oracle" block
        """
        run_mode = self._resolve_mode(mode)
        router, oracle, _swarm, _gcel = self._components_for_mode(run_mode)

        task_meta = dict(task_metadata or {})
        task_meta.setdefault("task_id", task_id)

        if run_mode == "v2":
            agent, decision = router.route(  # type: ignore[attr-defined]
                prompt,
                task_metadata=task_meta,
                memory_hints=memory_hints,
                budget=budget,
                history_stats=history_stats,
                top_k=2,
            )
        else:
            agent, decision = router.route(prompt)

        result = agent.handle(prompt, task_id=task_id)
        oracle_block = oracle.verdict(prompt, result.text)

        decision_payload = {
            "agent": decision.agent_name,
            "score": float(decision.score),
            "reason": getattr(decision, "reason", "router_score"),
            "rationale": getattr(decision, "rationale", ""),
            "exploration_probability": float(getattr(decision, "exploration_probability", 0.0)),
            "expected_utility": float(getattr(decision, "expected_utility", decision.score)),
            "selected_by_exploration": bool(getattr(decision, "selected_by_exploration", False)),
            "components": getattr(decision, "components", {}) or {},
        }

        return {
            "mode": run_mode,
            "decision": decision_payload,
            "result": {
                "agent": result.agent_name,
                "text": result.text,
                "meta": result.meta or {},
            },
            "oracle": {
                "score": float(getattr(oracle_block, "score", 0.5)),
                "reason": getattr(oracle_block, "reason", ""),
                "meta": getattr(oracle_block, "meta", {}) or {},
            },
        }

    def run_swarm(
        self,
        prompt: str,
        task_id: str = "default",
        rounds: int = 3,
        top_k: int = 2,
        *,
        mode: str | None = None,
        task_metadata: Optional[Mapping[str, Any]] = None,
        memory_hints: Optional[Mapping[str, Any]] = None,
        budget: Optional[Mapping[str, Any]] = None,
        history_stats: Optional[Mapping[str, Any]] = None,
        cross_check: bool = False,
        run_id: str | None = None,
    ) -> Dict[str, Any]:
        """
        Phase 4 contract: must exist.
        Cycle 2 adds optional mode + trace emission.
        """
        run_mode = self._resolve_mode(mode)
        _router, _oracle, swarm, _gcel = self._components_for_mode(run_mode)

        task_meta = dict(task_metadata or {})
        task_meta.setdefault("task_id", task_id)

        out = swarm.run(
            prompt=prompt,
            task_id=task_id,
            rounds=rounds,
            top_k=top_k,
            mode=run_mode,
            task_metadata=task_meta,
            memory_hints=memory_hints,
            budget=budget,
            history_stats=history_stats,
            cross_check=cross_check,
        )

        out["mode"] = run_mode

        if run_id:
            trace_path = self._write_trace_file(run_id, run_mode, prompt, task_id, out.get("trace", {}))
            out["trace_path"] = trace_path

        return out

    def _apply_contracts(self, contracts: list[Contract]) -> None:
        by_name = {c.name: c for c in contracts}
        if "math-agent" in by_name:
            self.math.contract = by_name["math-agent"]
        if "code-agent" in by_name:
            self.code.contract = by_name["code-agent"]

    def evolve_contracts(self, fitness: Dict[str, Any], *, mode: str | None = None) -> Dict[str, Any]:
        """
        Phase 11 + Cycle 2:
        Evolve contracts based on fitness or richer metrics.
        Returns before/after snapshot.
        """
        run_mode = self._resolve_mode(mode)
        _router, _oracle, _swarm, gcel = self._components_for_mode(run_mode)

        before = [self.math.contract, self.code.contract]

        if run_mode == "v2":
            outcome = gcel.evolve(before, fitness)  # type: ignore[attr-defined]
            after = list(outcome.contracts)
            self._apply_contracts(after)
            gate = {
                "accepted": bool(outcome.accepted),
                "baseline_score": float(outcome.baseline_score),
                "candidate_score": float(outcome.candidate_score),
                "fitness": outcome.fitness,
            }
        else:
            after = gcel.evolve(before, fitness)  # type: ignore[attr-defined]
            self._apply_contracts(after)
            gate = {
                "accepted": True,
                "baseline_score": None,
                "candidate_score": None,
                "fitness": {k: float(v) for k, v in fitness.items()} if fitness else {},
            }

        return {
            "mode": run_mode,
            "before": [
                {
                    "name": c.name,
                    "competence": c.competence,
                    "reliability": c.reliability,
                    "cost_prior": c.cost_prior,
                    "domains": c.domains,
                    "tools": c.tools,
                }
                for c in before
            ],
            "after": [
                {
                    "name": c.name,
                    "competence": c.competence,
                    "reliability": c.reliability,
                    "cost_prior": c.cost_prior,
                    "domains": c.domains,
                    "tools": c.tools,
                }
                for c in after
            ],
            "gate": gate,
        }
