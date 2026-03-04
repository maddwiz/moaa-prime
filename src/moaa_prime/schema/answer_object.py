from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, Mapping


ANSWER_OBJECT_KEYS = ("final", "tools", "confidence", "notes", "trace")

_AGENT_TOOL_HINTS = {
    "math-agent": "sympy",
    "code-agent": "exec",
    "dual-brain": "dual-brain-runner",
}


def _coerce_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        v = value.strip()
        if v:
            yield v
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, str):
                v = item.strip()
                if v:
                    yield v


def _append_strings(dest: list[str], value: Any) -> None:
    for item in _iter_strings(value):
        if item not in dest:
            dest.append(item)


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "pass", "passed", "ok", "success", "succeeded"}:
            return True
        if lowered in {"0", "false", "no", "n", "fail", "failed", "error"}:
            return False
    return bool(default)


def _normalize_verification_signal(
    signal: Mapping[str, Any],
    *,
    source: str,
    tool: str = "",
    attempted: bool | None = None,
    success: bool | None = None,
) -> Dict[str, Any]:
    raw_status = str(signal.get("status", "") or "").strip().lower()
    passed = _coerce_bool(signal.get("passed"), default=(raw_status == "pass"))
    status = raw_status if raw_status in {"pass", "fail"} else ("pass" if passed else "fail")
    stage = str(signal.get("stage", "") or "").strip().lower()

    normalized: Dict[str, Any] = {
        "status": status,
        "passed": bool(passed),
        "stage": stage,
        "exec_ran": _coerce_bool(signal.get("exec_ran"), default=False),
        "source": source,
    }
    if tool:
        normalized["tool"] = tool
    if attempted is not None:
        normalized["attempted"] = bool(attempted)
    if success is not None:
        normalized["success"] = bool(success)

    error_type = signal.get("error_type")
    error_message = signal.get("error_message")
    if error_type is not None:
        normalized["error_type"] = error_type
    if error_message is not None:
        normalized["error_message"] = error_message
    return normalized


def _verification_candidates_from_tool_first(tool_first: Mapping[str, Any], *, source_prefix: str) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    attempted = _coerce_bool(tool_first.get("attempted"), default=False)
    success = _coerce_bool(tool_first.get("success"), default=False)
    tool_hint = str(tool_first.get("solver") or tool_first.get("tool") or "").strip()

    verification = _coerce_mapping(tool_first.get("verification"))
    if verification:
        rows.append(
            _normalize_verification_signal(
                verification,
                source=f"{source_prefix}.verification",
                tool=tool_hint,
                attempted=attempted,
                success=success,
            )
        )

    for probe_name in ("proposal_probe", "prompt_probe"):
        probe = _coerce_mapping(tool_first.get(probe_name))
        probe_verification = _coerce_mapping(probe.get("verification"))
        if not probe_verification:
            continue
        probe_tool = str(probe.get("solver") or probe.get("tool") or tool_hint).strip()
        probe_attempted = _coerce_bool(probe.get("attempted"), default=attempted)
        probe_success = _coerce_bool(probe.get("success"), default=success)
        rows.append(
            _normalize_verification_signal(
                probe_verification,
                source=f"{source_prefix}.{probe_name}.verification",
                tool=probe_tool,
                attempted=probe_attempted,
                success=probe_success,
            )
        )

    if not verification and attempted and "success" in tool_first:
        stage = str(tool_first.get("mode") or tool_first.get("stage") or tool_hint or "tool").strip().lower()
        rows.append(
            _normalize_verification_signal(
                {
                    "status": "pass" if success else "fail",
                    "passed": bool(success),
                    "stage": stage,
                    "exec_ran": False,
                    "error_type": tool_first.get("error_type"),
                    "error_message": tool_first.get("error") or tool_first.get("error_message"),
                },
                source=f"{source_prefix}.outcome",
                tool=tool_hint,
                attempted=attempted,
                success=success,
            )
        )

    return rows


def _verification_candidates_from_oracle(oracle_block: Mapping[str, Any], *, source: str) -> list[Dict[str, Any]]:
    meta = _coerce_mapping(oracle_block.get("meta"))
    signal = _coerce_mapping(meta.get("verification_signal"))
    if not signal:
        return []
    resolved_source = str(signal.get("source") or source).strip() or source
    return [_normalize_verification_signal(signal, source=resolved_source, tool=str(signal.get("tool") or "").strip())]


