from __future__ import annotations

from typing import Any, Dict, Optional

from moaa_prime.agents import CodeAgent, MathAgent
from moaa_prime.contracts import Contract
from moaa_prime.router import MetaRouter

from moaa_prime.oracle.verifier import OracleVerifier
from moaa_prime.swarm.manager import SwarmManager

from moaa_prime.memory import ReasoningBank

from moaa_prime.evolution.gcel import GCEL


class MoAAPrime:
    """
    MoAA-Prime app object.

    IMPORTANT:
    This file must remain backward-compatible with Phase 1–10 tests.
    Phase 11 adds GCEL WITHOUT removing earlier features.
    """

    def __init__(self) -> None:
        # Phase 5+: global memory bank
        self.bank = ReasoningBank()

        # Phase 2: contracts
        self.math_contract = Contract(name="math-agent", domains=["math"], competence=0.80, tools=["sympy"])
        self.code_contract = Contract(name="code-agent", domains=["code"], competence=0.78, tools=["exec"])

        # Phase 2: agents (wired to bank)
        self.math = MathAgent(self.math_contract, bank=self.bank)
        self.code = CodeAgent(self.code_contract, bank=self.bank)

        # Phase 2: router
        self.router = MetaRouter([self.math, self.code])

        # Phase 3: oracle
        self.oracle = OracleVerifier()

        # Phase 4: swarm manager
        self.swarm = SwarmManager(self.router, self.oracle)

        # Phase 11: GCEL (optional)
        self.gcel = GCEL(mutation_step=0.04, elite_frac=0.50, seed=0)

    def hello(self) -> str:
        return "moaa-prime says hello"

    def run_once(self, prompt: str, task_id: str = "default") -> Dict[str, Any]:
        """
        Phase 2/3/5 contract:
        - accepts task_id
        - returns decision + result
        - includes top-level "oracle" block (Phase 3 test)
        - BaseAgent handles memory writes/reads and returns memory meta (Phase 5/6 tests)
        """
        agent, decision = self.router.route(prompt)
        result = agent.handle(prompt, task_id=task_id)

        oracle_block = self.oracle.verdict(prompt, result.text)

        return {
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
            "oracle": {
                "score": float(getattr(oracle_block, "score", 0.5)),
                "reason": getattr(oracle_block, "reason", ""),
                "meta": getattr(oracle_block, "meta", {}) or {},
            },
        }

    def run_swarm(self, prompt: str, task_id: str = "default", rounds: int = 3, top_k: int = 2) -> Dict[str, Any]:
        """
        Phase 4 contract: must exist.
        """
        return self.swarm.run(prompt=prompt, task_id=task_id, rounds=rounds, top_k=top_k)

    def evolve_contracts(self, fitness: Dict[str, float]) -> Dict[str, Any]:
        """
        Phase 11:
        Evolve contracts based on fitness scores.
        Returns before/after snapshot.
        """
        before = [self.math.contract, self.code.contract]
        after = self.gcel.evolve(before, fitness)

        # apply evolved contracts back onto agents
        by_name = {c.name: c for c in after}
        if "math-agent" in by_name:
            self.math.contract = by_name["math-agent"]
        if "code-agent" in by_name:
            self.code.contract = by_name["code-agent"]

        return {
            "before": [
                {"name": c.name, "competence": c.competence, "domains": c.domains, "tools": c.tools}
                for c in before
            ],
            "after": [
                {"name": c.name, "competence": c.competence, "domains": c.domains, "tools": c.tools}
                for c in after
            ],
        }
