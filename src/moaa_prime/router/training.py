from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
from typing import Any, Dict, List, Mapping, Sequence

from moaa_prime.contracts import Contract

from .router_v2 import RoutingBudget
from .router_v3 import FEATURE_NAMES, RouterV3Model, build_router_v3_features, save_router_v3_model


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sigmoid(x: float) -> float:
    z = _clamp(float(x), -50.0, 50.0)
    return 1.0 / (1.0 + math.exp(-z))


def _label_to_binary(label: float) -> float:
    return 1.0 if float(label) >= 0.5 else 0.0


@dataclass(frozen=True)
class RouterTrainingExample:
    run_id: str
    prompt: str
    agent_name: str
    budget_mode: str
    features: Dict[str, float]
    label: float


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def load_router_training_records(
    *,
    trace_dir: str = "reports/traces",
    dataset_path: str = "datasets/router_training.jsonl",
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    ds_path = Path(dataset_path)
    if ds_path.exists():
        for line in ds_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)

    tr_path = Path(trace_dir)
    if tr_path.exists():
        for path in sorted(tr_path.glob("run_*.json")):
            payload = _load_json(path)
            if isinstance(payload, dict):
                out.append(payload)

    dedup: Dict[str, Dict[str, Any]] = {}
    for row in out:
        run_id = str(row.get("run_id", ""))
        if run_id:
            dedup[run_id] = row
        else:
            dedup[f"anon_{len(dedup):06d}"] = row

    return [dedup[k] for k in sorted(dedup.keys())]


def _contract_from_payload(agent_name: str, payload: Mapping[str, Any]) -> Contract:
    emb = payload.get("embedding", [])
    if not isinstance(emb, list):
        emb = []

    return Contract(
        name=agent_name,
        domains=[str(x) for x in payload.get("domains", []) or []],
        tools=[str(x) for x in payload.get("tools", []) or []],
        competence=float(payload.get("competence", 0.6)),
        reliability=float(payload.get("reliability", 0.6)),
        cost_prior=float(payload.get("cost_prior", 0.3)),
        tags=[str(x) for x in payload.get("tags", []) or []],
        description=str(payload.get("description", "") or ""),
        embedding=[float(x) for x in emb],
    )


def records_to_examples(
    records: Sequence[Mapping[str, Any]],
    *,
    embedding_dim: int = 24,
    seed: int = 0,
) -> List[RouterTrainingExample]:
    examples: List[RouterTrainingExample] = []

    for row in records:
        run_id = str(row.get("run_id", ""))
        prompt = str(row.get("task", ""))
        winner = str(row.get("winner", ""))
        budget_mode = str(row.get("budget_mode", "balanced")) or "balanced"

        contract_map = row.get("contracts", {}) or {}
        if not isinstance(contract_map, Mapping):
            contract_map = {}

        metrics = row.get("agent_metrics", {}) or {}
        if not isinstance(metrics, Mapping):
            metrics = {}

        # Keep deterministic ordering.
        agent_names = sorted(set(list(contract_map.keys()) + list(metrics.keys())))
        for agent_name in agent_names:
            c_payload = contract_map.get(agent_name, {}) or {}
            if not isinstance(c_payload, Mapping):
                c_payload = {}
            contract = _contract_from_payload(str(agent_name), c_payload)

            m_payload = metrics.get(agent_name, {}) or {}
            if not isinstance(m_payload, Mapping):
                m_payload = {}

            history_row = {
                "success_rate": _clamp(float(m_payload.get("oracle_score", contract.reliability)), 0.0, 1.0),
                "avg_oracle_score": _clamp(float(m_payload.get("oracle_score", contract.reliability)), 0.0, 1.0),
                "avg_latency_ms": max(1.0, float(m_payload.get("latency", 180.0))),
                "avg_cost_tokens": max(1.0, float(m_payload.get("cost", 96.0))),
            }

            features = build_router_v3_features(
                prompt,
                contract,
                history_row=history_row,
                memory_alignment=float(m_payload.get("confidence", 0.5)),
                budget=RoutingBudget(),
                embedding_dim=embedding_dim,
                seed=seed,
            )

            label = 1.0 if str(agent_name) == winner else 0.0
            examples.append(
                RouterTrainingExample(
                    run_id=run_id,
                    prompt=prompt,
                    agent_name=str(agent_name),
                    budget_mode=budget_mode,
                    features=features,
                    label=label,
                )
            )

    # Stable order by run then agent.
    examples.sort(key=lambda e: (e.run_id, e.agent_name))
    return examples