def _dedupe_verification_signals(signals: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[Dict[str, Any]] = []
    for row in signals:
        key = (
            row.get("source"),
            row.get("status"),
            row.get("stage"),
            row.get("passed"),
            row.get("exec_ran"),
            row.get("error_type"),
            row.get("error_message"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _extract_verification_signal(output: Mapping[str, Any], existing: Mapping[str, Any]) -> Dict[str, Any]:
    candidates: list[Dict[str, Any]] = []

    for block_name in ("best", "result"):
        block = _coerce_mapping(output.get(block_name))
        meta = _coerce_mapping(block.get("meta"))
        tool_first = _coerce_mapping(meta.get("tool_first"))
        if tool_first:
            candidates.extend(_verification_candidates_from_tool_first(tool_first, source_prefix=f"{block_name}.meta.tool_first"))
        block_oracle = _coerce_mapping(block.get("oracle"))
        if block_oracle:
            candidates.extend(
                _verification_candidates_from_oracle(
                    block_oracle,
                    source=f"{block_name}.oracle.meta.verification_signal",
                )
            )

    oracle = _coerce_mapping(output.get("oracle"))
    if oracle:
        candidates.extend(_verification_candidates_from_oracle(oracle, source="oracle.meta.verification_signal"))

    existing_trace = _coerce_mapping(existing.get("trace"))
    existing_verification = _coerce_mapping(existing_trace.get("verification"))
    if existing_verification:
        existing_source = str(existing_verification.get("source") or "answer_object.trace.verification").strip()
        candidates.append(
            _normalize_verification_signal(
                existing_verification,
                source=existing_source or "answer_object.trace.verification",
                tool=str(existing_verification.get("tool") or "").strip(),
            )
        )

    signals = _dedupe_verification_signals(candidates)
    if not signals:
        return {}

    primary = next((row for row in signals if bool(row.get("passed"))), signals[0])
    summary = dict(primary)
    if len(signals) > 1:
        summary["signals"] = [dict(row) for row in signals]
    return summary


def _extract_primary_agent(output: Mapping[str, Any]) -> str:
    best = _coerce_mapping(output.get("best"))
    best_agent = str(best.get("agent", "") or "").strip()
    if best_agent:
        return best_agent

    result = _coerce_mapping(output.get("result"))
    result_agent = str(result.get("agent", "") or "").strip()
    if result_agent:
        return result_agent

    decision = _coerce_mapping(output.get("decision"))
    return str(decision.get("agent", "") or "").strip()


def _extract_final(output: Mapping[str, Any], existing: Mapping[str, Any]) -> str:
    best = _coerce_mapping(output.get("best"))
    best_text = best.get("text")
    if isinstance(best_text, str):
        return best_text

    result = _coerce_mapping(output.get("result"))
    result_text = result.get("text")
    if isinstance(result_text, str):
        return result_text

    final = output.get("final")
    if isinstance(final, str):
        return final

    existing_final = existing.get("final")
    if isinstance(existing_final, str):
        return existing_final
    return ""


def _extract_confidence(output: Mapping[str, Any], existing: Mapping[str, Any]) -> float:
    best = _coerce_mapping(output.get("best"))
    best_oracle = _coerce_mapping(best.get("oracle"))
    oracle = _coerce_mapping(output.get("oracle"))
    trace = _coerce_mapping(output.get("trace"))
    trace_final = _coerce_mapping(trace.get("final"))

    raw = output.get("confidence")
    if raw is None:
        raw = oracle.get("score")
    if raw is None:
        raw = best.get("confidence_proxy")
    if raw is None:
        raw = best_oracle.get("score")
    if raw is None:
        raw = trace_final.get("confidence")
    if raw is None:
        raw = existing.get("confidence")

    return _clamp01(_safe_float(raw, default=0.0))


def _extract_tools(
    output: Mapping[str, Any],
    existing: Mapping[str, Any],
    *,
    verification_signal: Mapping[str, Any],
) -> list[str]:
    tools: list[str] = []
    _append_strings(tools, existing.get("tools"))
    _append_strings(tools, output.get("tools"))

    for block_name in ("result", "best"):
        block = _coerce_mapping(output.get(block_name))
        meta = _coerce_mapping(block.get("meta"))
        _append_strings(tools, meta.get("tools"))

        model = str(meta.get("model", "") or "").strip()
        if model.startswith("tool_first:"):
            _append_strings(tools, model.split(":", 1)[1])

        tool_first = _coerce_mapping(meta.get("tool_first"))
        _append_strings(tools, tool_first.get("solver"))
        _append_strings(tools, tool_first.get("tool"))
        verification_rows = _verification_candidates_from_tool_first(tool_first, source_prefix=f"{block_name}.meta.tool_first")
        if any(str(row.get("source", "")).endswith(".verification") for row in verification_rows):
            _append_strings(tools, "python-verify")

    agent_name = _extract_primary_agent(output)
    if agent_name:
        hint = _AGENT_TOOL_HINTS.get(agent_name)
        if hint:
            _append_strings(tools, hint)

    if verification_signal:
        if bool(verification_signal.get("passed")):
            _append_strings(tools, "tool-verified")
        else:
            _append_strings(tools, "tool-unverified")

    return tools


def _extract_notes(
    output: Mapping[str, Any],
    existing: Mapping[str, Any],
    *,
    verification_signal: Mapping[str, Any],
) -> list[str]:
    notes: list[str] = []
    _append_strings(notes, existing.get("notes"))

    best = _coerce_mapping(output.get("best"))
    best_oracle = _coerce_mapping(best.get("oracle"))
    oracle = _coerce_mapping(output.get("oracle"))
    route_trace = _coerce_mapping(output.get("route_trace"))
    trace = _coerce_mapping(output.get("trace"))
    trace_swarm = _coerce_mapping(trace.get("swarm"))
    dual_gate = _coerce_mapping(trace_swarm.get("dual_gate"))

    reason = best_oracle.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = oracle.get("reason")
    _append_strings(notes, reason)

    _append_strings(notes, route_trace.get("ranking_rationale"))

    if bool(dual_gate.get("triggered", False)):
        reasons = [str(x) for x in (dual_gate.get("reasons") or []) if str(x).strip()]
        if reasons:
            _append_strings(notes, f"dual_gate:{','.join(reasons)}")

    if verification_signal:
        status = str(verification_signal.get("status", "unknown") or "unknown").strip().lower()
        stage = str(verification_signal.get("stage", "") or "").strip().lower()
        label = f"verification:{status}" + (f"({stage})" if stage else "")
        _append_strings(notes, label)

    return notes


def _extract_trace(
    output: Mapping[str, Any],
    existing: Mapping[str, Any],
    *,
    confidence: float,
    verification_signal: Mapping[str, Any],
) -> Dict[str, Any]:
    trace = _coerce_mapping(output.get("trace"))
    if trace:
        out = deepcopy(dict(trace))
        if verification_signal:
            out["verification"] = deepcopy(dict(verification_signal))
        return out

    route_trace = _coerce_mapping(output.get("route_trace"))
    decision = _coerce_mapping(output.get("decision"))
    result = _coerce_mapping(output.get("result"))
    oracle = _coerce_mapping(output.get("oracle"))

    synthesized: Dict[str, Any] = {}
    if route_trace:
        synthesized["router"] = dict(route_trace)
    if decision:
        synthesized["decision"] = dict(decision)
    if oracle:
        synthesized["oracle"] = dict(oracle)
    if result or decision:
        synthesized["final"] = {
            "agent": str(result.get("agent", decision.get("agent", "")) or ""),
            "score": _safe_float(oracle.get("score"), default=0.0),
            "confidence": float(confidence),
        }

    if synthesized:
        if verification_signal:
            synthesized["verification"] = deepcopy(dict(verification_signal))
        return synthesized

    existing_trace = _coerce_mapping(existing.get("trace"))
    if existing_trace:
        out = deepcopy(dict(existing_trace))
        if verification_signal:
            out["verification"] = deepcopy(dict(verification_signal))
        return out
    if verification_signal:
        return {"verification": deepcopy(dict(verification_signal))}
    return {}


def normalize_answer_object(output: Mapping[str, Any]) -> Dict[str, Any]:
    existing = _coerce_mapping(output.get("answer_object"))
    final = _extract_final(output, existing)
    confidence = _extract_confidence(output, existing)
    verification_signal = _extract_verification_signal(output, existing)
    return {
        "final": final,
        "tools": _extract_tools(output, existing, verification_signal=verification_signal),
        "confidence": confidence,
        "notes": _extract_notes(output, existing, verification_signal=verification_signal),
        "trace": _extract_trace(output, existing, confidence=confidence, verification_signal=verification_signal),
    }


def upgrade_answer_object(payload: Mapping[str, Any] | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(payload, dict):
        out = payload
    else:
        out = dict(payload)
    out["answer_object"] = normalize_answer_object(out)
    return out


__all__ = ["ANSWER_OBJECT_KEYS", "normalize_answer_object", "upgrade_answer_object"]
