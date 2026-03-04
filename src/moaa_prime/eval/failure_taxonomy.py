from __future__ import annotations

from types import MappingProxyType
from typing import Any, Final, Mapping, MutableMapping, TypedDict

FAILURE_CLASSES: Final[tuple[str, ...]] = (
    "ROUTING_MISS",
    "TOOL_PARSE_FAIL",
    "TOOL_EXEC_FAIL",
    "FORMAT_FAIL",
    "MEMORY_DRIFT",
    "DUAL_REGRESSION",
    "SWARM_LOOP",
)

_PARSE_TOKENS: Final[tuple[str, ...]] = (
    "no_python_source_found",
    "extract",
    "parse",
    "syntax",
)

_EXEC_TOKENS: Final[tuple[str, ...]] = (
    "exec",
    "runtime",
    "nameerror",
    "typeerror",
    "zerodivision",
    "timeout",
)


class RemediationAction(TypedDict):
    owner: str
    priority: str
    action: str
    metric: str
    playbook: str


class RemediationPlanItem(RemediationAction):
    failure_class: str
    count: int


_REMEDIATION_BY_CLASS: Final[dict[str, RemediationAction]] = {
    "ROUTING_MISS": {
        "owner": "router",
        "priority": "high",
        "action": "Refresh intent calibration data and tighten router policy thresholds.",
        "metric": "routing_accuracy_delta",
        "playbook": "router_retrain",
    },
    "TOOL_PARSE_FAIL": {
        "owner": "tooling",
        "priority": "high",
        "action": "Harden code extraction and parser guards before tool execution.",
        "metric": "tool_verification_rate",
        "playbook": "tool_parser_hardening",
    },
    "TOOL_EXEC_FAIL": {
        "owner": "tooling",
        "priority": "high",
        "action": "Expand sandbox runtime checks and add execution fallback handling.",
        "metric": "tool_verification_rate",
        "playbook": "tool_runtime_guardrails",
    },
    "FORMAT_FAIL": {
        "owner": "policy",
        "priority": "medium",
        "action": "Strengthen output schema constraints and post-format normalization.",
        "metric": "pass_rate",
        "playbook": "response_format_enforcement",
    },
    "MEMORY_DRIFT": {
        "owner": "memory",
        "priority": "medium",
        "action": "Re-score memory retrieval quality and clamp low-signal memory injections.",
        "metric": "oracle_score_delta",
        "playbook": "memory_retrieval_audit",
    },
    "DUAL_REGRESSION": {
        "owner": "dual",
        "priority": "high",
        "action": "Re-tune dual-gate trigger policy against single-agent baseline regressions.",
        "metric": "dual_gate_pass_rate_delta",
        "playbook": "dual_gate_rebalance",
    },
    "SWARM_LOOP": {
        "owner": "swarm",
        "priority": "medium",
        "action": "Cap exploration loops when latency rises without pass-rate gain.",
        "metric": "latency_efficiency_delta",
        "playbook": "swarm_loop_clamp",
    },
}

if tuple(_REMEDIATION_BY_CLASS.keys()) != FAILURE_CLASSES:
    raise RuntimeError("remediation mapping keys must match FAILURE_CLASSES")

REMEDIATION_BY_CLASS: Final[Mapping[str, RemediationAction]] = MappingProxyType(_REMEDIATION_BY_CLASS)


def default_failure_counters() -> dict[str, int]:
    return {name: 0 for name in FAILURE_CLASSES}


def get_remediation_mapping() -> dict[str, RemediationAction]:
    return {name: dict(data) for name, data in _REMEDIATION_BY_CLASS.items()}


def remediation_for(failure_class: str) -> RemediationAction | None:
    action = _REMEDIATION_BY_CLASS.get(str(failure_class).strip())
    if action is None:
        return None
    return dict(action)