def train_router_v3_model(
    examples: Sequence[RouterTrainingExample],
    *,
    seed: int = 0,
    epochs: int = 250,
    learning_rate: float = 0.18,
    l2: float = 1.0e-4,
    fit_calibration: bool = True,
) -> RouterV3Model:
    rng = random.Random(int(seed))

    base = RouterV3Model(seed=int(seed))
    weights = {k: float(base.weights.get(k, 0.0)) for k in FEATURE_NAMES}
    bias = float(base.bias)

    # Tiny deterministic jitter so repeated training with different seeds can diverge.
    for k in FEATURE_NAMES:
        weights[k] += rng.uniform(-0.001, 0.001)

    if not examples:
        return RouterV3Model(
            feature_names=list(FEATURE_NAMES),
            weights=weights,
            bias=bias,
            calibration_scale=float(base.calibration_scale),
            calibration_bias=float(base.calibration_bias),
            seed=int(seed),
        )

    sample_weights = _build_class_balanced_sample_weights(examples)

    for _ in range(max(1, int(epochs))):
        for idx, ex in enumerate(examples):
            z = bias
            for k in FEATURE_NAMES:
                z += weights[k] * float(ex.features.get(k, 0.0))
            pred = _sigmoid(z)
            err = (pred - _label_to_binary(ex.label)) * sample_weights[idx]

            for k in FEATURE_NAMES:
                x = float(ex.features.get(k, 0.0))
                grad = (err * x) + (l2 * weights[k])
                weights[k] -= float(learning_rate) * grad
            bias -= float(learning_rate) * err

    model = RouterV3Model(
        feature_names=list(FEATURE_NAMES),
        weights=weights,
        bias=bias,
        seed=int(seed),
    )

    calibration_scale = float(base.calibration_scale)
    calibration_bias = float(base.calibration_bias)
    if fit_calibration:
        calibration_scale, calibration_bias = fit_router_v3_calibration(
            model,
            examples,
            sample_weights=sample_weights,
        )

    return RouterV3Model(
        feature_names=list(FEATURE_NAMES),
        weights=weights,
        bias=bias,
        calibration_scale=calibration_scale,
        calibration_bias=calibration_bias,
        seed=int(seed),
    )


def _build_class_balanced_sample_weights(examples: Sequence[RouterTrainingExample]) -> List[float]:
    total = len(examples)
    if total == 0:
        return []

    num_pos = sum(1 for ex in examples if _label_to_binary(ex.label) >= 0.5)
    num_neg = total - num_pos
    if num_pos == 0 or num_neg == 0:
        return [1.0 for _ in examples]

    pos_weight = float(total) / (2.0 * float(num_pos))
    neg_weight = float(total) / (2.0 * float(num_neg))
    return [pos_weight if _label_to_binary(ex.label) >= 0.5 else neg_weight for ex in examples]


def fit_router_v3_calibration(
    model: RouterV3Model,
    examples: Sequence[RouterTrainingExample],
    *,
    sample_weights: Sequence[float] | None = None,
    epochs: int = 300,
    learning_rate: float = 0.08,
    l2: float = 1.0e-4,
) -> tuple[float, float]:
    if not examples:
        return 1.0, 0.0

    if sample_weights is None or len(sample_weights) != len(examples):
        sample_weights = [1.0 for _ in examples]

    scale = 1.0
    offset = 0.0
    num_examples = float(len(examples))
    for _ in range(max(1, int(epochs))):
        grad_scale = 0.0
        grad_offset = 0.0

        for idx, ex in enumerate(examples):
            raw_logit = float(model.predict_logit(ex.features))
            calibrated_logit = (scale * raw_logit) + offset
            pred = _sigmoid(calibrated_logit)
            err = (pred - _label_to_binary(ex.label)) * float(sample_weights[idx])
            grad_scale += err * raw_logit
            grad_offset += err

        # Light regularization around the identity transform (scale=1, offset=0)
        # keeps calibration stable for small/clean datasets.
        grad_scale = (grad_scale / num_examples) + (l2 * (scale - 1.0))
        grad_offset = (grad_offset / num_examples) + (l2 * offset)
        scale = _clamp(scale - (float(learning_rate) * grad_scale), 0.05, 20.0)
        offset = _clamp(offset - (float(learning_rate) * grad_offset), -20.0, 20.0)

    return float(scale), float(offset)


