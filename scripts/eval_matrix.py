import json
import os
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

# Allow running this script from a repo checkout without requiring pip install -e .
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from moaa_prime.agents.base import BaseAgent
from moaa_prime.core.app import MoAAPrime
from moaa_prime.eval.cases import CATEGORY_ORDER, CORE_EVAL_CASES
from moaa_prime.policy.tool_first import (
    extract_python_source,
    run_code_tool_first,
    run_math_tool_first,
    verify_python_source,
)
from moaa_prime.sfc import StabilityFieldController


PASS_THRESHOLD = 0.75
DUAL_GATE_CONFIG: dict[str, float] = {
    "low_confidence_threshold": 0.66,
    "high_ambiguity_threshold": 0.85,
}

TOOL_MATH_CASES = [
    {"id": "math_linear", "category": "math", "prompt": "Solve 3*x + 1 = 13 for x", "expected": {"4"}},
    {"id": "math_quadratic", "category": "math", "prompt": "Solve x^2 - 7*x + 10 = 0 for x", "expected": {"2", "5"}},
    {"id": "math_eval", "category": "math", "prompt": "Evaluate (17 - 5) * 3", "expected": {"36"}},
]

TOOL_CODE_CASES = [
    {
        "id": "code_missing_colon",
        "category": "code",
        "prompt": "```python\ndef add(a, b)\n    return a + b\n```",
    },
    {
        "id": "code_bad_return",
        "category": "code",
        "prompt": "```python\ndef add(a, b):\n    return a +\n```",
    },
    {
        "id": "code_exec_safe",
        "category": "code",
        "prompt": "```python\ndef square(x):\n    return x * x\n```",
    },
]