def build_remediation_plan(
    counters: Mapping[str, Any],
    *,
    top_k: int | None = None,
) -> list[RemediationPlanItem]:
    priority_weight = {"high": 0, "medium": 1, "low": 2}
    class_rank = {name: idx for idx, name in enumerate(FAILURE_CLASSES)}

    plan: list[RemediationPlanItem] = []
    for failure_class in FAILURE_CLASSES:
        count = int(max(0.0, _safe_float(counters.get(failure_class), default=0.0)))
        if count <= 0:
            continue
        remediation = _REMEDIATION_BY_CLASS.get(failure_class)
        if remediation is None:
            continue
        plan.append(
            {
                "failure_class": failure_class,
                "count": count,
                "owner": str(remediation["owner"]),
                "priority": str(remediation["priority"]),
                "action": str(remediation["action"]),
                "metric": str(remediation["metric"]),
                "playbook": str(remediation["playbook"]),
            }
        )

    plan.sort(
        key=lambda item: (
            -int(item["count"]),
            priority_weight.get(str(item["priority"]).strip().lower(), 9),
            class_rank.get(str(item["failure_class"]), 99),
        )
    )
    if top_k is not None:
        return plan[: max(0, int(top_k))]
    return plan


def classify_tool_verification_failure(*, status: Any, error_type: Any, error_message: Any) -> str | None:
    if str(status).strip().lower() != "fail":
        return None

    error_text = f"{error_type or ''} {error_message or ''}".lower()
    if any(token in error_text for token in _PARSE_TOKENS):
        return "TOOL_PARSE_FAIL"
    if any(token in error_text for token in _EXEC_TOKENS):
        return "TOOL_EXEC_FAIL"
    return "FORMAT_FAIL"


def is_routing_miss(*, intent: Any, chosen_agent: Any) -> bool:
    intent_value = str(intent).strip().lower()
    chosen_agent_value = str(chosen_agent).strip().lower()

    if not chosen_agent_value:
        return False
    if intent_value == "math":
        return "math" not in chosen_agent_value
    if intent_value == "code":
        return "code" not in chosen_agent_value
    return False


def is_memory_drift(*, pass_delta: Any | None = None, oracle_delta: Any | None = None, local_hits: Any | None = None) -> bool:
    if local_hits is not None and _safe_float(local_hits, default=0.0) < 0.0:
        return True

    if pass_delta is None and oracle_delta is None:
        return False

    pass_delta_value = _safe_float(pass_delta, default=0.0)
    oracle_delta_value = _safe_float(oracle_delta, default=0.0)
    return pass_delta_value < 0.0 or (pass_delta_value == 0.0 and oracle_delta_value < 0.0)


def is_dual_regression(*, pass_delta: Any) -> bool:
    return _safe_float(pass_delta, default=0.0) < 0.0


def is_swarm_loop(*, latency_delta: Any, pass_delta: Any | None = None, entropy_delta: Any | None = None) -> bool:
    if _safe_float(latency_delta, default=0.0) <= 0.0:
        return False

    if pass_delta is not None:
        return _safe_float(pass_delta, default=0.0) <= 0.0
    if entropy_delta is not None:
        return _safe_float(entropy_delta, default=0.0) <= 0.0
    return False


