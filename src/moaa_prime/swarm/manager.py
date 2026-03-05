from __future__ import annotations

import re
import statistics
from typing import Any, Dict, List, Mapping, Optional, Union

from moaa_prime.router.intent import analyze_prompt_intent, intent_confidence_score
from moaa_prime.router.meta_router import MetaRouter
from moaa_prime.swarm.pareto import pareto_frontier

try:
    from moaa_prime.oracle.verifier import OracleVerifier
except Exception:  # pragma: no cover
    OracleVerifier = None  # type: ignore

# Phase 7/8 optional imports
try:
    from moaa_prime.sgm import SharedGeometricManifold
    from moaa_prime.fusion import EnergyFusion
except Exception:  # pragma: no cover
    SharedGeometricManifold = None  # type: ignore
    EnergyFusion = None  # type: ignore


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _coerce_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "pass", "passed"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _clean_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def _cleanliness_penalty(text: str) -> int:
    raw = str(text or "")
    if not raw.strip():
        return 10
    compact = _clean_text(raw)
    lower = raw.lower()
    extra_ws = max(0, len(raw.strip()) - len(compact))
    code_fences = raw.count("```")
    blank_runs = raw.count("\n\n")
    noisy_tokens = len(re.findall(r"\b(?:todo|fixme|placeholder)\b", lower))
    ellipsis = 1 if raw.strip().endswith("...") else 0
    return (6 * code_fences) + (2 * blank_runs) + (3 * noisy_tokens) + min(extra_ws, 12) + ellipsis


_EPS = 1.0e-12


def _is_signature_mismatch_typeerror(exc: TypeError) -> bool:
    msg = str(exc or "")
    return (
        ("unexpected keyword argument" in msg)
        or ("positional arguments but" in msg and "were given" in msg)
        or ("required positional argument" in msg)
    )