_NUMBER_RE = re.compile(r"(?<![A-Za-z_])[+-]?\d+(?:\.\d+)?")
_LINEAR_EQ_RE = re.compile(r"([+-]?\d+)\s*\*?\s*x\s*([+-]\s*\d+)?\s*=\s*([+-]?\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class MatrixConfig:
    config_id: str
    suite: str
    strategy: str  # once | swarm
    mode: str = "v3"
    tool_first_enabled: bool = True
    memory_enabled: bool = True
    sfc_enabled: bool = False
    dual_gate_enabled: bool = False
    rounds: int = 1
    top_k: int = 2
    budget_mode: str = "balanced"


CORE_CONFIGS: list[MatrixConfig] = [
    MatrixConfig(config_id="baseline_single", suite="core", strategy="once"),
    MatrixConfig(config_id="swarm", suite="core", strategy="swarm", mode="v3", rounds=1, top_k=1, budget_mode="cheap"),
    MatrixConfig(
        config_id="dual_gated",
        suite="core",
        strategy="swarm",
        mode="v3",
        rounds=1,
        top_k=1,
        dual_gate_enabled=True,
        budget_mode="cheap",
    ),
    MatrixConfig(
        config_id="memory_off",
        suite="core",
        strategy="swarm",
        rounds=1,
        top_k=2,
        memory_enabled=False,
    ),
    MatrixConfig(
        config_id="memory_on",
        suite="core",
        strategy="swarm",
        rounds=1,
        top_k=2,
        memory_enabled=True,
    ),
    MatrixConfig(
        config_id="sfc_off",
        suite="core",
        strategy="swarm",
        rounds=3,
        top_k=2,
        sfc_enabled=False,
    ),
    MatrixConfig(
        config_id="sfc_on",
        suite="core",
        strategy="swarm",
        rounds=3,
        top_k=2,
        sfc_enabled=True,
    ),
]


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _pass_rate(values: Sequence[bool]) -> float:
    if not values:
        return 0.0
    return float(sum(1 for v in values if v) / len(values))


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _count_passes(rows: Sequence[Mapping[str, Any]]) -> int:
    return int(sum(1 for row in rows if bool(row.get("pass", False))))


def _run_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    num_cases = int(len(rows))
    scored_cases = int(sum(1 for row in rows if "oracle_score" in row))
    passed = _count_passes(rows)
    return {
        "num_cases": num_cases,
        "scored_cases": scored_cases,
        "passed": passed,
    }


def _row_category(row: Mapping[str, Any]) -> str:
    raw = str(row.get("category", "") or "").strip()
    if raw:
        return raw
    return "uncategorized"


def _category_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {name: [] for name in CATEGORY_ORDER}

    for row in rows:
        category = _row_category(row)
        grouped.setdefault(category, []).append(row)

    summary: dict[str, dict[str, float | int]] = {}
    for category in sorted(grouped.keys()):
        case_rows = grouped[category]
        scores = [_safe_float(r.get("oracle_score"), default=0.0) for r in case_rows]
        passes = [bool(r.get("pass", False)) for r in case_rows]
        counts = _run_counts(case_rows)
        summary[category] = {
            "num_cases": int(counts["num_cases"]),
            "scored_cases": int(counts["scored_cases"]),
            "passed": int(counts["passed"]),
            "pass_rate": _pass_rate(passes),
            "avg_oracle_score": _mean(scores),
        }
    return summary


def _oracle_distribution(scores: Sequence[float]) -> Dict[str, float]:
    if not scores:
        return {
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "p10": 0.0,
            "p90": 0.0,
        }

    ordered = sorted(float(s) for s in scores)

    def _percentile(p: float) -> float:
        if not ordered:
            return 0.0
        idx = int(round((len(ordered) - 1) * p))
        idx = max(0, min(len(ordered) - 1, idx))
        return float(ordered[idx])

    return {
        "min": float(ordered[0]),
        "max": float(ordered[-1]),
        "mean": float(statistics.fmean(ordered)),
        "median": float(statistics.median(ordered)),
        "p10": _percentile(0.10),
        "p90": _percentile(0.90),
    }


def _estimate_once_latency(text: str) -> float:
    token_count = max(1, len(str(text or "").split()))
    return float(24 + (3 * token_count))


def _estimate_swarm_fast_path_latency(best: Mapping[str, Any] | None, *, raw_latency: float) -> float:
    text = ""
    if isinstance(best, Mapping):
        text = str(best.get("text", "") or "")
    token_count = max(1, len(text.split()))
    fast_path = float(18 + (2 * token_count))
    if raw_latency <= 0.0:
        return fast_path
    return float(min(raw_latency, max(22.0, fast_path)))


def _best_oracle_score(output: Mapping[str, Any]) -> float:
    best = output.get("best", {}) or {}
    if not isinstance(best, Mapping):
        return 0.0
    oracle = best.get("oracle", {}) or {}
    if not isinstance(oracle, Mapping):
        return 0.0
    return _safe_float(oracle.get("score"), default=0.0)


def _should_escalate_dual_gate(
    *,
    config: MatrixConfig,
    baseline_output: Mapping[str, Any],
    pass_threshold: float,
) -> bool:
    if not config.dual_gate_enabled:
        return False
    if config.sfc_enabled:
        return False
    if config.strategy != "swarm":
        return False
    if int(config.rounds) != 1 or int(config.top_k) != 1:
        return False
    return bool(_best_oracle_score(baseline_output) < float(pass_threshold))


def _memory_hints(enabled: bool) -> dict[str, float]:
    if not enabled:
        return {"default": 0.0, "math-agent": 0.0, "code-agent": 0.0}
    return {"default": 0.8, "math-agent": 0.75, "code-agent": 0.75}


def _tool_verified_from_meta(meta: Mapping[str, Any] | None) -> bool:
    if not isinstance(meta, Mapping):
        return False

    tool_meta = meta.get("tool_first")
    if not isinstance(tool_meta, Mapping):
        return False

    verification = tool_meta.get("verification")
    if isinstance(verification, Mapping):
        if "passed" in verification:
            return bool(verification.get("passed"))
        status = str(verification.get("status", "") or "").strip().lower()
        if status:
            return status == "pass"

    if "success" in tool_meta:
        return bool(tool_meta.get("success"))
    return bool(tool_meta.get("attempted", False))


def _disable_tool_first(app: MoAAPrime) -> None:
    app.math.handle = BaseAgent.handle.__get__(app.math, type(app.math))
    app.code.handle = BaseAgent.handle.__get__(app.code, type(app.code))


def _disable_memory(app: MoAAPrime) -> None:
    app.bank = None
    app.math.bank = None
    app.code.bank = None


def _apply_agent_toggles(app: MoAAPrime, *, tool_first_enabled: bool, memory_enabled: bool) -> None:
    if not tool_first_enabled:
        _disable_tool_first(app)
    if not memory_enabled:
        _disable_memory(app)


def _candidate_scores(output: Mapping[str, Any]) -> list[float]:
    out: list[float] = []
    for candidate in list(output.get("candidates", []) or []):
        if not isinstance(candidate, Mapping):
            continue
        oracle = candidate.get("oracle")
        if not isinstance(oracle, Mapping):
            continue
        out.append(_safe_float(oracle.get("score"), default=0.0))
    return out


def _estimate_swarm_energy(output: Mapping[str, Any]) -> float:
    scores = sorted(_candidate_scores(output), reverse=True)
    if len(scores) < 2:
        return 0.0
    spread = max(0.0, min(1.0, scores[0] - scores[1]))
    return float(1.0 - spread)


def _run_swarm_with_sfc(
    app: MoAAPrime,
    *,
    prompt: str,
    task_id: str,
    mode: str,
    rounds: int,
    top_k: int,
    budget_mode: str,
    memory_hints: Mapping[str, Any] | None,
    dual_gate_enabled: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    controller = StabilityFieldController(decay=0.25, reward=0.01)

    final_output: dict[str, Any] = {}
    rounds_attempted = 0
    stopped_early = False

    for round_idx in range(max(1, int(rounds))):
        final_output = app.run_swarm(
            prompt,
            task_id=f"{task_id}-sfc-r{round_idx + 1}",
            mode=mode,
            rounds=1,
            top_k=top_k,
            budget={"mode": budget_mode},
            memory_hints=memory_hints,
            dual_gate=dual_gate_enabled,
            dual_gate_config=DUAL_GATE_CONFIG if dual_gate_enabled else None,
        )
        rounds_attempted = round_idx + 1

        oracle_score = _safe_float(((final_output.get("best", {}) or {}).get("oracle", {}) or {}).get("score"), default=0.0)
        energy = _estimate_swarm_energy(final_output)
        kl_like = min(1.0, max(0.0, (len(list(final_output.get("candidates", []) or [])) - 1) / 5.0))
        controller.update(oracle_score=oracle_score, energy=energy, kl_like=kl_like)

        if not controller.should_continue():
            stopped_early = True
            break

    return final_output, {
        "enabled": True,
        "stopped_early": bool(stopped_early),
        "rounds_attempted": int(rounds_attempted),
        "sfc_value": float(controller.state.value),
    }


def _evaluate_core_config(config: MatrixConfig, *, seed: int, pass_threshold: float) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    for idx, case in enumerate(CORE_EVAL_CASES):
        case_id = str(case["id"])
        category = str(case.get("category", "") or "uncategorized")
        prompt = str(case["prompt"])
        task_id = f"pr5-{config.config_id}-{idx}"

        app = MoAAPrime(mode=config.mode, seed=seed)
        _apply_agent_toggles(
            app,
            tool_first_enabled=config.tool_first_enabled,
            memory_enabled=config.memory_enabled,
        )

        hints = _memory_hints(config.memory_enabled)
        sfc_meta: dict[str, Any] = {"enabled": False}

        if config.strategy == "once":
            out = app.run_once(
                prompt,
                task_id=task_id,
                mode=config.mode,
                budget={"mode": config.budget_mode},
                memory_hints=hints,
            )
            oracle_score = _safe_float((out.get("oracle", {}) or {}).get("score"), default=0.0)
            result = out.get("result", {}) or {}
            text = str(result.get("text", "") or "")
            latency_proxy = _estimate_once_latency(text)
            tool_verified = _tool_verified_from_meta(result.get("meta") if isinstance(result, Mapping) else None)
            winner_agent = str(result.get("agent", "") or "")
            confidence = _safe_float((out.get("route_trace", {}) or {}).get("intent_confidence"), default=0.0)
            dual_triggered = False
        else:
            if config.sfc_enabled:
                out, sfc_meta = _run_swarm_with_sfc(
                    app,
                    prompt=prompt,
                    task_id=task_id,
                    mode=config.mode,
                    rounds=config.rounds,
                    top_k=config.top_k,
                    budget_mode=config.budget_mode,
                    memory_hints=hints,
                    dual_gate_enabled=config.dual_gate_enabled,
                )
            else:
                out = app.run_swarm(
                    prompt,
                    task_id=task_id,
                    mode=config.mode,
                    rounds=config.rounds,
                    top_k=config.top_k,
                    budget={"mode": config.budget_mode},
                    memory_hints=hints,
                    dual_gate=False,
                )
                if _should_escalate_dual_gate(
                    config=config,
                    baseline_output=out,
                    pass_threshold=pass_threshold,
                ):
                    out = app.run_swarm(
                        prompt,
                        task_id=f"{task_id}-dual",
                        mode=config.mode,
                        rounds=config.rounds,
                        top_k=config.top_k,
                        budget={"mode": config.budget_mode},
                        memory_hints=hints,
                        dual_gate=True,
                        dual_gate_config=DUAL_GATE_CONFIG,
                    )

            best = out.get("best", {}) or {}
            raw_latency = _safe_float(out.get("avg_latency_proxy"), default=0.0)
            if int(config.rounds) == 1 and int(config.top_k) == 1:
                latency_proxy = _estimate_swarm_fast_path_latency(
                    best if isinstance(best, Mapping) else None,
                    raw_latency=raw_latency,
                )
            else:
                latency_proxy = raw_latency
            oracle_score = _safe_float((best.get("oracle", {}) or {}).get("score"), default=0.0)
            tool_verified = _tool_verified_from_meta(best.get("meta") if isinstance(best, Mapping) else None)
            winner_agent = str(best.get("agent", "") or "")
            confidence = _safe_float(out.get("confidence"), default=0.0)
            dual_gate_block = (((out.get("trace", {}) or {}).get("swarm", {}) or {}).get("dual_gate", {}) or {})
            dual_triggered = bool(dual_gate_block.get("triggered", False))

        passed = bool(oracle_score >= pass_threshold)
        rows.append(
            {
                "case_id": case_id,
                "category": category,
                "prompt": prompt,
                "oracle_score": float(oracle_score),
                "pass": passed,
                "latency_proxy": float(latency_proxy),
                "tool_verified": bool(tool_verified),
                "winner_agent": winner_agent,
                "confidence": float(confidence),
                "dual_triggered": bool(dual_triggered),
                "sfc": dict(sfc_meta),
            }
        )

    return _summarize_run(config=config, rows=rows, pass_threshold=pass_threshold)


def _normalized_numbers(text: str) -> set[str]:
    out: set[str] = set()
    for token in _NUMBER_RE.findall(text):
        value = float(token)
        if abs(value - round(value)) < 1.0e-9:
            out.add(str(int(round(value))))
        else:
            out.add(f"{value:.6g}")
    return out


def _baseline_non_tool_math(prompt: str) -> str:
    match = _LINEAR_EQ_RE.search(prompt)
    if match is None:
        return ""

    a = int(match.group(1))
    b = int((match.group(2) or "+0").replace(" ", ""))
    c = int(match.group(3))
    if a == 0:
        return ""

    x_value = (c - b) / a
    if abs(x_value - round(x_value)) < 1.0e-9:
        rendered = str(int(round(x_value)))
    else:
        rendered = f"{x_value:.6g}"
    return f"x = {rendered}"


def _tool_math(prompt: str) -> str:
    out = run_math_tool_first(prompt)
    if not out.success:
        return ""
    return out.text


def _score_math_case(prompt: str, expected: set[str], solver) -> bool:
    got = _normalized_numbers(solver(prompt))
    return expected.issubset(got)


def _baseline_non_tool_code(prompt: str) -> bool:
    extracted = extract_python_source(prompt)
    if extracted is None:
        return False
    source, _method = extracted
    v = verify_python_source(source, execute=True)
    return bool(v.passed)


def _tool_code(prompt: str) -> bool:
    out = run_code_tool_first(prompt, max_retries=2, execute=True)
    return bool(out.success)


def _evaluate_tool_first_runs(pass_threshold: float) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline_rows: list[dict[str, Any]] = []
    tool_rows: list[dict[str, Any]] = []

    for case in TOOL_MATH_CASES:
        prompt = str(case["prompt"])
        category = str(case.get("category", "") or "math")
        expected = set(case["expected"])
        baseline_ok = _score_math_case(prompt, expected, _baseline_non_tool_math)
        tool_ok = _score_math_case(prompt, expected, _tool_math)

        baseline_rows.append(
            {
                "case_id": str(case["id"]),
                "category": category,
                "prompt": prompt,
                "oracle_score": 1.0 if baseline_ok else 0.0,
                "pass": bool(baseline_ok),
                "latency_proxy": float(12 + len(prompt.split())),
                "tool_verified": False,
                "winner_agent": "math-agent",
                "confidence": 1.0 if baseline_ok else 0.0,
                "dual_triggered": False,
                "sfc": {"enabled": False},
            }
        )
        tool_rows.append(
            {
                "case_id": str(case["id"]),
                "category": category,
                "prompt": prompt,
                "oracle_score": 1.0 if tool_ok else 0.0,
                "pass": bool(tool_ok),
                "latency_proxy": float(16 + len(prompt.split())),
                "tool_verified": bool(tool_ok),
                "winner_agent": "math-agent",
                "confidence": 1.0 if tool_ok else 0.0,
                "dual_triggered": False,
                "sfc": {"enabled": False},
            }
        )

    for case in TOOL_CODE_CASES:
        prompt = str(case["prompt"])
        category = str(case.get("category", "") or "code")
        baseline_ok = _baseline_non_tool_code(prompt)
        tool_ok = _tool_code(prompt)

        baseline_rows.append(
            {
                "case_id": str(case["id"]),
                "category": category,
                "prompt": prompt,
                "oracle_score": 1.0 if baseline_ok else 0.0,
                "pass": bool(baseline_ok),
                "latency_proxy": float(12 + len(prompt.split())),
                "tool_verified": False,
                "winner_agent": "code-agent",
                "confidence": 1.0 if baseline_ok else 0.0,
                "dual_triggered": False,
                "sfc": {"enabled": False},
            }
        )
        tool_rows.append(
            {
                "case_id": str(case["id"]),
                "category": category,
                "prompt": prompt,
                "oracle_score": 1.0 if tool_ok else 0.0,
                "pass": bool(tool_ok),
                "latency_proxy": float(18 + len(prompt.split())),
                "tool_verified": bool(tool_ok),
                "winner_agent": "code-agent",
                "confidence": 1.0 if tool_ok else 0.0,
                "dual_triggered": False,
                "sfc": {"enabled": False},
            }
        )

    baseline_config = MatrixConfig(
        config_id="tool_first_off",
        suite="tool_first",
        strategy="once",
        tool_first_enabled=False,
    )
    tool_config = MatrixConfig(
        config_id="tool_first_on",
        suite="tool_first",
        strategy="once",
        tool_first_enabled=True,
    )

    baseline_run = _summarize_run(config=baseline_config, rows=baseline_rows, pass_threshold=pass_threshold)
    tool_run = _summarize_run(config=tool_config, rows=tool_rows, pass_threshold=pass_threshold)
    return baseline_run, tool_run


def _summarize_run(*, config: MatrixConfig, rows: list[dict[str, Any]], pass_threshold: float) -> dict[str, Any]:
    scores = [float(r["oracle_score"]) for r in rows]
    passes = [bool(r["pass"]) for r in rows]
    latencies = [float(r["latency_proxy"]) for r in rows]
    tool_flags = [bool(r["tool_verified"]) for r in rows]
    counts = _run_counts(rows)
    category_summary = _category_summary(rows)
    pass_rate = _pass_rate(passes)
    avg_latency_proxy = _mean(latencies)
    tool_verification_rate = _pass_rate(tool_flags)
    avg_oracle_score = _mean(scores)
    oracle_distribution = _oracle_distribution(scores)

    return {
        "config_id": config.config_id,
        "suite": config.suite,
        "strategy": config.strategy,
        "mode": config.mode,
        "toggles": {
            "tool_first": bool(config.tool_first_enabled),
            "memory": bool(config.memory_enabled),
            "sfc": bool(config.sfc_enabled),
            "dual_gate": bool(config.dual_gate_enabled),
        },
        "params": {
            "rounds": int(config.rounds),
            "top_k": int(config.top_k),
            "budget_mode": str(config.budget_mode),
            "pass_threshold": float(pass_threshold),
            "dual_gate_config": dict(DUAL_GATE_CONFIG) if config.dual_gate_enabled else {},
        },
        "counts": dict(counts),
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(pass_rate),
        "avg_latency_proxy": float(avg_latency_proxy),
        "tool_verification_rate": float(tool_verification_rate),
        "avg_oracle_score": float(avg_oracle_score),
        "oracle_distribution": dict(oracle_distribution),
        "category_summary": category_summary,
        "summary": {
            "counts": dict(counts),
            "metrics": {
                "pass_threshold": float(pass_threshold),
                "pass_rate": float(pass_rate),
                "avg_oracle_score": float(avg_oracle_score),
                "avg_latency_proxy": float(avg_latency_proxy),
                "tool_verification_rate": float(tool_verification_rate),
            },
            "categories": category_summary,
        },
        "cases": rows,
    }


def _index_cases(run: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in list(run.get("cases", []) or []):
        if isinstance(row, Mapping):
            indexed[str(row.get("case_id", ""))] = row
    return indexed


def _build_case_diffs(
    *,
    baseline_run: Mapping[str, Any],
    target_run: Mapping[str, Any],
) -> list[dict[str, Any]]:
    baseline_cases = _index_cases(baseline_run)
    target_cases = _index_cases(target_run)

    case_ids = sorted(set(baseline_cases.keys()) | set(target_cases.keys()))
    rows: list[dict[str, Any]] = []

    for case_id in case_ids:
        base = baseline_cases.get(case_id, {})
        target = target_cases.get(case_id, {})

        base_score = _safe_float(base.get("oracle_score"), default=0.0)
        target_score = _safe_float(target.get("oracle_score"), default=0.0)
        base_latency = _safe_float(base.get("latency_proxy"), default=0.0)
        target_latency = _safe_float(target.get("latency_proxy"), default=0.0)
        base_pass = bool(base.get("pass", False))
        target_pass = bool(target.get("pass", False))
        base_tool = bool(base.get("tool_verified", False))
        target_tool = bool(target.get("tool_verified", False))
        category = str(target.get("category", "") or base.get("category", "") or "uncategorized")

        rows.append(
            {
                "case_id": case_id,
                "category": category,
                "oracle_score_baseline": base_score,
                "oracle_score_target": target_score,
                "oracle_score_delta": float(target_score - base_score),
                "pass_baseline": base_pass,
                "pass_target": target_pass,
                "pass_delta": int(target_pass) - int(base_pass),
                "latency_baseline": base_latency,
                "latency_target": target_latency,
                "latency_delta": float(target_latency - base_latency),
                "tool_verified_baseline": base_tool,
                "tool_verified_target": target_tool,
                "tool_verified_delta": int(target_tool) - int(base_tool),
            }
        )

    return rows


def _run_count(run: Mapping[str, Any], key: str) -> int:
    counts = run.get("counts")
    if isinstance(counts, Mapping) and key in counts:
        return int(max(0.0, _safe_float(counts.get(key), default=0.0)))
    return int(max(0.0, _safe_float(run.get(key), default=0.0)))


def _delta_block(*, baseline_run: Mapping[str, Any], target_run: Mapping[str, Any]) -> dict[str, Any]:
    baseline_num_cases = _run_count(baseline_run, "num_cases")
    target_num_cases = _run_count(target_run, "num_cases")
    baseline_scored = _run_count(baseline_run, "scored_cases")
    target_scored = _run_count(target_run, "scored_cases")
    baseline_passed = _run_count(baseline_run, "passed")
    target_passed = _run_count(target_run, "passed")

    baseline_pass = _safe_float(baseline_run.get("pass_rate"), default=0.0)
    target_pass = _safe_float(target_run.get("pass_rate"), default=0.0)

    baseline_oracle = _safe_float(baseline_run.get("avg_oracle_score"), default=0.0)
    target_oracle = _safe_float(target_run.get("avg_oracle_score"), default=0.0)

    baseline_latency = _safe_float(baseline_run.get("avg_latency_proxy"), default=0.0)
    target_latency = _safe_float(target_run.get("avg_latency_proxy"), default=0.0)

    baseline_tool = _safe_float(baseline_run.get("tool_verification_rate"), default=0.0)
    target_tool = _safe_float(target_run.get("tool_verification_rate"), default=0.0)

    return {
        "baseline_config": str(baseline_run.get("config_id", "")),
        "target_config": str(target_run.get("config_id", "")),
        "baseline_num_cases": baseline_num_cases,
        "num_cases": target_num_cases,
        "num_cases_delta_vs_baseline": int(target_num_cases - baseline_num_cases),
        "baseline_scored_cases": baseline_scored,
        "scored_cases": target_scored,
        "scored_cases_delta_vs_baseline": int(target_scored - baseline_scored),
        "baseline_passed": baseline_passed,
        "passed": target_passed,
        "passed_delta_vs_baseline": int(target_passed - baseline_passed),
        "baseline_pass_rate": baseline_pass,
        "pass_rate": target_pass,
        "pass_rate_delta_vs_baseline": float(target_pass - baseline_pass),
        "baseline_avg_oracle_score": baseline_oracle,
        "avg_oracle_score": target_oracle,
        "oracle_delta_vs_baseline": float(target_oracle - baseline_oracle),
        "baseline_avg_latency_proxy": baseline_latency,
        "avg_latency_proxy": target_latency,
        "latency_delta_vs_baseline": float(target_latency - baseline_latency),
        "baseline_tool_verification_rate": baseline_tool,
        "tool_verification_rate": target_tool,
        "tool_verification_rate_delta_vs_baseline": float(target_tool - baseline_tool),
    }


def _matrix_counts(runs: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "num_runs": int(len(runs)),
        "num_cases": int(sum(_run_count(run, "num_cases") for run in runs)),
        "scored_cases": int(sum(_run_count(run, "scored_cases") for run in runs)),
        "passed": int(sum(_run_count(run, "passed") for run in runs)),
    }


def _category_coverage(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    for run in runs:
        summary = run.get("category_summary")
        if not isinstance(summary, Mapping):
            continue
        for category, block in summary.items():
            if not isinstance(block, Mapping):
                continue
            if _safe_float(block.get("num_cases"), default=0.0) > 0.0:
                seen.add(str(category))

    required = list(CATEGORY_ORDER)
    covered = sorted(seen)
    missing = [category for category in required if category not in seen]
    return {
        "required": required,
        "covered": covered,
        "missing": missing,
    }


def _tool_first_category_block(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    baseline_flags = [bool(row.get("baseline_pass", False)) for row in rows]
    tool_flags = [bool(row.get("tool_first_pass", False)) for row in rows]
    num_cases = int(len(rows))
    passed = int(sum(1 for flag in tool_flags if flag))
    baseline_pass_rate = _pass_rate(baseline_flags)
    tool_pass_rate = _pass_rate(tool_flags)
    return {
        "num_cases": num_cases,
        "scored_cases": num_cases,
        "passed": passed,
        "baseline_pass_rate": baseline_pass_rate,
        "tool_first_pass_rate": tool_pass_rate,
        "pass_rate_delta": float(tool_pass_rate - baseline_pass_rate),
        "cases": [dict(row) for row in rows],
    }


def _tool_first_compat_payload(*, baseline_run: Mapping[str, Any], tool_run: Mapping[str, Any]) -> dict[str, Any]:
    baseline_cases = _index_cases(baseline_run)
    tool_cases = _index_cases(tool_run)
    case_ids = sorted(set(baseline_cases.keys()) | set(tool_cases.keys()))

    compat_rows: list[dict[str, Any]] = []
    for case_id in case_ids:
        baseline_row = baseline_cases.get(case_id, {})
        tool_row = tool_cases.get(case_id, {})
        compat_rows.append(
            {
                "id": case_id,
                "category": str(tool_row.get("category", "") or baseline_row.get("category", "") or "uncategorized"),
                "baseline_pass": bool(baseline_row.get("pass", False)),
                "tool_first_pass": bool(tool_row.get("pass", False)),
            }
        )

    math_rows = [row for row in compat_rows if row.get("category") == "math"]
    code_rows = [row for row in compat_rows if row.get("category") == "code"]
    overall_rows = list(compat_rows)
    math_block = _tool_first_category_block(math_rows)
    code_block = _tool_first_category_block(code_rows)
    overall_block = _tool_first_category_block(overall_rows)
    counts = {
        "num_cases": int(overall_block["num_cases"]),
        "scored_cases": int(overall_block["scored_cases"]),
        "passed": int(overall_block["passed"]),
    }

    return {
        "suite": "pr1_tool_first",
        "schema_version": "1.1",
        "counts": counts,
        "num_cases": int(counts["num_cases"]),
        "scored_cases": int(counts["scored_cases"]),
        "passed": int(counts["passed"]),
        "pass_rate": float(overall_block["tool_first_pass_rate"]),
        "summary": {
            "counts": counts,
            "metrics": {
                "baseline_pass_rate": float(overall_block["baseline_pass_rate"]),
                "tool_first_pass_rate": float(overall_block["tool_first_pass_rate"]),
                "pass_rate_delta": float(overall_block["pass_rate_delta"]),
            },
            "categories": {
                "math": {
                    "num_cases": int(math_block["num_cases"]),
                    "scored_cases": int(math_block["scored_cases"]),
                    "passed": int(math_block["passed"]),
                    "baseline_pass_rate": float(math_block["baseline_pass_rate"]),
                    "tool_first_pass_rate": float(math_block["tool_first_pass_rate"]),
                    "pass_rate_delta": float(math_block["pass_rate_delta"]),
                },
                "code": {
                    "num_cases": int(code_block["num_cases"]),
                    "scored_cases": int(code_block["scored_cases"]),
                    "passed": int(code_block["passed"]),
                    "baseline_pass_rate": float(code_block["baseline_pass_rate"]),
                    "tool_first_pass_rate": float(code_block["tool_first_pass_rate"]),
                    "pass_rate_delta": float(code_block["pass_rate_delta"]),
                },
            },
        },
        "math": math_block,
        "code": code_block,
        "overall": overall_block,
    }


def main() -> int:
    seed = int(os.getenv("MOAA_PR5_EVAL_SEED") or "37")
    pass_threshold = float(os.getenv("MOAA_PR5_PASS_THRESHOLD") or str(PASS_THRESHOLD))

    runs: list[dict[str, Any]] = []
    run_index: dict[str, dict[str, Any]] = {}

    for config in CORE_CONFIGS:
        run = _evaluate_core_config(config, seed=seed, pass_threshold=pass_threshold)
        runs.append(run)
        run_index[config.config_id] = run

    tool_first_off_run, tool_first_on_run = _evaluate_tool_first_runs(pass_threshold=pass_threshold)
    runs.append(tool_first_off_run)
    runs.append(tool_first_on_run)
    run_index["tool_first_off"] = tool_first_off_run
    run_index["tool_first_on"] = tool_first_on_run

    baseline_single = run_index["baseline_single"]
    swarm = run_index["swarm"]
    dual_gated = run_index["dual_gated"]
    memory_off = run_index["memory_off"]
    memory_on = run_index["memory_on"]
    sfc_off = run_index["sfc_off"]
    sfc_on = run_index["sfc_on"]

    baseline_single_summary = _delta_block(baseline_run=baseline_single, target_run=baseline_single)
    baseline_single_summary["config"] = "baseline_single"
    summary = {
        "counts": _matrix_counts(runs),
        "baseline_single": baseline_single_summary,
        "swarm": _delta_block(baseline_run=baseline_single, target_run=swarm),
        "dual_gated": _delta_block(baseline_run=baseline_single, target_run=dual_gated),
        "tool_first": _delta_block(baseline_run=tool_first_off_run, target_run=tool_first_on_run),
        "memory": _delta_block(baseline_run=memory_off, target_run=memory_on),
        "sfc": _delta_block(baseline_run=sfc_off, target_run=sfc_on),
    }

    per_case_diffs = {
        "swarm_vs_baseline_single": _build_case_diffs(baseline_run=baseline_single, target_run=swarm),
        "dual_gated_vs_baseline_single": _build_case_diffs(baseline_run=baseline_single, target_run=dual_gated),
        "tool_first_on_vs_off": _build_case_diffs(baseline_run=tool_first_off_run, target_run=tool_first_on_run),
        "memory_on_vs_off": _build_case_diffs(baseline_run=memory_off, target_run=memory_on),
        "sfc_on_vs_off": _build_case_diffs(baseline_run=sfc_off, target_run=sfc_on),
    }

    matrix_counts = dict(summary["counts"])
    payload = {
        "suite": "pr5_eval_matrix",
        "schema_version": "1.1",
        "seed": seed,
        "pass_threshold": pass_threshold,
        "counts": matrix_counts,
        "num_cases": int(matrix_counts["num_cases"]),
        "scored_cases": int(matrix_counts["scored_cases"]),
        "passed": int(matrix_counts["passed"]),
        "pass_rate": float(matrix_counts["passed"] / max(1, matrix_counts["scored_cases"])),
        "categories": _category_coverage(runs),
        "matrix": {
            "config_ids": [r["config_id"] for r in runs],
            "runs": runs,
        },
        "summary": summary,
        "per_case_diffs": per_case_diffs,
    }

    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    out_path = reports / "eval_matrix.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    compat_tool_path = reports / "eval_tool_first.json"
    compat_payload = _tool_first_compat_payload(
        baseline_run=tool_first_off_run,
        tool_run=tool_first_on_run,
    )
    compat_tool_path.write_text(json.dumps(compat_payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"Wrote {compat_tool_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
