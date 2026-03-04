from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence


_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_EQUATION_RE = re.compile(r"[a-z0-9_\)\]]\s*=\s*[a-z0-9_\(\[]", flags=re.IGNORECASE)
_ARITHMETIC_RE = re.compile(r"(?<!\w)(?:\d+(?:\.\d+)?\s*[\+\-\*/\^]\s*)+\d+(?:\.\d+)?")
_CODE_BLOCK_RE = re.compile(r"```")
_PYTHON_SIG_RE = re.compile(r"\b(def|class|import|from|return|lambda|try|except|raise)\b")
_TRACEBACK_RE = re.compile(r"\b(traceback|stack trace|exception|nameerror|typeerror|syntaxerror)\b")

_MATH_KEYWORDS = {
    "algebra",
    "calculate",
    "derivative",
    "differentiate",
    "equation",
    "factor",
    "integral",
    "math",
    "simplify",
    "solve",
    "sum",
}

_CODE_KEYWORDS = {
    "api",
    "bug",
    "code",
    "debug",
    "error",
    "exception",
    "function",
    "implementation",
    "python",
    "refactor",
    "stack",
    "traceback",
}

_VALID_INTENTS = {"math", "code", "general"}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _normalize_text(prompt: str, task_metadata: Mapping[str, Any] | None = None) -> str:
    parts = [str(prompt or "")]
    if isinstance(task_metadata, Mapping):
        objective = task_metadata.get("objective")
        if objective:
            parts.append(str(objective))
        required = task_metadata.get("required_domains")
        if isinstance(required, Sequence) and not isinstance(required, (str, bytes)):
            parts.extend(str(x) for x in required)
    return "\n".join(parts)


def _required_domains(task_metadata: Mapping[str, Any] | None) -> set[str]:
    out: set[str] = set()
    if not isinstance(task_metadata, Mapping):
        return out
    required = task_metadata.get("required_domains")
    if isinstance(required, Sequence) and not isinstance(required, (str, bytes)):
        for item in required:
            token = str(item).strip().lower()
            if token:
                out.add(token)
    return out


@dataclass(frozen=True)
class IntentAnalysis:
    intent: str
    matched_features: tuple[str, ...]
    scores: dict[str, float]


def analyze_prompt_intent(prompt: str, *, task_metadata: Mapping[str, Any] | None = None) -> IntentAnalysis:
    text = _normalize_text(prompt, task_metadata=task_metadata)
    lowered = text.lower()
    tokens = set(_TOKEN_RE.findall(lowered))
    required_domains = _required_domains(task_metadata)

    matched_features: list[str] = []

    math_score = 0.0
    code_score = 0.0

    if _EQUATION_RE.search(lowered):
        math_score += 0.70
        matched_features.append("equation_pattern")
    if _ARITHMETIC_RE.search(lowered):
        math_score += 0.55
        matched_features.append("arithmetic_pattern")
    if any(tok in {"x", "y", "z"} for tok in tokens):
        math_score += 0.18
        matched_features.append("symbolic_variable")

    math_hits = sorted(tokens.intersection(_MATH_KEYWORDS))
    if math_hits:
        math_score += min(0.60, 0.12 * float(len(math_hits)))
        matched_features.extend([f"math_kw:{kw}" for kw in math_hits[:4]])

    if "math" in required_domains:
        math_score += 0.45
        matched_features.append("required_domain:math")

    if _CODE_BLOCK_RE.search(text):
        code_score += 0.72
        matched_features.append("code_block")
    if _PYTHON_SIG_RE.search(lowered):
        code_score += 0.55
        matched_features.append("python_syntax")
    if _TRACEBACK_RE.search(lowered):
        code_score += 0.62
        matched_features.append("traceback_signal")

    code_hits = sorted(tokens.intersection(_CODE_KEYWORDS))
    if code_hits:
        code_score += min(0.60, 0.12 * float(len(code_hits)))
        matched_features.extend([f"code_kw:{kw}" for kw in code_hits[:4]])

    if "code" in required_domains:
        code_score += 0.45
        matched_features.append("required_domain:code")

    math_score = _clamp(math_score, 0.0, 1.0)
    code_score = _clamp(code_score, 0.0, 1.0)

    if math_score >= 0.56 and math_score >= (code_score + 0.08):
        intent = "math"
    elif code_score >= 0.56 and code_score >= (math_score + 0.08):
        intent = "code"
    elif math_score >= code_score and math_score >= 0.72:
        intent = "math"
    elif code_score > math_score and code_score >= 0.72:
        intent = "code"
    else:
        intent = "general"

    general_score = _clamp(0.55 + (0.45 * (1.0 - max(math_score, code_score))), 0.0, 1.0)
    scores = {
        "math": float(math_score),
        "code": float(code_score),
        "general": float(general_score),
    }
    return IntentAnalysis(
        intent=intent,
        matched_features=tuple(dict.fromkeys(matched_features)),
        scores=scores,
    )


def intent_confidence_score(scores: Mapping[str, float], intent: str) -> float:
    if not isinstance(scores, Mapping):
        return 0.5
    intent_name = str(intent or "general").strip().lower()
    if intent_name not in _VALID_INTENTS:
        intent_name = "general"

    ordered = sorted((float(scores.get(k, 0.0)) for k in _VALID_INTENTS), reverse=True)
    top = ordered[0] if ordered else 0.0
    second = ordered[1] if len(ordered) > 1 else 0.0
    lead = _clamp(top - second, 0.0, 1.0)
    selected = _clamp(float(scores.get(intent_name, 0.0)), 0.0, 1.0)
    return _clamp(0.40 + (0.45 * selected) + (0.35 * lead), 0.0, 1.0)


def intent_alignment_score(intent: str, domains: Sequence[str]) -> float:
    intent_name = str(intent or "general").strip().lower()
    ds = {str(d).strip().lower() for d in (domains or []) if str(d).strip()}

    if intent_name == "math":
        if "math" in ds:
            return 1.0
        if "code" in ds:
            return 0.10
        return 0.45

    if intent_name == "code":
        if "code" in ds:
            return 1.0
        if "math" in ds:
            return 0.15
        return 0.45

    if not ds or "general" in ds:
        return 0.78
    return 0.60
