from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from moaa_prime.core.app import MoAAPrime


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


class EvalRunner:
    def __init__(self) -> None:
        self.app = MoAAPrime()

    def run(self, cases: List[EvalCase]) -> List[EvalResult]:
        results: List[EvalResult] = []
        for c in cases:
            if c.mode == "swarm":
                out = self.app.run_swarm(c.prompt)  # assumes exists from Phase 4+
            else:
                out = self.app.run_once(c.prompt)
            results.append(EvalResult(case_id=c.case_id, mode=c.mode, output=out))
        return results
