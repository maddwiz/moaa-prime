from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping, Sequence


_EPS = 1.0e-12
_TOOL_FAIL = "tool-fail"
_LOW_CONFIDENCE = "low-confidence"
_HIGH_AMBIGUITY = "high-ambiguity"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


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


@dataclass(frozen=True)
class DualSelectionCandidate:
    label: str
    text: str
    oracle_score: float
    tool_verified: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", str(self.label or "").strip() or "candidate")
        object.__setattr__(self, "text", str(self.text or ""))
        object.__setattr__(self, "oracle_score", _clamp(float(self.oracle_score), 0.0, 1.0))
        object.__setattr__(self, "tool_verified", bool(self.tool_verified))
        object.__setattr__(self, "meta", dict(self.meta or {}))


@dataclass(frozen=True)
class DualGateDecision:
    should_trigger: bool
    reasons: tuple[str, ...]
    confidence: float
    ambiguity: float
    tool_failed: bool


@dataclass(frozen=True)
class DualSelectionResult:
    trigger: DualGateDecision
    candidates: tuple[DualSelectionCandidate, ...]
    winner: DualSelectionCandidate
    selection_reason: str


class GatedDualBrainSelector:
    """
    Deterministic PR-4 gate + selector.

    Trigger conditions:
    - low-confidence
    - high-ambiguity
    - tool-fail

    Selection order:
    1) tool-verified winner
    2) higher oracle score
    3) stable shorter/cleaner fallback
    """

    def __init__(
        self,
        *,
        low_confidence_threshold: float = 0.60,
        high_ambiguity_threshold: float = 0.55,
    ) -> None:
        self.low_confidence_threshold = _clamp(float(low_confidence_threshold), 0.0, 1.0)
        self.high_ambiguity_threshold = _clamp(float(high_ambiguity_threshold), 0.0, 1.0)

    def ambiguity_from_scores(self, ranked_scores: Sequence[float] | None) -> float:
        if not ranked_scores or len(ranked_scores) < 2:
            return 0.0

        normalized = sorted((_clamp(float(v), 0.0, 1.0) for v in ranked_scores), reverse=True)
        gap = _clamp(normalized[0] - normalized[1], 0.0, 1.0)
        return _clamp(1.0 - gap, 0.0, 1.0)

    def _tool_failed_from_metadata(self, answer_metadata: Mapping[str, Any] | None) -> bool:
        meta = _coerce_mapping(answer_metadata)
        tool_meta = _coerce_mapping(meta.get("tool_first"))
        if not tool_meta:
            return False

        attempted = _coerce_bool(tool_meta.get("attempted", False))
        success_flag = tool_meta.get("success")
        if attempted and success_flag is False:
            return True

        verification = _coerce_mapping(tool_meta.get("verification"))
        if not verification:
            return False

        status = str(verification.get("status", "") or "").strip().lower()
        if status == "fail":
            return True

        if verification.get("passed") is False:
            return True

        return False

    def evaluate_trigger(
        self,
        *,
        confidence: float | None = None,
        ambiguity: float | None = None,
        ranked_scores: Sequence[float] | None = None,
        tool_failed: bool = False,
        answer_metadata: Mapping[str, Any] | None = None,
    ) -> DualGateDecision:
        conf_value = 1.0 if confidence is None else _clamp(float(confidence), 0.0, 1.0)
        if ambiguity is None:
            amb_value = self.ambiguity_from_scores(ranked_scores)
        else:
            amb_value = _clamp(float(ambiguity), 0.0, 1.0)

        tool_fail_value = bool(tool_failed) or self._tool_failed_from_metadata(answer_metadata)

        low_confidence = conf_value < self.low_confidence_threshold
        high_ambiguity = amb_value >= self.high_ambiguity_threshold

        reasons: list[str] = []
        if low_confidence:
            reasons.append(_LOW_CONFIDENCE)
        if high_ambiguity:
            reasons.append(_HIGH_AMBIGUITY)
        if tool_fail_value:
            reasons.append(_TOOL_FAIL)

        return DualGateDecision(
            should_trigger=bool(reasons),
            reasons=tuple(reasons),
            confidence=conf_value,
            ambiguity=amb_value,
            tool_failed=tool_fail_value,
        )

    def _candidate_from_mapping(
        self,
        raw: Mapping[str, Any],
        *,
        default_label: str,
    ) -> DualSelectionCandidate:
        oracle = _coerce_mapping(raw.get("oracle"))
        meta = dict(_coerce_mapping(raw.get("meta")))
        score = raw.get("oracle_score", oracle.get("score", 0.0))
        label = raw.get("label", raw.get("mode", default_label))
        text = str(raw.get("text", ""))
        if "tool_verified" in raw:
            tool_verified = bool(raw.get("tool_verified"))
        else:
            tool_verified = False
            tool_meta = _coerce_mapping(meta.get("tool_first"))
            if tool_meta:
                attempted = _coerce_bool(tool_meta.get("attempted", False))
                if attempted and tool_meta.get("success") is True:
                    tool_verified = True
                verification = _coerce_mapping(tool_meta.get("verification"))
                if verification:
                    passed = verification.get("passed")
                    status = str(verification.get("status", "") or "").strip().lower()
                    tool_verified = bool(passed is True or status == "pass")
        try:
            score_value = float(score)
        except (TypeError, ValueError):
            score_value = 0.0
        return DualSelectionCandidate(
            label=str(label),
            text=text,
            oracle_score=score_value,
            tool_verified=bool(tool_verified),
            meta=meta,
        )

    def coerce_candidate(
        self,
        candidate: DualSelectionCandidate | Mapping[str, Any],
        *,
        default_label: str,
    ) -> DualSelectionCandidate:
        if isinstance(candidate, DualSelectionCandidate):
            return candidate
        return self._candidate_from_mapping(_coerce_mapping(candidate), default_label=default_label)

    def build_candidate_set(
        self,
        *,
        single: DualSelectionCandidate | Mapping[str, Any],
        dual: DualSelectionCandidate | Mapping[str, Any] | None,
    ) -> tuple[DualSelectionCandidate, ...]:
        single_candidate = self.coerce_candidate(single, default_label="single")
        if dual is None:
            return (single_candidate,)
        dual_candidate = self.coerce_candidate(dual, default_label="dual")
        return (single_candidate, dual_candidate)

    def _fallback_key(
        self,
        candidate: DualSelectionCandidate,
        *,
        index: int,
    ) -> tuple[int, int, str, int]:
        clean = _clean_text(candidate.text)
        return (
            _cleanliness_penalty(candidate.text),
            len(clean),
            candidate.label,
            index,
        )

    def select_winner(
        self,
        candidates: Sequence[DualSelectionCandidate],
    ) -> tuple[DualSelectionCandidate, str]:
        if not candidates:
            raise ValueError("candidates must not be empty")

        ordered = list(candidates)
        verified = [c for c in ordered if c.tool_verified]
        pool = verified if verified else ordered
        pool_reason = "tool-verified" if verified else "oracle-score"

        best_score = max(c.oracle_score for c in pool)
        top = [c for c in pool if abs(c.oracle_score - best_score) <= _EPS]
        if len(top) == 1:
            return top[0], pool_reason

        index_by_object = {id(candidate): idx for idx, candidate in enumerate(ordered)}
        winner = min(
            top,
            key=lambda c: self._fallback_key(c, index=index_by_object[id(c)]),
        )
        return winner, "fallback-shorter-cleaner"

    def run(
        self,
        *,
        single: DualSelectionCandidate | Mapping[str, Any],
        dual: DualSelectionCandidate | Mapping[str, Any] | None = None,
        confidence: float | None = None,
        ambiguity: float | None = None,
        ranked_scores: Sequence[float] | None = None,
        tool_failed: bool = False,
        answer_metadata: Mapping[str, Any] | None = None,
    ) -> DualSelectionResult:
        trigger = self.evaluate_trigger(
            confidence=confidence,
            ambiguity=ambiguity,
            ranked_scores=ranked_scores,
            tool_failed=tool_failed,
            answer_metadata=answer_metadata,
        )
        all_candidates = self.build_candidate_set(single=single, dual=dual)
        if trigger.should_trigger:
            active_candidates = all_candidates
        else:
            active_candidates = all_candidates[:1]

        winner, selection_reason = self.select_winner(active_candidates)
        return DualSelectionResult(
            trigger=trigger,
            candidates=tuple(active_candidates),
            winner=winner,
            selection_reason=selection_reason,
        )


GatedDualSelector = GatedDualBrainSelector


def select_gated_dual(
    *,
    single: DualSelectionCandidate | Mapping[str, Any],
    dual: DualSelectionCandidate | Mapping[str, Any] | None = None,
    confidence: float | None = None,
    ambiguity: float | None = None,
    ranked_scores: Sequence[float] | None = None,
    tool_failed: bool = False,
    answer_metadata: Mapping[str, Any] | None = None,
    low_confidence_threshold: float = 0.60,
    high_ambiguity_threshold: float = 0.55,
) -> DualSelectionResult:
    selector = GatedDualBrainSelector(
        low_confidence_threshold=low_confidence_threshold,
        high_ambiguity_threshold=high_ambiguity_threshold,
    )
    return selector.run(
        single=single,
        dual=dual,
        confidence=confidence,
        ambiguity=ambiguity,
        ranked_scores=ranked_scores,
        tool_failed=tool_failed,
        answer_metadata=answer_metadata,
    )


__all__ = [
    "DualGateDecision",
    "DualSelectionCandidate",
    "DualSelectionResult",
    "GatedDualBrainSelector",
    "GatedDualSelector",
    "select_gated_dual",
]
