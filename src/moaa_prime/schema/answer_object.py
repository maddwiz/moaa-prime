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


def _extract_tools(output: Mapping[str, Any], existing: Mapping[str, Any]) -> list[str]:
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
        if _coerce_mapping(tool_first.get("verification")):
            _append_strings(tools, "python-verify")

    agent_name = _extract_primary_agent(output)
    if agent_name:
        hint = _AGENT_TOOL_HINTS.get(agent_name)
        if hint:
            _append_strings(tools, hint)

    return tools


def _extract_notes(output: Mapping[str, Any], existing: Mapping[str, Any]) -> list[str]:
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

    return notes


def _extract_trace(output: Mapping[str, Any], existing: Mapping[str, Any], *, confidence: float) -> Dict[str, Any]:
    trace = _coerce_mapping(output.get("trace"))
    if trace:
        return deepcopy(dict(trace))

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
        return synthesized

    existing_trace = _coerce_mapping(existing.get("trace"))
    if existing_trace:
        return deepcopy(dict(existing_trace))
    return {}


def normalize_answer_object(output: Mapping[str, Any]) -> Dict[str, Any]:
    existing = _coerce_mapping(output.get("answer_object"))
    final = _extract_final(output, existing)
    confidence = _extract_confidence(output, existing)
    return {
        "final": final,
        "tools": _extract_tools(output, existing),
        "confidence": confidence,
        "notes": _extract_notes(output, existing),
        "trace": _extract_trace(output, existing, confidence=confidence),
    }


def upgrade_answer_object(payload: Mapping[str, Any] | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(payload, dict):
        out = payload
    else:
        out = dict(payload)
    out["answer_object"] = normalize_answer_object(out)
    return out


__all__ = ["ANSWER_OBJECT_KEYS", "normalize_answer_object", "upgrade_answer_object"]
