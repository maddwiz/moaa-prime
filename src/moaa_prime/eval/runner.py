from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, List

from moaa_prime.core.app import MoAAPrime
from moaa_prime.schema import upgrade_answer_object


@dataclass
class EvalCase:
    case_id: str
    prompt: str
    mode: str = "once"  # "once" or "swarm"


@dataclass
class EvalResult:
    case_id: str
    mode: str
    output: Dict[str, Any]
    oracle_score: float
    routing_entropy: float
    cost_proxy: float
    latency_proxy: float


class EvalRunner:
    def __init__(self, *, model_mode: str = "v1", seed: int = 0) -> None:
        self.model_mode = (model_mode or "v1").strip().lower()
        self.app = MoAAPrime(mode=self.model_mode, seed=seed)

    def _routing_entropy(self, output: Dict[str, Any]) -> float:
        ranked = ((output.get("trace", {}) or {}).get("router", {}) or {}).get("ranked", [])
        if not ranked:
            return 0.0

        scores = [float(r.get("score", 0.0)) for r in ranked]
        if not scores:
            return 0.0

        # Softmax probabilities for a stable entropy proxy.
        max_s = max(scores)
        exps = [math.exp(s - max_s) for s in scores]
        denom = sum(exps)
        if denom <= 0:
            return 0.0
        probs = [v / denom for v in exps]

        entropy = 0.0
        for p in probs:
            if p > 0:
                entropy -= p * math.log(p, 2)
        return float(entropy)

    def _summarize_metrics(self, mode: str, output: Dict[str, Any]) -> tuple[float, float, float, float]:
        if mode == "swarm":
            oracle_score = float(((output.get("best", {}) or {}).get("oracle", {}) or {}).get("score", 0.0))
            routing_entropy = self._routing_entropy(output)
            cost_proxy = float(output.get("avg_cost_proxy", 0.0))
            latency_proxy = float(output.get("avg_latency_proxy", 0.0))
            return oracle_score, routing_entropy, cost_proxy, latency_proxy

        oracle_score = float((output.get("oracle", {}) or {}).get("score", 0.0))
        text = str(((output.get("result", {}) or {}).get("text", "")))
        token_count = max(1, len(text.split()))
        cost_proxy = float(8 + token_count)
        latency_proxy = float(24 + (3 * token_count))
        return oracle_score, 0.0, cost_proxy, latency_proxy

    def run(self, cases: List[EvalCase]) -> List[EvalResult]:
        results: List[EvalResult] = []
        for c in cases:
            if c.mode == "swarm":
                out = self.app.run_swarm(c.prompt, mode=self.model_mode)
            else:
                out = self.app.run_once(c.prompt, mode=self.model_mode)
            out = upgrade_answer_object(out)

            oracle_score, routing_entropy, cost_proxy, latency_proxy = self._summarize_metrics(c.mode, out)
            results.append(
                EvalResult(
                    case_id=c.case_id,
                    mode=c.mode,
                    output=out,
                    oracle_score=oracle_score,
                    routing_entropy=routing_entropy,
                    cost_proxy=cost_proxy,
                    latency_proxy=latency_proxy,
                )
            )
        return results
