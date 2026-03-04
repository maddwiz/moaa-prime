#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

FAILURE_CLASSES: tuple[str, ...] = (
    "ROUTING_MISS",
    "TOOL_PARSE_FAIL",
    "TOOL_EXEC_FAIL",
    "FORMAT_FAIL",
    "MEMORY_DRIFT",
    "DUAL_REGRESSION",
    "SWARM_LOOP",
)

REPORT_FILES: dict[str, str] = {
    "eval_matrix": "eval_matrix.json",
    "tool_first_eval": "tool_first_eval.json",
    "dual_gated_eval": "dual_gated_eval.json",
    "eval_compare": "eval_compare.json",
    "eval_report": "eval_report.json",
    "eval_router": "eval_router.json",
    "router_train_report": "router_train_report.json",
    "final_report": "final_report.json",
}


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _pct(value: Any) -> str:
    if value is None:
        return "NA"
    return f"{(100.0 * _safe_float(value)):.2f}%"


def _num(value: Any, *, signed: bool = False) -> str:
    if value is None:
        return "NA"
    if signed:
        return f"{_safe_float(value):+.4f}"
    return f"{_safe_float(value):.4f}"


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing:{path.name}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"invalid:{path.name}:{exc.__class__.__name__}"
    if isinstance(payload, dict):
        return payload, None
    return None, f"invalid:{path.name}:non_object_root"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _extract_matrix_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = _as_mapping(report.get("summary"))
    baseline = _as_mapping(summary.get("baseline_single"))

    def _delta_block(name: str) -> dict[str, Any]:
        block = _as_mapping(summary.get(name))
        return {
            "pass_rate_delta": block.get("pass_rate_delta_vs_baseline"),
            "oracle_delta": block.get("oracle_delta_vs_baseline"),
            "latency_delta": block.get("latency_delta_vs_baseline"),
            "tool_verification_delta": block.get("tool_verification_rate_delta_vs_baseline"),
        }

    return {
        "pass_threshold": report.get("pass_threshold"),
        "baseline": {
            "pass_rate": baseline.get("pass_rate"),
            "avg_oracle_score": baseline.get("avg_oracle_score"),
            "avg_latency_proxy": baseline.get("avg_latency_proxy"),
            "tool_verification_rate": baseline.get("tool_verification_rate"),
        },
        "swarm": _delta_block("swarm"),
        "dual_gated": _delta_block("dual_gated"),
        "tool_first": _delta_block("tool_first"),
        "memory": _delta_block("memory"),
        "sfc": _delta_block("sfc"),
    }


def _count_failures_from_matrix(report: Mapping[str, Any], counters: dict[str, int]) -> None:
    per_case = _as_mapping(report.get("per_case_diffs"))

    for row in list(per_case.get("swarm_vs_baseline_single") or []):
        r = _as_mapping(row)
        pass_baseline = bool(r.get("pass_baseline"))
        pass_target = bool(r.get("pass_target"))
        pass_delta = _safe_float(r.get("pass_delta"))
        latency_delta = _safe_float(r.get("latency_delta"))

        if pass_baseline and not pass_target:
            counters["ROUTING_MISS"] += 1
        if latency_delta > 0.0 and pass_delta <= 0.0:
            counters["SWARM_LOOP"] += 1

    for row in list(per_case.get("tool_first_on_vs_off") or []):
        r = _as_mapping(row)
        case_id = str(r.get("case_id", "")).lower()
        pass_baseline = bool(r.get("pass_baseline"))
        pass_target = bool(r.get("pass_target"))
        pass_delta = _safe_float(r.get("pass_delta"))
        tool_delta = _safe_float(r.get("tool_verified_delta"))

        if tool_delta > 0.0 and pass_delta > 0.0:
            if any(token in case_id for token in ("exec", "runtime", "traceback")):
                counters["TOOL_EXEC_FAIL"] += 1
            else:
                counters["TOOL_PARSE_FAIL"] += 1
        elif pass_baseline and not pass_target:
            counters["FORMAT_FAIL"] += 1

    for row in list(per_case.get("memory_on_vs_off") or []):
        r = _as_mapping(row)
        pass_delta = _safe_float(r.get("pass_delta"))
        oracle_delta = _safe_float(r.get("oracle_score_delta"))
        if pass_delta < 0.0 or (pass_delta == 0.0 and oracle_delta < 0.0):
            counters["MEMORY_DRIFT"] += 1

    for row in list(per_case.get("dual_gated_vs_baseline_single") or []):
        r = _as_mapping(row)
        if _safe_float(r.get("pass_delta")) < 0.0:
            counters["DUAL_REGRESSION"] += 1


