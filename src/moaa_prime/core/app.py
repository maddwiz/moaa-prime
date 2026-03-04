from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from moaa_prime.agents import CodeAgent, MathAgent
from moaa_prime.contracts import Contract
from moaa_prime.router import MetaRouter, RouterV2, RouterV3, contract_embedding

from moaa_prime.oracle.verifier import OracleV2, OracleVerifier
from moaa_prime.swarm.manager import SwarmManager

from moaa_prime.memory import ReasoningBank

from moaa_prime.evolution.gcel import GCEL, GCELV2
from moaa_prime.trace import TraceRecorder


class MoAAPrime:
    """
    MoAA-Prime app object.

    Supports A/B/C modes:
    - v1: legacy MetaRouter + OracleVerifier + legacy swarm/gcel
    - v2: RouterV2 + OracleV2 + Cycle2 swarm/gcel gating
    - v3: RouterV3 (learned) + OracleV2 + Pareto swarm + trace learning
    """

    def __init__(self, *, mode: str | None = None, seed: int = 0, oracle_rubric_path: str | None = None) -> None:
        self.seed = int(seed)
        self.default_mode = self._normalize_mode(mode or os.getenv("MOAA_AB_MODE") or "v1")
        self._trace_counter = 0

        self.bank = ReasoningBank()
        self.trace_recorder = TraceRecorder()

        math_contract = Contract(
            name="math-agent",
            domains=["math"],
            competence=0.80,
            reliability=0.83,
            cost_prior=0.28,
            tools=["sympy"],
            tags=["equation", "algebra", "reasoning"],
            description="mathematical reasoning agent for equations and numerical correctness",
        )
        code_contract = Contract(
            name="code-agent",
            domains=["code"],
            competence=0.78,
            reliability=0.81,
            cost_prior=0.34,
            tools=["exec"],
            tags=["python", "debug", "implementation"],
            description="software engineering agent for code generation and debugging",
        )

        self.math_contract = self._with_embedding(math_contract)
        self.code_contract = self._with_embedding(code_contract)

        self.math = MathAgent(self.math_contract, bank=self.bank)
        self.code = CodeAgent(self.code_contract, bank=self.bank)
        self.agents = [self.math, self.code]

        self.router_v1 = MetaRouter(self.agents)
        self.router_v2 = RouterV2(self.agents, seed=self.seed)
        self.router_v3 = RouterV3(
            self.agents,
            seed=self.seed,
            model_path=os.getenv("MOAA_ROUTER_V3_MODEL", "models/router_v3.pt"),
            default_budget_mode=os.getenv("MOAA_BUDGET_MODE", "balanced"),
        )

        self.oracle_v1 = OracleVerifier()
        self.oracle_v2 = OracleV2(rubric_path=oracle_rubric_path, seed=self.seed)

        self.swarm_v1 = SwarmManager(self.router_v1, self.oracle_v1, mode="v1", seed=self.seed)
        self.swarm_v2 = SwarmManager(self.router_v2, self.oracle_v2, mode="v2", seed=self.seed)
        self.swarm_v3 = SwarmManager(self.router_v3, self.oracle_v2, mode="v3", seed=self.seed)

        self.gcel_v1 = GCEL(mutation_step=0.04, elite_frac=0.50, seed=self.seed)
        self.gcel_v2 = GCELV2(seed=self.seed)

        # Backward-compatible aliases
        self.router = self.router_v1
        self.oracle = self.oracle_v1
        self.swarm = self.swarm_v1
        self.gcel = self.gcel_v1

    def _normalize_mode(self, mode: str) -> str:
        m = (mode or "v1").strip().lower()
        if m in {"v1", "v2", "v3"}:
            return m
        return "v1"

    def _resolve_mode(self, mode: str | None) -> str:
        if mode is None:
            return self.default_mode
        return self._normalize_mode(mode)

    def _with_embedding(self, contract: Contract) -> Contract:
        emb = contract_embedding(contract, dim=24, seed=self.seed)
        return Contract(
            name=contract.name,
            domains=list(contract.domains),
            tools=list(contract.tools),
            modalities=dict(contract.modalities),
            competence=float(contract.competence),
            reliability=float(contract.reliability),
            cost_prior=float(contract.cost_prior),
            tags=list(contract.tags),
            description=str(contract.description),
            embedding=[float(v) for v in emb],
        )

    def _components_for_mode(self, mode: str):
        if mode == "v2":
            return self.router_v2, self.oracle_v2, self.swarm_v2, self.gcel_v2
        if mode == "v3":
            return self.router_v3, self.oracle_v2, self.swarm_v3, self.gcel_v2
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

    def _next_run_id(self, prompt: str, task_id: str, mode: str) -> str:
        self._trace_counter += 1
        digest = hashlib.sha1(f"{prompt}|{task_id}|{mode}|{self.seed}".encode("utf-8")).hexdigest()[:8]
        return f"{mode}_{self._trace_counter:06d}_{digest}"

    def _contracts_snapshot(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for c in [self.math.contract, self.code.contract]:
            out[c.name] = {
                "name": c.name,
                "domains": list(c.domains),
                "tools": list(c.tools),
                "competence": float(c.competence),
                "reliability": float(c.reliability),
                "cost_prior": float(c.cost_prior),
                "tags": list(c.tags),
                "description": str(c.description),
                "embedding": [float(v) for v in (c.embedding or [])],
            }
        return out

    def _budget_mode(self, budget: Optional[Mapping[str, Any]]) -> str:
        mode = os.getenv("MOAA_BUDGET_MODE", "balanced").strip().lower()
        if isinstance(budget, Mapping):
            mode = str(budget.get("mode", mode) or mode).strip().lower()
        if mode in {"cheap", "balanced", "max_quality"}:
            return mode
        return "balanced"

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
        run_mode = self._resolve_mode(mode)
        router, oracle, _swarm, _gcel = self._components_for_mode(run_mode)

        task_meta = dict(task_metadata or {})
        task_meta.setdefault("task_id", task_id)

        if run_mode == "v1":
            agent, decision = router.route(prompt)  # type: ignore[attr-defined]
        elif run_mode == "v2":
            agent, decision = router.route(  # type: ignore[attr-defined]
                prompt,
                task_metadata=task_meta,
                memory_hints=memory_hints,
                budget=budget,
                history_stats=history_stats,
                top_k=2,
            )
        else:
            agent, decision = router.route(  # type: ignore[attr-defined]
                prompt,
                task_metadata=task_meta,
                memory_hints=memory_hints,
                budget=budget,
                history_stats=history_stats,
                top_k=2,
                budget_mode=self._budget_mode(budget),
            )

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
        run_mode = self._resolve_mode(mode)
        _router, _oracle, swarm, _gcel = self._components_for_mode(run_mode)

        task_meta = dict(task_metadata or {})
        task_meta.setdefault("task_id", task_id)

        budget_payload = dict(budget or {})
        budget_payload.setdefault("mode", self._budget_mode(budget_payload))

        out = swarm.run(
            prompt=prompt,
            task_id=task_id,
            rounds=rounds,
            top_k=top_k,
            mode=run_mode,
            task_metadata=task_meta,
            memory_hints=memory_hints,
            budget=budget_payload,
            history_stats=history_stats,
            cross_check=cross_check,
        )

        out["mode"] = run_mode

        trace_run_id = run_id or self._next_run_id(prompt, task_id, run_mode)

        # Backward-compatible trace file used by Cycle 2 scripts.
        if run_id:
            trace_path = self._write_trace_file(trace_run_id, run_mode, prompt, task_id, out.get("trace", {}))
            out["trace_path"] = trace_path

        # Cycle 3 learning trace + dataset append (every swarm run).
        learn_paths = self.trace_recorder.record(
            run_id=trace_run_id,
            mode=run_mode,
            task_id=task_id,
            prompt=prompt,
            trace=out.get("trace", {}) or {},
            candidates=out.get("candidates", []) or [],
            best=out.get("best", {}) or {},
            contracts=self._contracts_snapshot(),
            budget_mode=self._budget_mode(budget_payload),
            avg_latency=float(out.get("avg_latency_proxy", 0.0)),
            avg_cost=float(out.get("avg_cost_proxy", 0.0)),
        )
        out["learning_trace_path"] = learn_paths["trace_path"]
        out["router_dataset_path"] = learn_paths["dataset_path"]

        return out

    def _apply_contracts(self, contracts: list[Contract]) -> None:
        by_name = {c.name: c for c in contracts}
        if "math-agent" in by_name:
            self.math.contract = self._with_embedding(by_name["math-agent"])
        if "code-agent" in by_name:
            self.code.contract = self._with_embedding(by_name["code-agent"])

    def evolve_contracts(self, fitness: Dict[str, Any], *, mode: str | None = None) -> Dict[str, Any]:
        run_mode = self._resolve_mode(mode)
        _router, _oracle, _swarm, gcel = self._components_for_mode(run_mode)

        before = [self.math.contract, self.code.contract]

        if run_mode in {"v2", "v3"}:
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
                    "tags": c.tags,
                    "description": c.description,
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
                    "tags": c.tags,
                    "description": c.description,
                }
                for c in after
            ],
            "gate": gate,
        }