class SwarmManager:
    """
    SwarmManager (Phase 4–9 compatible + Cycle 2/3 mode support)

    GUARANTEES:
    - `run(...)` exists and returns {"best": ..., "candidates": [...]}.
    - v1/v2 legacy behavior preserved.
    - v3 adds Pareto-based selection with adaptive budget weighting.
    """

    def __init__(
        self,
        router_or_agents: Union[MetaRouter, List[Any]],
        oracle: Optional[OracleVerifier] = None,
        fusion_mode: Optional[str] = None,
        *,
        mode: str = "v1",
        seed: int = 0,
    ) -> None:
        self.router: Optional[MetaRouter] = None
        self._agents_override: Optional[List[Any]] = None

        if isinstance(router_or_agents, list):
            self._agents_override = router_or_agents
        else:
            self.router = router_or_agents

        self.oracle = oracle
        self.fusion_mode = fusion_mode
        self.mode = (mode or "v1").strip().lower()
        self.seed = int(seed)

        # Optional Phase 7/8 wiring (non-breaking)
        self.sgm = SharedGeometricManifold() if SharedGeometricManifold else None
        self.energy_fusion = EnergyFusion(self.sgm) if (EnergyFusion and self.sgm) else None

    # -----------------------------
    # Oracle helper
    # -----------------------------
    def _oracle_block(
        self,
        prompt: str,
        text: str,
        *,
        answer_metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.oracle is None:
            return {"score": 0.5, "reason": "no oracle", "meta": {}}

        if hasattr(self.oracle, "verdict"):
            if answer_metadata is None:
                v = self.oracle.verdict(prompt, text)  # type: ignore[attr-defined]
            else:
                try:
                    v = self.oracle.verdict(prompt, text, answer_metadata=answer_metadata)  # type: ignore[attr-defined]
                except TypeError as exc:
                    if "answer_metadata" in str(exc):
                        v = self.oracle.verdict(prompt, text)  # type: ignore[attr-defined]
                    else:
                        raise
            return {
                "score": float(getattr(v, "score", 0.5)),
                "reason": getattr(v, "reason", ""),
                "meta": getattr(v, "meta", {}) or {},
            }

        if answer_metadata is None:
            return {"score": float(self.oracle.score(prompt, text)), "reason": "", "meta": {}}

        try:
            score = float(self.oracle.score(prompt, text, answer_metadata=answer_metadata))
        except TypeError as exc:
            if "answer_metadata" in str(exc):
                score = float(self.oracle.score(prompt, text))
            else:
                raise
        return {"score": score, "reason": "", "meta": {}}

    def _build_router_trace(
        self,
        decisions: List[Any],
        chosen_mode: str,
        *,
        prompt: str = "",
        task_metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        fallback_intent = analyze_prompt_intent(prompt, task_metadata=task_metadata)
        intent = fallback_intent.intent
        matched_features = list(fallback_intent.matched_features)
        intent_scores: Dict[str, float] = {k: float(v) for k, v in fallback_intent.scores.items()}

        ranked: List[Dict[str, Any]] = []
        for idx, d in enumerate(decisions):
            comps = getattr(d, "components", {}) or {}
            if idx == 0:
                raw_intent = getattr(d, "intent", None)
                if isinstance(raw_intent, str) and raw_intent.strip():
                    intent = raw_intent.strip().lower()
                raw_features = getattr(d, "matched_features", ())
                if isinstance(raw_features, (list, tuple)):
                    matched_features = [str(x) for x in raw_features if str(x).strip()]
                raw_scores = getattr(d, "intent_scores", {})
                if isinstance(raw_scores, Mapping):
                    intent_scores = {str(k): float(v) for k, v in raw_scores.items()}
            ranked.append(
                {
                    "agent": getattr(d, "agent_name", ""),
                    "score": float(getattr(d, "score", 0.0)),
                    "expected_utility": float(getattr(d, "expected_utility", getattr(d, "score", 0.0))),
                    "exploration_probability": float(getattr(d, "exploration_probability", 0.0)),
                    "selected_by_exploration": bool(getattr(d, "selected_by_exploration", False)),
                    "reason": getattr(d, "reason", ""),
                    "rationale": getattr(d, "rationale", ""),
                    "components": comps,
                }
            )

        exploration_probability = 0.0
        if ranked:
            exploration_probability = float(ranked[0].get("exploration_probability", 0.0))

        chosen_agent = ranked[0]["agent"] if ranked else ""
        alternatives = [
            {
                "agent": r["agent"],
                "score": float(r["score"]),
                "reason": r["reason"],
                "rationale": r["rationale"],
            }
            for r in ranked[1:]
        ]

        return {
            "mode": chosen_mode,
            "ranked": ranked,
            "exploration_probability": exploration_probability,
            "intent": intent,
            "intent_scores": intent_scores,
            "intent_confidence": float(intent_confidence_score(intent_scores, intent)),
            "matched_features": matched_features,
            "chosen_agent": chosen_agent,
            "alternatives": alternatives,
            "ranking_rationale": "ranked by router decision score (desc), then deterministic agent-name order",
        }

    # -----------------------------
    # Internal: get candidate agents
    # -----------------------------
    def _get_agents_and_decisions(
        self,
        prompt: str,
        top_k: int,
        *,
        task_metadata: Optional[Mapping[str, Any]] = None,
        memory_hints: Optional[Mapping[str, Any]] = None,
        budget: Optional[Mapping[str, Any]] = None,
        history_stats: Optional[Mapping[str, Any]] = None,
        budget_mode: Optional[str] = None,
    ) -> tuple[List[Any], List[Any]]:
        if self.router is not None:
            # RouterV3/RouterV2 supports richer kwargs; MetaRouter only accepts prompt/k.
            try:
                agents, decisions = self.router.route_top_k(  # type: ignore[misc]
                    prompt,
                    k=top_k,
                    task_metadata=task_metadata,
                    memory_hints=memory_hints,
                    budget=budget,
                    history_stats=history_stats,
                    budget_mode=budget_mode,
                )
                return list(agents), list(decisions)
            except TypeError as exc:
                if not _is_signature_mismatch_typeerror(exc):
                    raise
                try:
                    agents, decisions = self.router.route_top_k(  # type: ignore[misc]
                        prompt,
                        k=top_k,
                        task_metadata=task_metadata,
                        memory_hints=memory_hints,
                        budget=budget,
                        history_stats=history_stats,
                    )
                    return list(agents), list(decisions)
                except TypeError as nested_exc:
                    if not _is_signature_mismatch_typeerror(nested_exc):
                        raise
                    agents, decisions = self.router.route_top_k(prompt, k=top_k)
                    return list(agents), list(decisions)

        if self._agents_override is not None:
            agents = list(self._agents_override)
            decisions: List[Dict[str, Any]] = []
            for idx, a in enumerate(agents[:top_k]):
                name = getattr(getattr(a, "contract", None), "name", getattr(a, "name", f"agent-{idx}"))
                decisions.append(
                    {
                        "agent_name": str(name),
                        "score": float(1.0 - (idx * 0.01)),
                        "reason": "agents_override",
                    }
                )
            return agents[:top_k], decisions

        return [], []

    def _candidate_prompt(self, prompt: str, agent: Any, round_idx: int, mode: str) -> str:
        if mode == "v1":
            return prompt

        contract = getattr(agent, "contract", None)
        domains = getattr(contract, "domains", []) if contract is not None else []
        domain_hint = ",".join(str(d) for d in domains) if domains else "general"

        if mode == "v3":
            return f"{prompt}\n[agent_domain={domain_hint}; round={round_idx + 1}; style=deliberative]"

        return f"{prompt}\n[agent_domain={domain_hint}; round={round_idx + 1}]"

    def _v3_round_policy(self, budget_mode: str) -> Dict[str, float]:
        profile_map = {
            "cheap": {
                "prune_score": 0.82,
                "prune_margin": 0.05,
                "min_improvement": 0.010,
                "stop_score_floor": 0.76,
            },
            "balanced": {
                "prune_score": 0.85,
                "prune_margin": 0.06,
                "min_improvement": 0.008,
                "stop_score_floor": 0.80,
            },
            "max_quality": {
                "prune_score": 0.92,
                "prune_margin": 0.12,
                "min_improvement": 0.006,
                "stop_score_floor": 0.88,
            },
        }
        return dict(profile_map.get(budget_mode, profile_map["balanced"]))

    def _build_candidate(
        self,
        *,
        agent: Any,
        prompt: str,
        task_id: str,
        round_idx: int,
        rank_idx: int,
        mode: str,
        budget_mode: str = "balanced",
    ) -> Dict[str, Any]:
        call_prompt = self._candidate_prompt(prompt, agent, round_idx, mode)

        try:
            result = agent.handle(call_prompt, task_id=task_id)
        except TypeError as exc:
            if not _is_signature_mismatch_typeerror(exc):
                raise
            result = agent.handle(call_prompt)

        text = getattr(result, "text", str(result))
        agent_name = getattr(result, "agent_name", getattr(agent, "name", "agent"))
        meta = getattr(result, "meta", {}) or {}

        oracle_block = self._oracle_block(prompt, text, answer_metadata=meta if isinstance(meta, Mapping) else None)

        token_count = max(1, len(str(text).split()))
        contract = getattr(agent, "contract", None)
        cost_prior = float(getattr(contract, "cost_prior", 0.3) or 0.3)

        base_latency = float(40 + (4 * token_count) + (8 * rank_idx) + (3 * round_idx) + int(20 * cost_prior))
        budget_latency_scale = {
            "cheap": 0.90,
            "balanced": 1.00,
            "max_quality": 1.06,
        }.get(str(budget_mode or "balanced").strip().lower(), 1.00)
        latency_proxy = float(base_latency * budget_latency_scale)
        cost_proxy = float(16 + token_count + int(42 * cost_prior))

        grounding = float((((oracle_block.get("meta", {}) or {}).get("components", {}) or {}).get("grounding", oracle_block["score"])))
        confidence_proxy = _clamp((0.65 * float(oracle_block["score"])) + (0.35 * grounding), 0.0, 1.0)
        tool_verification = self._extract_tool_verification(
            candidate_meta=meta if isinstance(meta, Mapping) else None,
            oracle_meta=_coerce_mapping(oracle_block.get("meta")),
        )

        return {
            "agent": str(agent_name),
            "text": str(text),
            "meta": meta,
            "oracle": oracle_block,
            "round": int(round_idx + 1),
            "rank": int(rank_idx),
            "latency_proxy": latency_proxy,
            "cost_proxy": cost_proxy,
            "confidence_proxy": confidence_proxy,
            "tool_verified": bool(tool_verification.get("passed", False)),
            "tool_verification": dict(tool_verification),
        }

    def _extract_tool_verification(
        self,
        *,
        candidate_meta: Optional[Mapping[str, Any]],
        oracle_meta: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        signal = _coerce_mapping(_coerce_mapping(oracle_meta).get("verification_signal"))
        if signal:
            status = str(signal.get("status", "") or "").strip().lower()
            passed_raw = signal.get("passed")
            if isinstance(passed_raw, bool):
                passed = passed_raw
            else:
                passed = status == "pass"
            if status not in {"pass", "fail"}:
                status = "pass" if passed else "fail"
            attempted = True
            return {
                "status": status,
                "attempted": attempted,
                "passed": bool(passed),
                "stage": str(signal.get("stage", "") or ""),
                "exec_ran": bool(signal.get("exec_ran", False)),
                "source": "oracle.verification_signal",
            }

        tool_meta = _coerce_mapping(_coerce_mapping(candidate_meta).get("tool_first"))
        verification = _coerce_mapping(tool_meta.get("verification"))
        if verification:
            status = str(verification.get("status", "") or "").strip().lower()
            passed_raw = verification.get("passed")
            if isinstance(passed_raw, bool):
                passed = passed_raw
            elif status:
                passed = status == "pass"
            else:
                passed = False
            if status not in {"pass", "fail"}:
                status = "pass" if passed else "fail"
            return {
                "status": status,
                "attempted": True,
                "passed": bool(passed),
                "stage": str(verification.get("stage", "") or ""),
                "exec_ran": bool(verification.get("exec_ran", False)),
                "source": "meta.tool_first.verification",
            }

        attempted = _coerce_bool(tool_meta.get("attempted", False))
        success_raw = tool_meta.get("success")
        success_known = success_raw is not None
        passed = bool(success_raw is True)
        attempted = bool(attempted or success_known or passed)
        status = "unknown"
        if success_known:
            status = "pass" if passed else "fail"

        return {
            "status": status,
            "attempted": attempted,
            "passed": bool(passed),
            "stage": "",
            "exec_ran": False,
            "source": "meta.tool_first",
        }

    def _candidate_tool_verification(self, candidate: Mapping[str, Any]) -> Dict[str, Any]:
        block = _coerce_mapping(candidate.get("tool_verification"))
        if block:
            status = str(block.get("status", "") or "").strip().lower()
            passed = bool(block.get("passed", False))
            attempted = bool(block.get("attempted", False) or passed)
            if status not in {"pass", "fail", "unknown"}:
                status = "pass" if passed else "unknown"
            return {
                "status": status,
                "attempted": attempted,
                "passed": passed,
                "stage": str(block.get("stage", "") or ""),
                "exec_ran": bool(block.get("exec_ran", False)),
                "source": str(block.get("source", "") or "candidate.tool_verification"),
            }

        oracle_meta = _coerce_mapping(_coerce_mapping(candidate.get("oracle")).get("meta"))
        candidate_meta = _coerce_mapping(candidate.get("meta"))
        return self._extract_tool_verification(candidate_meta=candidate_meta, oracle_meta=oracle_meta)

    def _is_tool_verified(self, candidate: Mapping[str, Any]) -> bool:
        raw = candidate.get("tool_verified", None)
        if raw is not None:
            return bool(_coerce_bool(raw))
        return bool(self._candidate_tool_verification(candidate).get("passed", False))

    def _oracle_score(self, candidate: Mapping[str, Any]) -> float:
        return float(_coerce_mapping(candidate.get("oracle")).get("score", 0.0))

    def _fallback_key(self, candidate: Mapping[str, Any], *, index: int) -> tuple[int, int, str, int]:
        text = str(candidate.get("text", ""))
        clean = _clean_text(text)
        label = str(candidate.get("agent", ""))
        return (
            _cleanliness_penalty(text),
            len(clean),
            label,
            int(index),
        )

    def _select_by_tool_verified_oracle_fallback(
        self,
        candidates: List[Dict[str, Any]],
    ) -> tuple[Dict[str, Any], str]:
        if not candidates:
            raise ValueError("candidates must not be empty")

        ordered = list(candidates)
        verified = [c for c in ordered if self._is_tool_verified(c)]
        pool = verified if verified else ordered
        pool_reason = "tool-verified" if verified else "oracle-score"

        best_score = max(self._oracle_score(c) for c in pool)
        top = [c for c in pool if abs(self._oracle_score(c) - best_score) <= _EPS]
        if len(top) == 1:
            return top[0], pool_reason

        index_by_object = {id(candidate): idx for idx, candidate in enumerate(ordered)}
        winner = min(
            top,
            key=lambda c: self._fallback_key(c, index=index_by_object.get(id(c), 0)),
        )
        return winner, "fallback-shorter-cleaner"

    def _aggregate_tool_verification(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = int(len(candidates))
        if total <= 0:
            return {
                "total_candidates": 0,
                "attempted_candidates": 0,
                "verified_candidates": 0,
                "failed_candidates": 0,
                "verification_rate": 0.0,
                "attempt_rate": 0.0,
                "pass_rate_given_attempted": 0.0,
            }

        attempted = 0
        verified = 0
        failed = 0

        for candidate in candidates:
            verification = self._candidate_tool_verification(candidate)
            passed = bool(verification.get("passed", False))
            attempted_flag = bool(verification.get("attempted", False) or passed)
            status = str(verification.get("status", "") or "").strip().lower()

            if attempted_flag:
                attempted += 1
            if passed:
                verified += 1
            if attempted_flag and (status == "fail" or (not passed and status != "unknown")):
                failed += 1

        return {
            "total_candidates": total,
            "attempted_candidates": int(attempted),
            "verified_candidates": int(verified),
            "failed_candidates": int(failed),
            "verification_rate": float(verified / float(total)),
            "attempt_rate": float(attempted / float(total)),
            "pass_rate_given_attempted": float((verified / float(attempted)) if attempted > 0 else 0.0),
        }

    def _apply_cross_critique(self, candidates: List[Dict[str, Any]], *, enabled: bool) -> Dict[str, Any]:
        if not enabled:
            return {"enabled": False, "status": "disabled"}
        if len(candidates) < 2:
            return {"enabled": True, "status": "insufficient-candidates"}

        ranked = sorted(candidates, key=lambda c: float((c.get("oracle", {}) or {}).get("score", 0.0)), reverse=True)
        c1 = ranked[0]
        c2 = ranked[1]

        note_1 = f"Critique against {c2['agent']}: strengthen grounding and constraints."
        note_2 = f"Critique against {c1['agent']}: improve directness and correctness."

        c1["critique"] = note_1
        c2["critique"] = note_2

        c1["confidence_proxy"] = _clamp(float(c1.get("confidence_proxy", 0.5)) + 0.02, 0.0, 1.0)
        c2["confidence_proxy"] = _clamp(float(c2.get("confidence_proxy", 0.5)) + 0.01, 0.0, 1.0)

        return {
            "enabled": True,
            "status": "top2-critique-applied",
            "candidate_a": c1["agent"],
            "candidate_b": c2["agent"],
        }

    def _select_best_legacy(self, candidates: List[Dict[str, Any]], *, cross_check: bool = False) -> tuple[Dict[str, Any], float, Dict[str, Any]]:
        if not candidates:
            return (
                {
                    "agent": "",
                    "text": "",
                    "meta": {},
                    "oracle": {"score": 0.0, "reason": "no candidates", "meta": {}},
                    "round": 0,
                    "rank": 0,
                    "latency_proxy": 0.0,
                    "cost_proxy": 0.0,
                    "confidence_proxy": 0.0,
                    "tool_verified": False,
                    "tool_verification": {
                        "status": "unknown",
                        "attempted": False,
                        "passed": False,
                        "stage": "",
                        "exec_ran": False,
                        "source": "none",
                    },
                },
                0.0,
                {"enabled": cross_check, "status": "no-candidates"},
            )

        ranked = sorted(candidates, key=lambda c: float((c.get("oracle", {}) or {}).get("score", 0.0)), reverse=True)
        best = ranked[0]

        second_score = float((ranked[1].get("oracle", {}) or {}).get("score", 0.0)) if len(ranked) > 1 else float((best.get("oracle", {}) or {}).get("score", 0.0))
        margin = _clamp(float((best.get("oracle", {}) or {}).get("score", 0.0)) - second_score, 0.0, 1.0)

        values = [float((c.get("oracle", {}) or {}).get("score", 0.0)) for c in ranked]
        dispersion = float(statistics.pstdev(values)) if len(values) > 1 else 0.0
        confidence = _clamp(0.55 + (0.35 * margin) + (0.10 * (1.0 - dispersion)), 0.0, 1.0)

        cross_meta: Dict[str, Any] = {"enabled": bool(cross_check), "status": "disabled"}
        if cross_check and len(ranked) > 1:
            c1 = ranked[0]
            c2 = ranked[1]
            c1_components = ((c1.get("oracle", {}) or {}).get("meta", {}) or {}).get("components", {}) or {}
            c2_components = ((c2.get("oracle", {}) or {}).get("meta", {}) or {}).get("components", {}) or {}
            c1_ground = float(c1_components.get("grounding", 0.0))
            c2_ground = float(c2_components.get("grounding", 0.0))
            winner = c1 if c1_ground >= c2_ground else c2
            best = winner
            confidence = _clamp(confidence + 0.03, 0.0, 1.0)
            cross_meta = {
                "enabled": True,
                "status": "top2_stubbed",
                "candidate_a": c1["agent"],
                "candidate_b": c2["agent"],
                "winner": best["agent"],
                "grounding_a": c1_ground,
                "grounding_b": c2_ground,
            }

        return best, confidence, cross_meta

    def _select_best_v3(self, candidates: List[Dict[str, Any]], *, budget_mode: str) -> tuple[Dict[str, Any], float, Dict[str, Any]]:
        if not candidates:
            return (
                {
                    "agent": "",
                    "text": "",
                    "meta": {},
                    "oracle": {"score": 0.0, "reason": "no candidates", "meta": {}},
                    "round": 0,
                    "rank": 0,
                    "latency_proxy": 0.0,
                    "cost_proxy": 0.0,
                    "confidence_proxy": 0.0,
                    "tool_verified": False,
                    "tool_verification": {
                        "status": "unknown",
                        "attempted": False,
                        "passed": False,
                        "stage": "",
                        "exec_ran": False,
                        "source": "none",
                    },
                },
                0.0,
                {"enabled": True, "status": "no-candidates", "frontier": []},
            )

        profile_map = {
            "cheap": {"score": 0.45, "confidence": 0.10, "latency": 0.20, "cost": 0.25},
            "balanced": {"score": 0.60, "confidence": 0.15, "latency": 0.13, "cost": 0.12},
            "max_quality": {"score": 0.78, "confidence": 0.18, "latency": 0.02, "cost": 0.02},
        }
        profile = profile_map.get(budget_mode, profile_map["balanced"])

        max_latency = max(float(c.get("latency_proxy", 0.0)) for c in candidates)
        max_cost = max(float(c.get("cost_proxy", 0.0)) for c in candidates)
        max_latency = max(1.0, max_latency)
        max_cost = max(1.0, max_cost)

        points = []
        for idx, c in enumerate(candidates):
            points.append(
                {
                    "id": float(idx),
                    "score": float((c.get("oracle", {}) or {}).get("score", 0.0)),
                    "confidence": float(c.get("confidence_proxy", 0.5)),
                    "latency": float(c.get("latency_proxy", 0.0)),
                    "cost": float(c.get("cost_proxy", 0.0)),
                }
            )

        frontier = pareto_frontier(points)
        frontier_ids = [int(p.get("id", 0.0)) for p in frontier]
        frontier_candidates = [candidates[i] for i in frontier_ids if 0 <= i < len(candidates)]
        if not frontier_candidates:
            frontier_candidates = list(candidates)

        def _utility(c: Dict[str, Any]) -> float:
            score = float((c.get("oracle", {}) or {}).get("score", 0.0))
            conf = float(c.get("confidence_proxy", 0.5))
            lat_eff = _clamp(1.0 - (float(c.get("latency_proxy", 0.0)) / max_latency), 0.0, 1.0)
            cost_eff = _clamp(1.0 - (float(c.get("cost_proxy", 0.0)) / max_cost), 0.0, 1.0)
            return _clamp(
                (profile["score"] * score)
                + (profile["confidence"] * conf)
                + (profile["latency"] * lat_eff)
                + (profile["cost"] * cost_eff),
                0.0,
                1.0,
            )

        global_verified = [c for c in candidates if self._is_tool_verified(c)]
        if global_verified:
            selection_pool = list(global_verified)
            selector_scope = "global-tool-verified"
        else:
            selection_pool = list(frontier_candidates)
            selector_scope = "pareto-frontier"

        best, selector_rule = self._select_by_tool_verified_oracle_fallback(selection_pool)
        confidence = _clamp(float(best.get("confidence_proxy", 0.5)), 0.0, 1.0)

        frontier_meta = [
            {
                "agent": c.get("agent", ""),
                "score": float((c.get("oracle", {}) or {}).get("score", 0.0)),
                "confidence": float(c.get("confidence_proxy", 0.0)),
                "latency": float(c.get("latency_proxy", 0.0)),
                "cost": float(c.get("cost_proxy", 0.0)),
                "tool_verified": bool(self._is_tool_verified(c)),
                "utility": float(_utility(c)),
            }
            for c in frontier_candidates
        ]

        return best, confidence, {
            "enabled": True,
            "status": "pareto-selected",
            "budget_mode": budget_mode,
            "profile": profile,
            "selector": {
                "rule": selector_rule,
                "scope": selector_scope,
                "pool_size": int(len(selection_pool)),
            },
            "frontier": frontier_meta,
        }

    def _aggregate_proxies(self, candidates: List[Dict[str, Any]]) -> Dict[str, float]:
        if not candidates:
            return {"avg_latency_proxy": 0.0, "avg_cost_proxy": 0.0}

        avg_latency = sum(float(c.get("latency_proxy", 0.0)) for c in candidates) / float(len(candidates))
        avg_cost = sum(float(c.get("cost_proxy", 0.0)) for c in candidates) / float(len(candidates))
        return {
            "avg_latency_proxy": float(avg_latency),
            "avg_cost_proxy": float(avg_cost),
        }

    # -----------------------------
    # Phase 4 main API (must exist)
    # -----------------------------
    def run(
        self,
        prompt: str,
        task_id: str = "default",
        rounds: int = 2,
        top_k: int = 2,
        *,
        mode: Optional[str] = None,
        task_metadata: Optional[Mapping[str, Any]] = None,
        memory_hints: Optional[Mapping[str, Any]] = None,
        budget: Optional[Mapping[str, Any]] = None,
        history_stats: Optional[Mapping[str, Any]] = None,
        cross_check: bool = False,
    ) -> Dict[str, Any]:
        chosen_mode = (mode or self.mode or "v1").strip().lower()
        if chosen_mode not in {"v1", "v2", "v3"}:
            chosen_mode = "v1"

        budget_mode = "balanced"
        if isinstance(budget, Mapping):
            maybe_mode = str(budget.get("mode", "") or "").strip().lower()
            if maybe_mode in {"cheap", "balanced", "max_quality"}:
                budget_mode = maybe_mode

        agents, decisions = self._get_agents_and_decisions(
            prompt,
            top_k=top_k,
            task_metadata=task_metadata,
            memory_hints=memory_hints,
            budget=budget,
            history_stats=history_stats,
            budget_mode=budget_mode,
        )

        requested_rounds = int(max(1, rounds))
        requested_top_k = int(max(1, top_k))
        round_policy = self._v3_round_policy(budget_mode) if chosen_mode == "v3" else {}

        candidates: List[Dict[str, Any]] = []
        active_agents = list(agents)
        executed_rounds = 0
        stopped_early = False
        stop_reason = "requested-rounds-complete"
        pruned_to_top1_round: Optional[int] = None
        best_score_so_far: Optional[float] = None

        for round_idx in range(requested_rounds):
            if not active_agents:
                stop_reason = "no-active-agents"
                break

            round_agents = list(active_agents)
            round_candidates: List[Dict[str, Any]] = []
            for rank_idx, agent in enumerate(round_agents):
                candidate = self._build_candidate(
                    agent=agent,
                    prompt=prompt,
                    task_id=task_id,
                    round_idx=round_idx,
                    rank_idx=rank_idx,
                    mode=chosen_mode,
                    budget_mode=budget_mode,
                )
                candidates.append(candidate)
                round_candidates.append(candidate)

            executed_rounds = int(round_idx + 1)

            if chosen_mode != "v3" or requested_rounds <= 1:
                continue

            round_ranked = sorted(round_candidates, key=self._oracle_score, reverse=True)
            round_best = round_ranked[0]
            round_best_score = self._oracle_score(round_best)
            round_second_score = self._oracle_score(round_ranked[1]) if len(round_ranked) > 1 else round_best_score
            round_margin = _clamp(round_best_score - round_second_score, 0.0, 1.0)

            improvement = None if best_score_so_far is None else float(round_best_score - best_score_so_far)
            if best_score_so_far is None or round_best_score > best_score_so_far:
                best_score_so_far = float(round_best_score)

            if round_idx + 1 >= requested_rounds:
                continue

            if len(round_agents) > 1:
                prune_score = float(round_policy.get("prune_score", 1.01))
                prune_margin = float(round_policy.get("prune_margin", 1.01))
                if round_best_score >= prune_score and round_margin >= prune_margin:
                    winner_local_idx = round_candidates.index(round_best)
                    active_agents = [round_agents[winner_local_idx]]
                    if pruned_to_top1_round is None:
                        pruned_to_top1_round = int(round_idx + 1)
                else:
                    active_agents = list(round_agents)

            min_improvement = float(round_policy.get("min_improvement", -1.0))
            stop_score_floor = float(round_policy.get("stop_score_floor", 1.01))
            if (
                round_idx >= 1
                and improvement is not None
                and improvement <= min_improvement
                and round_best_score >= stop_score_floor
            ):
                stopped_early = True
                stop_reason = "diminishing-returns"
                break

        cross_meta = {"enabled": False, "status": "disabled"}
        pareto_meta = {"enabled": False, "status": "not-used", "frontier": []}
        tool_verification_meta = self._aggregate_tool_verification(candidates)

        if chosen_mode == "v3":
            cross_meta = self._apply_cross_critique(candidates, enabled=bool(cross_check))
            best, confidence, pareto_meta = self._select_best_v3(candidates, budget_mode=budget_mode)
        else:
            best, confidence, cross_meta = self._select_best_legacy(
                candidates,
                cross_check=(chosen_mode == "v2" and bool(cross_check)),
            )

        aggregates = self._aggregate_proxies(candidates)

        trace = {
            "router": self._build_router_trace(
                decisions,
                chosen_mode,
                prompt=prompt,
                task_metadata=task_metadata,
            ),
            "swarm": {
                "mode": chosen_mode,
                "rounds": int(requested_rounds),
                "rounds_executed": int(executed_rounds),
                "top_k": int(requested_top_k),
                "num_candidates": int(len(candidates)),
                "cross_check": cross_meta,
                "pareto": pareto_meta,
                "budget_mode": budget_mode,
                "tool_verification": tool_verification_meta,
                "tool_verification_rate": float(tool_verification_meta.get("verification_rate", 0.0)),
                "round_control": {
                    "stopped_early": bool(stopped_early),
                    "stop_reason": str(stop_reason),
                    "pruned_to_top1_round": int(pruned_to_top1_round or 0),
                },
            },
            "oracle": {
                "mode": "oracle_v2" if chosen_mode in {"v2", "v3"} else "oracle_v1",
                "scores": [
                    {
                        "agent": c["agent"],
                        "score": float((c.get("oracle", {}) or {}).get("score", 0.0)),
                        "reason": (c.get("oracle", {}) or {}).get("reason", ""),
                        "components": ((c.get("oracle", {}) or {}).get("meta", {}) or {}).get("components", {}),
                        "tool_verified": bool(self._is_tool_verified(c)),
                        "tool_verification": self._candidate_tool_verification(c),
                        "verification_signal": ((c.get("oracle", {}) or {}).get("meta", {}) or {}).get("verification_signal", {}),
                    }
                    for c in candidates
                ],
            },
            "final": {
                "agent": best.get("agent", ""),
                "score": float((best.get("oracle", {}) or {}).get("score", 0.0)),
                "confidence": float(confidence),
                "budget_mode": budget_mode,
                "tool_verified": bool(self._is_tool_verified(best)),
            },
        }

        if not candidates:
            return {
                "best": best,
                "candidates": [],
                "confidence": float(confidence),
                "trace": trace,
                "mode": chosen_mode,
                "tool_verification_rate": float(tool_verification_meta.get("verification_rate", 0.0)),
                **aggregates,
            }

        return {
            "best": best,
            "candidates": candidates,
            "confidence": float(confidence),
            "trace": trace,
            "mode": chosen_mode,
            "tool_verification_rate": float(tool_verification_meta.get("verification_rate", 0.0)),
            **aggregates,
        }

    # -----------------------------
    # Phase 8 experimental API (optional)
    # -----------------------------
    def deliberate(self, prompt: str, rounds: int = 2) -> str:
        """
        Experimental: return only the chosen text.
        Does NOT replace Phase 4 contract; `run()` remains canonical.
        """
        out = self.run(prompt=prompt, task_id="default", rounds=rounds, top_k=2)
        candidates = [c["text"] for c in out.get("candidates", [])]

        if not candidates:
            return ""

        if self.fusion_mode == "energy" and self.energy_fusion and self.oracle:
            pick = self.energy_fusion.pick(prompt, candidates, oracle_score=self.oracle.score)
            return pick.text

        best = out.get("best", {})
        if isinstance(best, dict):
            return str(best.get("text", ""))

        if self.oracle:
            return max(candidates, key=lambda c: float(self.oracle.score(prompt, c)))

        return candidates[0]