def _count_failures_from_eval_report(report: Mapping[str, Any], counters: dict[str, int]) -> None:
    parse_tokens = (
        "no_python_source_found",
        "extract",
        "parse",
        "syntax",
    )
    exec_tokens = (
        "exec",
        "runtime",
        "nameerror",
        "typeerror",
        "zerodivision",
        "timeout",
    )

    for result in list(report.get("results") or []):
        r = _as_mapping(result)
        output = _as_mapping(r.get("output"))
        route_trace = _as_mapping(output.get("route_trace"))

        intent = str(route_trace.get("intent", "")).strip().lower()
        chosen_agent = str(route_trace.get("chosen_agent", "")).strip().lower()
        if intent == "math" and chosen_agent and "math" not in chosen_agent:
            counters["ROUTING_MISS"] += 1
        if intent == "code" and chosen_agent and "code" not in chosen_agent:
            counters["ROUTING_MISS"] += 1

        meta = _as_mapping(_as_mapping(output.get("result")).get("meta"))
        tool_first = _as_mapping(meta.get("tool_first"))

        local_hits = _safe_float(_as_mapping(meta.get("memory")).get("local_hits"), default=0.0)
        if local_hits < 0.0:
            counters["MEMORY_DRIFT"] += 1

        per_case_classes: set[str] = set()
        for probe_name in ("prompt_probe", "proposal_probe"):
            probe = _as_mapping(tool_first.get(probe_name))
            verification = _as_mapping(probe.get("verification"))
            status = str(verification.get("status", "")).strip().lower()
            if status != "fail":
                continue

            error_text = (
                f"{verification.get('error_type', '')} {verification.get('error_message', '')}"
            ).lower()
            if any(token in error_text for token in parse_tokens):
                per_case_classes.add("TOOL_PARSE_FAIL")
            elif any(token in error_text for token in exec_tokens):
                per_case_classes.add("TOOL_EXEC_FAIL")
            else:
                per_case_classes.add("FORMAT_FAIL")

        for category in sorted(per_case_classes):
            counters[category] += 1


def _count_failures_from_dual_eval(report: Mapping[str, Any], counters: dict[str, int]) -> None:
    summary = _as_mapping(report.get("summary"))
    dual = _as_mapping(summary.get("dual_gated"))
    if _safe_float(dual.get("pass_rate_delta_vs_baseline")) < 0.0:
        counters["DUAL_REGRESSION"] += 1


def _count_failures_from_eval_compare(report: Mapping[str, Any], counters: dict[str, int]) -> None:
    latency = _as_mapping(report.get("avg_latency_proxy"))
    entropy = _as_mapping(report.get("routing_entropy"))
    if _safe_float(latency.get("delta")) > 0.0 and _safe_float(entropy.get("delta")) <= 0.0:
        counters["SWARM_LOOP"] += 1


