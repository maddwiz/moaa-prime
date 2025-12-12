from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OracleVerdict:
    score: float
    reason: str


class OracleVerifier:
    """
    Phase 3 stub oracle.

    Contract:
      - score(prompt, answer) -> OracleVerdict(score, reason)
      - verify(prompt, answer, agent_name=None) -> OracleVerdict(score, reason)

    Later phases can replace this with:
      - SymPy / execution sandbox / classifier heads, etc.
    """

    def score(self, prompt: str, answer: str) -> OracleVerdict:
        # Keep it deterministic + aligned with existing stub behavior.
        a = (answer or "").lower()

        if a.startswith("[math-agent stub]"):
            return OracleVerdict(score=0.7, reason="math-stub")

        if a.startswith("[code-agent stub]"):
            return OracleVerdict(score=0.5, reason="code-stub")

        # Generic fallback
        p = (prompt or "").lower()
        if "solve" in p or "equation" in p:
            return OracleVerdict(score=0.6, reason="generic-math-ish")
        if "python" in p or "bug" in p or "function" in p:
            return OracleVerdict(score=0.6, reason="generic-code-ish")

        return OracleVerdict(score=0.5, reason="generic-stub")

    def verify(self, prompt: str, answer: str, agent_name: str | None = None) -> OracleVerdict:
        # SwarmManager calls verify(); for now it’s just a wrapper.
        # agent_name is accepted for future richer reasoning, but unused in the stub.
        _ = agent_name
        return self.score(prompt=prompt, answer=answer)
