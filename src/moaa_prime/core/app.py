from __future__ import annotations

from typing import Any, Dict, Optional

from moaa_prime.agents import CodeAgent, MathAgent
from moaa_prime.contracts import Contract
from moaa_prime.router import MetaRouter

try:
    from moaa_prime.oracle.verifier import OracleVerifier
except Exception:  # pragma: no cover
    OracleVerifier = None  # type: ignore

try:
    from moaa_prime.swarm.manager import SwarmManager
except Exception:  # pragma: no cover
    SwarmManager = None  # type: ignore

try:
    from moaa_prime.memory import ReasoningBank
except Exception:  # pragma: no cover
    ReasoningBank = None  # type: ignore


class MoAAPrime:
    """
    Phase status:
    - Phase 1: packaging + hello
    - Phase 2: routing
    - Phase 3: oracle
    - Phase 4: swarm
    - Phase 5: memory (ReasoningBank)
    """

    def __init__(self) -> None:
        self.bank = ReasoningBank() if ReasoningBank is not None else None

        self.math = MathAgent(
            Contract(name="math-agent", domains=["math"], competence=0.80, tools=["sympy"]),
            bank=self.bank,
        )
        self.code = CodeAgent(
            Contract(name="code-agent", domains=["code"], competence=0.78, tools=["exec"]),
            bank=self.bank,
        )

        self.router = MetaRouter([self.math, self.code])

        self.oracle = OracleVerifier() if OracleVerifier is not None else None
        self.swarm = SwarmManager(self.router, oracle=self.oracle) if SwarmManager is not None else None

    def hello(self) -> str:
        return "moaa-prime says hello"

    def run_once(self, prompt: str, task_id: str = "default") -> dict:
        agent, decision = self.router.route(prompt)
        result = agent.handle(prompt, task_id=task_id)

        out: Dict[str, Any] = {
            "decision": {
                "agent": decision.agent_name,
                "score": decision.score,
                "reason": decision.reason,
            },
            "result": {
                "agent": result.agent_name,
                "text": result.text,
                "meta": result.meta or {},
            },
        }

        # Phase 3 contract: ALWAYS include "oracle" key (tests expect it).
        if self.oracle is not None:
            try:
                score = float(self.oracle.score(prompt, result.text))  # type: ignore[attr-defined]
            except Exception:
                score = 0.0
            out["oracle"] = {"score": score}
        else:
            out["oracle"] = {"score": None}

        return out

    def run_swarm(self, prompt: str, task_id: str = "default", rounds: int = 3, top_k: int = 2) -> dict:
        if self.swarm is None:
            raise RuntimeError("SwarmManager not available")
        return self.swarm.run(prompt=prompt, task_id=task_id, rounds=rounds, top_k=top_k)