def derive_failure_taxonomy(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    counters = default_failure_counters()

    eval_matrix = reports.get("eval_matrix")
    if isinstance(eval_matrix, Mapping):
        _count_failures_from_matrix(eval_matrix, counters)

    eval_report = reports.get("eval_report")
    if isinstance(eval_report, Mapping):
        _count_failures_from_eval_report(eval_report, counters)

    dual_eval = reports.get("dual_gated_eval")
    if isinstance(dual_eval, Mapping):
        _count_failures_from_dual_eval(dual_eval, counters)

    eval_compare = reports.get("eval_compare")
    if isinstance(eval_compare, Mapping):
        _count_failures_from_eval_compare(eval_compare, counters)

    return counters


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _count_failures_from_matrix(report: Mapping[str, Any], counters: MutableMapping[str, int]) -> None:
    per_case = _as_mapping(report.get("per_case_diffs"))

    for row in list(per_case.get("swarm_vs_baseline_single") or []):
        result = _as_mapping(row)
        pass_baseline = bool(result.get("pass_baseline"))
        pass_target = bool(result.get("pass_target"))
        pass_delta = _safe_float(result.get("pass_delta"))
        latency_delta = _safe_float(result.get("latency_delta"))

        if pass_baseline and not pass_target:
            counters["ROUTING_MISS"] += 1
        if is_swarm_loop(latency_delta=latency_delta, pass_delta=pass_delta):
            counters["SWARM_LOOP"] += 1

    for row in list(per_case.get("tool_first_on_vs_off") or []):
        result = _as_mapping(row)
        case_id = str(result.get("case_id", "")).lower()
        pass_baseline = bool(result.get("pass_baseline"))
        pass_target = bool(result.get("pass_target"))
        pass_delta = _safe_float(result.get("pass_delta"))
        tool_delta = _safe_float(result.get("tool_verified_delta"))

        if tool_delta > 0.0 and pass_delta > 0.0:
            if any(token in case_id for token in ("exec", "runtime", "traceback")):
                counters["TOOL_EXEC_FAIL"] += 1
            else:
                counters["TOOL_PARSE_FAIL"] += 1
        elif pass_baseline and not pass_target:
            counters["FORMAT_FAIL"] += 1

    for row in list(per_case.get("memory_on_vs_off") or []):
        result = _as_mapping(row)
        if is_memory_drift(
            pass_delta=result.get("pass_delta"),
            oracle_delta=result.get("oracle_score_delta"),
        ):
            counters["MEMORY_DRIFT"] += 1

    for row in list(per_case.get("dual_gated_vs_baseline_single") or []):
        result = _as_mapping(row)
        if is_dual_regression(pass_delta=result.get("pass_delta")):
            counters["DUAL_REGRESSION"] += 1


def _count_failures_from_eval_report(report: Mapping[str, Any], counters: MutableMapping[str, int]) -> None:
    for result in list(report.get("results") or []):
        output = _as_mapping(_as_mapping(result).get("output"))
        route_trace = _as_mapping(output.get("route_trace"))

        if is_routing_miss(intent=route_trace.get("intent"), chosen_agent=route_trace.get("chosen_agent")):
            counters["ROUTING_MISS"] += 1

        meta = _as_mapping(_as_mapping(output.get("result")).get("meta"))
        tool_first = _as_mapping(meta.get("tool_first"))

        if is_memory_drift(local_hits=_as_mapping(meta.get("memory")).get("local_hits")):
            counters["MEMORY_DRIFT"] += 1

        per_case_classes: set[str] = set()
        for probe_name in ("prompt_probe", "proposal_probe"):
            probe = _as_mapping(tool_first.get(probe_name))
            verification = _as_mapping(probe.get("verification"))
            classified = classify_tool_verification_failure(
                status=verification.get("status"),
                error_type=verification.get("error_type"),
                error_message=verification.get("error_message"),
            )
            if classified is not None:
                per_case_classes.add(classified)

        for category in sorted(per_case_classes):
            counters[category] += 1


def _count_failures_from_dual_eval(report: Mapping[str, Any], counters: MutableMapping[str, int]) -> None:
    summary = _as_mapping(report.get("summary"))
    dual = _as_mapping(summary.get("dual_gated"))
    if is_dual_regression(pass_delta=dual.get("pass_rate_delta_vs_baseline")):
        counters["DUAL_REGRESSION"] += 1


def _count_failures_from_eval_compare(report: Mapping[str, Any], counters: MutableMapping[str, int]) -> None:
    latency = _as_mapping(report.get("avg_latency_proxy"))
    entropy = _as_mapping(report.get("routing_entropy"))
    if is_swarm_loop(latency_delta=latency.get("delta"), entropy_delta=entropy.get("delta")):
        counters["SWARM_LOOP"] += 1


__all__ = [
    "FAILURE_CLASSES",
    "REMEDIATION_BY_CLASS",
    "RemediationAction",
    "classify_tool_verification_failure",
    "default_failure_counters",
    "derive_failure_taxonomy",
    "build_remediation_plan",
    "get_remediation_mapping",
    "is_dual_regression",
    "is_memory_drift",
    "is_routing_miss",
    "is_swarm_loop",
    "RemediationPlanItem",
    "remediation_for",
]