def _derive_failure_taxonomy(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    counters = {name: 0 for name in FAILURE_CLASSES}

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


def build_dashboard(report_dir: Path) -> dict[str, Any]:
    artifacts: dict[str, dict[str, Any]] = {}
    reports: dict[str, Mapping[str, Any]] = {}
    warnings: list[str] = []

    for key in sorted(REPORT_FILES.keys()):
        filename = REPORT_FILES[key]
        path = report_dir / filename
        payload, error = _load_json(path)
        status = "ok"
        if error is not None:
            status = "missing" if error.startswith("missing:") else "invalid"
            warnings.append(error)
        if payload is not None:
            reports[key] = payload
        artifacts[key] = {
            "path": str(path),
            "status": status,
        }

    matrix_summary: dict[str, Any] = {}
    if "eval_matrix" in reports:
        matrix_summary = _extract_matrix_summary(reports["eval_matrix"])

    tool_first = _as_mapping(reports.get("tool_first_eval", {}))
    tool_first_overall = _as_mapping(tool_first.get("overall"))

    dual_eval = _as_mapping(reports.get("dual_gated_eval", {}))
    dual_summary = _as_mapping(_as_mapping(dual_eval.get("summary")).get("dual_gated"))

    router_eval = _as_mapping(reports.get("eval_router", {}))
    routing_accuracy = _as_mapping(router_eval.get("routing_accuracy"))
    oracle_gain = _as_mapping(router_eval.get("oracle_score_gain"))
    latency_efficiency = _as_mapping(router_eval.get("latency_efficiency"))

    router_train = _as_mapping(reports.get("router_train_report", {}))

    final_report = _as_mapping(reports.get("final_report", {}))

    failure_taxonomy = _derive_failure_taxonomy(reports)

    return {
        "dashboard_version": "pr7.v1",
        "reports_dir": str(report_dir),
        "artifacts": artifacts,
        "warnings": warnings,
        "matrix": matrix_summary,
        "focused_eval": {
            "tool_first_pass_rate_delta": tool_first_overall.get("pass_rate_delta"),
            "dual_gate_pass_rate_delta": dual_summary.get("pass_rate_delta_vs_baseline"),
            "dual_gate_trigger_rate": dual_summary.get("trigger_rate"),
        },
        "router": {
            "routing_accuracy_delta": routing_accuracy.get("delta"),
            "oracle_score_gain_delta": oracle_gain.get("delta"),
            "latency_efficiency_delta": latency_efficiency.get("delta"),
            "training_accuracy": router_train.get("training_accuracy"),
            "training_brier_score": router_train.get("training_brier_score"),
            "training_ece": router_train.get("training_ece"),
        },
        "failure_taxonomy": {
            "source": "derived_from_reports",
            "counts": failure_taxonomy,
        },
        "verdict": str(final_report.get("verdict", "")),
    }


def render_text(dashboard: Mapping[str, Any]) -> str:
    lines: list[str] = []
    lines.append("MOAA-Prime Dashboard")
    lines.append(f"dashboard_version: {dashboard.get('dashboard_version', 'NA')}")
    lines.append(f"reports_dir: {dashboard.get('reports_dir', 'NA')}")

    warnings = list(dashboard.get("warnings") or [])
    lines.append(f"warnings: {len(warnings)}")
    for warning in warnings:
        lines.append(f"warning: {warning}")

    lines.append("== Artifacts ==")
    artifacts = _as_mapping(dashboard.get("artifacts"))
    for key in sorted(artifacts.keys()):
        item = _as_mapping(artifacts.get(key))
        lines.append(
            f"artifact.{key}.status={item.get('status', 'NA')} artifact.{key}.path={item.get('path', 'NA')}"
        )

    lines.append("== Mode Deltas ==")
    matrix = _as_mapping(dashboard.get("matrix"))
    baseline = _as_mapping(matrix.get("baseline"))
    lines.append(f"pass_threshold={_num(matrix.get('pass_threshold'))}")
    lines.append(
        "baseline pass_rate={pass_rate} oracle={oracle} latency={latency} tool_verify={tool_verify}".format(
            pass_rate=_pct(baseline.get("pass_rate")),
            oracle=_num(baseline.get("avg_oracle_score")),
            latency=_num(baseline.get("avg_latency_proxy")),
            tool_verify=_pct(baseline.get("tool_verification_rate")),
        )
    )

    for name in ("swarm", "dual_gated", "tool_first", "memory", "sfc"):
        block = _as_mapping(matrix.get(name))
        lines.append(
            "{name} pass_delta={pass_delta} oracle_delta={oracle_delta} latency_delta={latency_delta} tool_verify_delta={tv_delta}".format(
                name=name,
                pass_delta=_num(block.get("pass_rate_delta"), signed=True),
                oracle_delta=_num(block.get("oracle_delta"), signed=True),
                latency_delta=_num(block.get("latency_delta"), signed=True),
                tv_delta=_num(block.get("tool_verification_delta"), signed=True),
            )
        )

    lines.append("== Focused Evals ==")
    focused = _as_mapping(dashboard.get("focused_eval"))
    lines.append(
        "tool_first.pass_rate_delta={value}".format(
            value=_num(focused.get("tool_first_pass_rate_delta"), signed=True)
        )
    )
    lines.append(
        "dual_gate.pass_rate_delta={value} dual_gate.trigger_rate={trigger}".format(
            value=_num(focused.get("dual_gate_pass_rate_delta"), signed=True),
            trigger=_pct(focused.get("dual_gate_trigger_rate")),
        )
    )

    lines.append("== Router ==")
    router = _as_mapping(dashboard.get("router"))
    lines.append(f"router.routing_accuracy_delta={_num(router.get('routing_accuracy_delta'), signed=True)}")
    lines.append(f"router.oracle_score_gain_delta={_num(router.get('oracle_score_gain_delta'), signed=True)}")
    lines.append(f"router.latency_efficiency_delta={_num(router.get('latency_efficiency_delta'), signed=True)}")
    lines.append(f"router.training_accuracy={_num(router.get('training_accuracy'))}")
    lines.append(f"router.training_brier_score={_num(router.get('training_brier_score'))}")
    lines.append(f"router.training_ece={_num(router.get('training_ece'))}")

    lines.append("== Failure Taxonomy ==")
    taxonomy = _as_mapping(dashboard.get("failure_taxonomy"))
    counts = _as_mapping(taxonomy.get("counts"))
    lines.append(f"taxonomy.source={taxonomy.get('source', 'NA')}")
    for name in FAILURE_CLASSES:
        lines.append(f"{name}: {int(_safe_float(counts.get(name), default=0.0))}")

    lines.append("== Verdict ==")
    verdict = str(dashboard.get("verdict", "")).strip() or "NA"
    lines.append(f"verdict={verdict}")

    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render MoAA-Prime telemetry dashboard from report artifacts.")
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory containing report JSON artifacts (default: reports)",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=("text", "json"),
        help="Output format (default: text)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report_dir = Path(args.reports_dir)

    dashboard = build_dashboard(report_dir)

    if args.format == "json":
        print(json.dumps(dashboard, indent=2, sort_keys=True))
    else:
        print(render_text(dashboard))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
