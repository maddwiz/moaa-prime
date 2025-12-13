from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class OracleVerdict:
    score: float
    reason: str = ""
    meta: Dict[str, Any] | None = None


class OracleVerifier:
    """
    Phase 3 Oracle.

    IMPORTANT CONTRACT:
    - verdict(prompt, answer) returns OracleVerdict (rich object)
    - score(prompt, answer) returns float in [0, 1] (simple numeric)
    """

    def verdict(self, prompt: str, answer: str) -> OracleVerdict:
        # v0 heuristic oracle (simple + deterministic)
        p = (prompt or "").lower()
        a = (answer or "").lower()

        # Tiny heuristics so tests + demos have stable behavior
        if "solve" in p and ("x=" in a or "x =" in a):
            return OracleVerdict(score=0.9, reason="contains x= form")

        if "python" in p or "code" in p:
            # if they mention a likely code term, give medium-high
            if "def " in a or "traceback" in a or "error" in a:
                return OracleVerdict(score=0.8, reason="looks like code-debug response")
            return OracleVerdict(score=0.6, reason="code-related response")

        # Default: neutral
        return OracleVerdict(score=0.5, reason="default oracle")

    def score(self, prompt: str, answer: str) -> float:
        v = self.verdict(prompt, answer)
        # Force [0,1] and float
        s = float(v.score)
        if s < 0.0:
            return 0.0
        if s > 1.0:
            return 1.0
        return s
