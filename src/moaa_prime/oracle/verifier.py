from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import statistics
from typing import Any, Dict, Mapping

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "with",
}


@dataclass(frozen=True)
class OracleVerdict:
    score: float
    reason: str = ""
    meta: Dict[str, Any] | None = None


class OracleVerifier:
    """
    Phase 3 Oracle (v1).

    IMPORTANT CONTRACT:
    - verdict(prompt, answer) returns OracleVerdict (rich object)
    - score(prompt, answer) returns float in [0, 1] (simple numeric)
    """

    def verdict(self, prompt: str, answer: str) -> OracleVerdict:
        # v0 heuristic oracle (simple + deterministic)
        p = (prompt or "").lower()
        a = str(answer or "").lower()

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


class OracleV2:
    """
    Cycle 2 Oracle with weighted components and pluggable rubric config.

    Components in [0,1]:
    - correctness_proxy
    - coherence
    - constraint_adherence
    - safety_overreach
    - grounding
    """

    _DEFAULT_RUBRIC: Dict[str, Any] = {
        "weights": {
            "correctness_proxy": 0.34,
            "coherence": 0.20,
            "constraint_adherence": 0.18,
            "safety_overreach": 0.16,
            "grounding": 0.12,
        },
        "consistency": {
            "max_variance": 1.0e-6,
        },
        "safety": {
            "forbidden_terms": ["exploit", "malware", "payload", "credential dump", "ransomware"],
        },
    }

    def __init__(self, *, rubric_path: str | None = None, seed: int = 0) -> None:
        self.seed = int(seed)
        self.rubric_path = rubric_path
        self.rubric = self._load_rubric(rubric_path)

    def _load_rubric(self, rubric_path: str | None) -> Dict[str, Any]:
        rubric = dict(self._DEFAULT_RUBRIC)

        if rubric_path:
            path = Path(rubric_path)
            if path.exists():
                loaded: Dict[str, Any]
                text = path.read_text(encoding="utf-8")
                if path.suffix.lower() in {".yaml", ".yml"}:
                    if yaml is None:
                        loaded = {}
                    else:
                        loaded = yaml.safe_load(text) or {}
                else:
                    loaded = json.loads(text)
                if isinstance(loaded, dict):
                    rubric = self._deep_merge(rubric, loaded)
        else:
            default_file = Path(__file__).resolve().parent / "rubric_v2.yaml"
            if default_file.exists() and yaml is not None:
                loaded = yaml.safe_load(default_file.read_text(encoding="utf-8")) or {}
                if isinstance(loaded, dict):
                    rubric = self._deep_merge(rubric, loaded)

        weights = dict(rubric.get("weights", {}))
        total = sum(float(weights.get(k, 0.0)) for k in self._DEFAULT_RUBRIC["weights"].keys())
        if total <= 0.0:
            total = 1.0
        normalized = {
            k: float(weights.get(k, self._DEFAULT_RUBRIC["weights"][k])) / total
            for k in self._DEFAULT_RUBRIC["weights"].keys()
        }
        rubric["weights"] = normalized
        return rubric

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(base)
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = self._deep_merge(dict(out[k]), v)
            else:
                out[k] = v
        return out

    def _tokenize(self, text: str) -> list[str]:
        return _TOKEN_RE.findall((text or "").lower())

    def _important_tokens(self, text: str) -> set[str]:
        return {t for t in self._tokenize(text) if len(t) > 2 and t not in _STOPWORDS}

    def _correctness_proxy(self, prompt: str, answer: str, p_tokens: set[str], a_tokens: set[str]) -> float:
        p = (prompt or "").lower()
        a = (answer or "").lower()

        if "solve" in p or "equation" in p:
            if "x=" in a or "x =" in a:
                return 0.95
            if any(ch.isdigit() for ch in a):
                return 0.75
            return 0.30

        if "python" in p or "code" in p or "function" in p:
            if "def " in a:
                return 0.90
            if "return" in a:
                return 0.75
            return 0.45

        if not p_tokens:
            return 0.5

        overlap = len(p_tokens.intersection(a_tokens)) / float(max(1, len(p_tokens)))
        return _clamp(0.35 + (0.65 * overlap), 0.0, 1.0)

    def _coherence(self, answer: str) -> float:
        a = (answer or "").strip()
        if not a:
            return 0.0

        tokens = self._tokenize(a)
        n = len(tokens)
        if n < 2:
            return 0.2

        if n <= 6:
            length_score = 0.60
        elif n <= 80:
            length_score = 0.90
        elif n <= 180:
            length_score = 0.75
        else:
            length_score = 0.45

        punctuation_bonus = 0.05 if any(ch in a for ch in ".:;") else 0.0
        newline_penalty = 0.10 if a.count("\n") > 12 else 0.0
        return _clamp(length_score + punctuation_bonus - newline_penalty, 0.0, 1.0)

    def _constraint_adherence(self, prompt: str, answer: str) -> float:
        p = (prompt or "").lower()
        a = (answer or "")
        a_l = a.lower()

        score = 0.70

        if "return only x" in p:
            if "x=" in a_l or a_l.strip().isdigit() or a_l.strip() in {"x", "x = 2", "2"}:
                score = 0.95
            else:
                score = 0.35

        if "json" in p:
            has_braces = "{" in a and "}" in a
            score = min(score, 0.90 if has_braces else 0.40)

        if "concise" in p or "brief" in p:
            score = min(score, 0.90 if len(self._tokenize(a_l)) < 80 else 0.55)

        if "safe" in p and "1/0" in p:
            safe_hint = ("try" in a_l and "except" in a_l) or "zero division" in a_l
            score = min(score, 0.92 if safe_hint else 0.50)

        return _clamp(score, 0.0, 1.0)

    def _safety_overreach(self, answer: str) -> float:
        a_l = (answer or "").lower()
        forbidden = self.rubric.get("safety", {}).get("forbidden_terms", [])

        score = 0.95
        for term in forbidden:
            if str(term).lower() in a_l:
                score -= 0.25

        if "guaranteed" in a_l and "always" in a_l:
            score -= 0.15

        if "i made this up" in a_l:
            score -= 0.30

        return _clamp(score, 0.0, 1.0)

    def _grounding(self, prompt: str, answer: str, p_tokens: set[str], a_tokens: set[str]) -> float:
        if not p_tokens:
            return 0.5
        overlap = len(p_tokens.intersection(a_tokens)) / float(max(1, len(p_tokens)))

        p = (prompt or "").lower()
        a = (answer or "").lower()
        structure_bonus = 0.08 if (("solve" in p and "x" in a) or ("python" in p and "def " in a)) else 0.0
        return _clamp((0.30 + (0.62 * overlap) + structure_bonus), 0.0, 1.0)

    def _component_scores(self, prompt: str, answer: str) -> Dict[str, float]:
        p_tokens = self._important_tokens(prompt)
        a_tokens = self._important_tokens(answer)

        components = {
            "correctness_proxy": self._correctness_proxy(prompt, answer, p_tokens, a_tokens),
            "coherence": self._coherence(answer),
            "constraint_adherence": self._constraint_adherence(prompt, answer),
            "safety_overreach": self._safety_overreach(answer),
            "grounding": self._grounding(prompt, answer, p_tokens, a_tokens),
        }
        return {k: _clamp(float(v), 0.0, 1.0) for k, v in components.items()}

    def verdict(self, prompt: str, answer: str) -> OracleVerdict:
        answer_text = str(answer or "")
        components = self._component_scores(prompt or "", answer_text)
        weights = self.rubric["weights"]

        score = 0.0
        for key, weight in weights.items():
            score += float(weight) * float(components.get(key, 0.0))
        score = _clamp(score, 0.0, 1.0)

        reason = (
            f"weighted_oracle_v2; correctness={components['correctness_proxy']:.2f}; "
            f"coherence={components['coherence']:.2f}; grounding={components['grounding']:.2f}"
        )

        return OracleVerdict(
            score=score,
            reason=reason,
            meta={
                "oracle": "v2",
                "weights": {k: float(v) for k, v in weights.items()},
                "components": components,
                "rubric_path": self.rubric_path or "builtin:rubric_v2.yaml",
            },
        )

    def score(self, prompt: str, answer: str) -> float:
        return float(self.verdict(prompt, answer).score)

    def consistency_check(self, prompt: str, answer: str, repeats: int = 5) -> Dict[str, float | bool]:
        r = max(1, int(repeats))
        values = [self.score(prompt, answer) for _ in range(r)]
        mean = float(sum(values) / len(values))
        variance = float(statistics.pvariance(values)) if len(values) > 1 else 0.0
        max_delta = float(max(values) - min(values)) if values else 0.0

        max_variance = float(self.rubric.get("consistency", {}).get("max_variance", 1.0e-6))
        stable = bool(variance <= max_variance)

        return {
            "mean": mean,
            "variance": variance,
            "max_delta": max_delta,
            "stable": stable,
        }
