from __future__ import annotations

from moaa_prime.agents import CodeAgent, MathAgent
from moaa_prime.contracts import Contract
from moaa_prime.oracle import OracleVerifier
from moaa_prime.router import MetaRouter
from moaa_prime.swarm import SwarmManager


class MoAAPrime:
    """
    Phase 1: packaging + smoke
    Phase 2: instantiate agents + route prompts
    Phase 3: oracle wired
    Phase 4: swarm wired (top-k -> oracle score -> best)
    """

    def __init__(self) -> None:
        self.math = MathAgent(Contract(name="math-agent", domains=["math"], competence=0.80, tools=["sympy"]))
        self.code = CodeAgent(Contract(name="code-agent", domains=["code"], competence=0.78, tools=["exec"]))

        self.router = MetaRouter([self.math, self.code])
        self.oracle = OracleVerifier()
        self.swarm = SwarmManager(router=self.router, oracle=self.oracle, k=2)

    def hello(self) -> str:
        return "moaa-prime says hello"

    def run_once(self, prompt: str) -> dict:
        agent, decision = self.router.route(prompt)
        result = agent.handle(prompt)
        return {
            "prompt": prompt,
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

    def run_swarm(self, prompt: str) -> dict:
        return self.swarm.run(prompt)
