from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from moaa_prime.agents import CodeAgent, MathAgent
from moaa_prime.contracts import Contract
from moaa_prime.duality import GatedDualBrainSelector
from moaa_prime.router import MetaRouter, RouterV2, RouterV3, contract_embedding
from moaa_prime.router.intent import analyze_prompt_intent, intent_confidence_score

from moaa_prime.oracle.verifier import OracleV2, OracleVerifier
from moaa_prime.swarm.dual_brain_runner import DualBrainRunner
from moaa_prime.swarm.manager import SwarmManager

from moaa_prime.memory import ReasoningBank

from moaa_prime.evolution.gcel import GCEL, GCELV2
from moaa_prime.schema import upgrade_answer_object
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

        self.dual_brain_runner = DualBrainRunner()
        self.gated_dual_selector = GatedDualBrainSelector()

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

    def _boolish(self, value: Any, *, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        if isinstance(value, (int, float)):
            return bool(value)
        return default

    def _safe_float(self, value: Any, *, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _selector_from_config(
        self,
        dual_gate_config: Optional[Mapping[str, Any]],
    ) -> GatedDualBrainSelector:
        if not isinstance(dual_gate_config, Mapping):
            return self.gated_dual_selector

        low_default = float(self.gated_dual_selector.low_confidence_threshold)
        high_default = float(self.gated_dual_selector.high_ambiguity_threshold)
        low = self._safe_float(dual_gate_config.get("low_confidence_threshold"), default=low_default)
        high = self._safe_float(dual_gate_config.get("high_ambiguity_threshold"), default=high_default)
        return GatedDualBrainSelector(
            low_confidence_threshold=low,
            high_ambiguity_threshold=high,
        )

    def _is_dual_gate_enabled(self, dual_gate: bool | None) -> bool:
        if dual_gate is not None:
            return bool(dual_gate)
        return self._boolish(os.getenv("MOAA_DUAL_GATE"), default=False)

    def _ranked_router_scores(self, out: Mapping[str, Any]) -> list[float]:
        ranked = (((out.get("trace", {}) or {}).get("router", {}) or {}).get("ranked", []) or [])
        scores: list[float] = []
        for row in ranked:
            if isinstance(row, Mapping):
                scores.append(self._safe_float(row.get("score"), default=0.0))
        return scores

    def _build_dual_candidate(
        self,
        *,
        prompt: str,
        run_mode: str,
        single_candidate: Mapping[str, Any],
    ) -> Dict[str, Any]:
        dual_result = self.dual_brain_runner.run(prompt)
        architect = dict((dual_result.get("architect") or {}))
        oracle = dict((dual_result.get("oracle") or {}))

        plan = str(architect.get("plan", "") or "")
        approved = bool(oracle.get("approved", False))
        reason = str(oracle.get("reason", "dual-brain verdict") or "dual-brain verdict")
        score = self._safe_float(oracle.get("score"), default=0.0)
        score = max(0.0, min(1.0, score))

        text = plan if approved else f"{plan}\nOracle veto: {reason}"
        token_count = max(1, len(text.split()))
        base_round = int(self._safe_float(single_candidate.get("round"), default=1.0))
        base_rank = int(self._safe_float(single_candidate.get("rank"), default=0.0))

        latency_proxy = float(46 + (4 * token_count) + (6 if run_mode == "v3" else 10))
        cost_proxy = float(18 + token_count + (8 if approved else 4))

        return {
            "agent": "dual-brain",
            "text": text,
            "meta": {
                "dual_brain": {
                    "architect": architect,
                    "oracle": oracle,
                },
                "dual_gate": {
                    "source": "dual_brain_runner",
                    "approved": approved,
                },
            },
            "oracle": {
                "score": score,
                "reason": reason,
                "meta": {
                    "source": "dual_brain_runner",
                    "approved": approved,
                    "oracle_meta": oracle.get("meta", {}) or {},
                },
            },
            "round": max(1, base_round),
            "rank": max(0, base_rank + 1),
            "latency_proxy": latency_proxy,
            "cost_proxy": cost_proxy,
            "confidence_proxy": score,
        }

    def _apply_dual_gate(
        self,
        *,
        out: Dict[str, Any],
        prompt: str,
        run_mode: str,
        dual_gate: bool | None,
        dual_gate_config: Optional[Mapping[str, Any]],
    ) -> None:
        trace = out.get("trace")
        if not isinstance(trace, dict):
            trace = {}
            out["trace"] = trace

        swarm_trace = trace.get("swarm")
        if not isinstance(swarm_trace, dict):
            swarm_trace = {}
            trace["swarm"] = swarm_trace

        enabled = self._is_dual_gate_enabled(dual_gate)
        selector = self._selector_from_config(dual_gate_config)
        dual_trace: Dict[str, Any] = {
            "enabled": bool(enabled),
            "triggered": False,
            "reasons": [],
            "confidence": self._safe_float(out.get("confidence"), default=0.0),
            "ambiguity": 0.0,
            "tool_failed": False,
            "thresholds": {
                "low_confidence": float(selector.low_confidence_threshold),
                "high_ambiguity": float(selector.high_ambiguity_threshold),
            },
            "selector": {
                "winner_source": "single",
                "rule": "disabled",
            },
            "candidate_labels": ["single"],
        }

        best = out.get("best")
        if not isinstance(best, Mapping):
            swarm_trace["dual_gate"] = dual_trace
            return

        best_candidate = dict(best)
        if not enabled:
            swarm_trace["dual_gate"] = dual_trace
            return

        dual_candidate = self._build_dual_candidate(
            prompt=prompt,
            run_mode=run_mode,
            single_candidate=best_candidate,
        )

        ranked_scores = self._ranked_router_scores(out)
        best_meta = best_candidate.get("meta") if isinstance(best_candidate.get("meta"), Mapping) else {}
        selection = selector.run(
            single={**best_candidate, "label": "single"},
            dual={**dual_candidate, "label": "dual"},
            confidence=self._safe_float(out.get("confidence"), default=0.0),
            ranked_scores=ranked_scores,
            answer_metadata=best_meta,
        )

        dual_trace.update(
            {
                "triggered": bool(selection.trigger.should_trigger),
                "reasons": list(selection.trigger.reasons),
                "confidence": float(selection.trigger.confidence),
                "ambiguity": float(selection.trigger.ambiguity),
                "tool_failed": bool(selection.trigger.tool_failed),
                "selector": {
                    "winner_source": str(selection.winner.label),
                    "rule": str(selection.selection_reason),
                },
                "candidate_labels": [str(c.label) for c in selection.candidates],
            }
        )

        if selection.trigger.should_trigger:
            candidates = out.get("candidates", [])
            candidate_rows: list[Dict[str, Any]] = []
            if isinstance(candidates, list):
                for row in candidates:
                    if isinstance(row, Mapping):
                        candidate_rows.append(dict(row))
            has_dual = any(str(c.get("agent", "")) == "dual-brain" for c in candidate_rows)
            if not has_dual:
                candidate_rows.append(dual_candidate)
            out["candidates"] = candidate_rows

        if selection.winner.label == "dual":
            out["best"] = dual_candidate
            out["confidence"] = max(
                self._safe_float(out.get("confidence"), default=0.0),
                self._safe_float(dual_candidate.get("confidence_proxy"), default=0.0),
            )

            final_trace = trace.get("final")
            if not isinstance(final_trace, dict):
                final_trace = {}
                trace["final"] = final_trace
            final_trace["agent"] = str(dual_candidate.get("agent", ""))
            final_trace["score"] = self._safe_float((dual_candidate.get("oracle", {}) or {}).get("score"), default=0.0)
            final_trace["confidence"] = self._safe_float(out.get("confidence"), default=0.0)

        swarm_trace["dual_gate"] = dual_trace

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
        answer_meta = result.meta if isinstance(result.meta, Mapping) else None
        if answer_meta is None:
            oracle_block = oracle.verdict(prompt, result.text)
        else:
            try:
                oracle_block = oracle.verdict(prompt, result.text, answer_metadata=answer_meta)
            except TypeError as exc:
                if "answer_metadata" in str(exc):
                    oracle_block = oracle.verdict(prompt, result.text)
                else:
                    raise

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

        fallback_intent = analyze_prompt_intent(prompt, task_metadata=task_meta)
        decision_intent = getattr(decision, "intent", None)
        if isinstance(decision_intent, str) and decision_intent.strip():
            intent = decision_intent.strip().lower()
        else:
            intent = fallback_intent.intent

        decision_features = getattr(decision, "matched_features", ())
        if isinstance(decision_features, (list, tuple)):
            matched_features = [str(x) for x in decision_features if str(x).strip()]
        else:
            matched_features = list(fallback_intent.matched_features)

        decision_intent_scores = getattr(decision, "intent_scores", {})
        if isinstance(decision_intent_scores, Mapping):
            intent_scores = {str(k): float(v) for k, v in decision_intent_scores.items()}
        else:
            intent_scores = {k: float(v) for k, v in fallback_intent.scores.items()}

        route_trace = {
            "intent": intent,
            "intent_scores": intent_scores,
            "intent_confidence": float(intent_confidence_score(intent_scores, intent)),
            "matched_features": matched_features,
            "chosen_agent": decision_payload["agent"],
            "selected_by_exploration": decision_payload["selected_by_exploration"],
            "ranking_rationale": decision_payload["rationale"],
        }

        out = {
            "mode": run_mode,
            "decision": decision_payload,
            "route_trace": route_trace,
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
        return upgrade_answer_object(out)

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
        dual_gate: bool | None = None,
        dual_gate_config: Optional[Mapping[str, Any]] = None,
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
        self._apply_dual_gate(
            out=out,
            prompt=prompt,
            run_mode=run_mode,
            dual_gate=dual_gate,
            dual_gate_config=dual_gate_config,
        )

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

        return upgrade_answer_object(out)

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