def evaluate_training_accuracy(model: RouterV3Model, examples: Sequence[RouterTrainingExample]) -> float:
    if not examples:
        return 0.0

    correct = 0
    for ex in examples:
        p = model.predict_expected_success(ex.features)
        y = _label_to_binary(ex.label)
        yhat = 1.0 if p >= 0.5 else 0.0
        if yhat == y:
            correct += 1
    return float(correct / float(len(examples)))


def evaluate_brier_score(model: RouterV3Model, examples: Sequence[RouterTrainingExample]) -> float:
    if not examples:
        return 0.0

    err = 0.0
    for ex in examples:
        p = _clamp(float(model.predict_expected_success(ex.features)), 0.0, 1.0)
        y = _label_to_binary(ex.label)
        delta = p - y
        err += delta * delta
    return float(err / float(len(examples)))


def evaluate_expected_calibration_error(
    model: RouterV3Model,
    examples: Sequence[RouterTrainingExample],
    *,
    num_bins: int = 10,
) -> float:
    if not examples:
        return 0.0

    bins = max(1, int(num_bins))
    stats: List[Dict[str, float]] = [{"count": 0.0, "sum_conf": 0.0, "sum_acc": 0.0} for _ in range(bins)]
    for ex in examples:
        conf = _clamp(float(model.predict_expected_success(ex.features)), 0.0, 1.0)
        acc = _label_to_binary(ex.label)
        idx = min(bins - 1, int(conf * bins))
        row = stats[idx]
        row["count"] += 1.0
        row["sum_conf"] += conf
        row["sum_acc"] += acc

    total = float(len(examples))
    ece = 0.0
    for row in stats:
        count = row["count"]
        if count <= 0.0:
            continue
        avg_conf = row["sum_conf"] / count
        avg_acc = row["sum_acc"] / count
        ece += abs(avg_acc - avg_conf) * (count / total)
    return float(ece)


def train_and_save_router_v3(
    *,
    seed: int = 0,
    trace_dir: str = "reports/traces",
    dataset_path: str = "datasets/router_training.jsonl",
    model_path: str = "models/router_v3.pt",
) -> Dict[str, Any]:
    records = load_router_training_records(trace_dir=trace_dir, dataset_path=dataset_path)
    examples = records_to_examples(records, seed=seed)
    model = train_router_v3_model(examples, seed=seed)
    save_router_v3_model(model_path, model)

    train_accuracy = evaluate_training_accuracy(model, examples)
    train_brier = evaluate_brier_score(model, examples)
    train_ece = evaluate_expected_calibration_error(model, examples)
    return {
        "seed": int(seed),
        "num_records": len(records),
        "num_examples": len(examples),
        "model_path": str(model_path),
        "training_accuracy": train_accuracy,
        "training_brier_score": train_brier,
        "training_ece": train_ece,
        "calibration_scale": float(model.calibration_scale),
        "calibration_bias": float(model.calibration_bias),
        "feature_names": list(FEATURE_NAMES),
        "weights": {k: float(model.weights.get(k, 0.0)) for k in FEATURE_NAMES},
        "bias": float(model.bias),
        "metrics": {
            "accuracy": train_accuracy,
            "brier_score": train_brier,
            "ece": train_ece,
        },
        "calibration": {
            "scale": float(model.calibration_scale),
            "bias": float(model.calibration_bias),
        },
    }
