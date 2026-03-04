from __future__ import annotations

from dataclasses import dataclass
import hashlib
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


def _stable_hash_int(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


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
    early_stopping: bool = True,
    early_stopping_validation_fraction: float = 0.25,
    early_stopping_patience: int = 16,
    early_stopping_min_epochs: int = 20,
    early_stopping_min_delta: float = 1.0e-8,
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

    training_examples = list(examples)
    validation_examples: List[RouterTrainingExample] = []
    if early_stopping:
        training_examples, validation_examples = _split_training_examples_by_run_group(
            examples,
            seed=seed,
            validation_fraction=early_stopping_validation_fraction,
        )
        if not training_examples:
            training_examples = list(examples)
            validation_examples = []

    sample_weights = _build_class_balanced_sample_weights(training_examples)
    validation_weights = _build_class_balanced_sample_weights(validation_examples)

    num_epochs = max(1, int(epochs))
    patience = max(1, int(early_stopping_patience))
    min_epochs = max(1, int(early_stopping_min_epochs))
    min_delta = max(0.0, float(early_stopping_min_delta))
    use_early_stopping = bool(early_stopping and validation_examples)

    best_weights = {k: float(weights.get(k, 0.0)) for k in FEATURE_NAMES}
    best_bias = float(bias)
    best_validation_nll = math.inf
    epochs_without_improvement = 0

    for epoch_idx in range(num_epochs):
        for idx, ex in enumerate(training_examples):
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

        if not use_early_stopping:
            continue

        candidate_model = RouterV3Model(
            feature_names=list(FEATURE_NAMES),
            weights=weights,
            bias=bias,
            seed=int(seed),
        )
        validation_nll = _evaluate_weighted_nll(
            candidate_model,
            validation_examples,
            calibration_scale=1.0,
            calibration_bias=0.0,
            sample_weights=validation_weights,
        )
        if math.isfinite(validation_nll) and (validation_nll + min_delta < best_validation_nll):
            best_validation_nll = float(validation_nll)
            best_weights = {k: float(weights.get(k, 0.0)) for k in FEATURE_NAMES}
            best_bias = float(bias)
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if (epoch_idx + 1) >= min_epochs and epochs_without_improvement >= patience:
                break

    if use_early_stopping and math.isfinite(best_validation_nll):
        weights = {k: float(best_weights.get(k, 0.0)) for k in FEATURE_NAMES}
        bias = float(best_bias)

    model = RouterV3Model(
        feature_names=list(FEATURE_NAMES),
        weights=weights,
        bias=bias,
        seed=int(seed),
    )

    calibration_scale = float(base.calibration_scale)
    calibration_bias = float(base.calibration_bias)
    if fit_calibration:
        calibration_scale, calibration_bias = _fit_router_v3_calibration_with_gate(model, examples, seed=seed)

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


def _split_examples_by_run_group(
    examples: Sequence[RouterTrainingExample],
    *,
    seed: int,
    validation_fraction: float,
    max_validation_fraction: float = 0.5,
) -> tuple[List[RouterTrainingExample], List[RouterTrainingExample]]:
    if not examples:
        return [], []

    grouped: Dict[str, List[RouterTrainingExample]] = {}
    for idx, ex in enumerate(examples):
        run_key = str(ex.run_id).strip() or f"anon_{idx:06d}"
        grouped.setdefault(run_key, []).append(ex)

    run_ids = sorted(grouped.keys())
    if len(run_ids) < 2:
        return list(examples), []

    raw_fraction = _clamp(float(validation_fraction), 0.0, float(max_validation_fraction))
    num_validation_runs = int(round(float(len(run_ids)) * raw_fraction))
    num_validation_runs = max(1, min(len(run_ids) - 1, num_validation_runs))

    ranked_runs = sorted(run_ids, key=lambda run_id: (_stable_hash_int(f"{int(seed)}|{run_id}"), run_id))
    validation_runs = set(ranked_runs[:num_validation_runs])

    train_examples: List[RouterTrainingExample] = []
    validation_examples: List[RouterTrainingExample] = []
    for idx, ex in enumerate(examples):
        run_key = str(ex.run_id).strip() or f"anon_{idx:06d}"
        if run_key in validation_runs:
            validation_examples.append(ex)
        else:
            train_examples.append(ex)
    return train_examples, validation_examples


def _split_training_examples_by_run_group(
    examples: Sequence[RouterTrainingExample],
    *,
    seed: int,
    validation_fraction: float = 0.25,
) -> tuple[List[RouterTrainingExample], List[RouterTrainingExample]]:
    return _split_examples_by_run_group(
        examples,
        seed=seed,
        validation_fraction=validation_fraction,
        max_validation_fraction=0.5,
    )


def _split_calibration_examples_by_run_group(
    examples: Sequence[RouterTrainingExample],
    *,
    seed: int,
    validation_fraction: float = 0.25,
) -> tuple[List[RouterTrainingExample], List[RouterTrainingExample]]:
    calibration_train, calibration_validation = _split_examples_by_run_group(
        examples,
        seed=seed,
        validation_fraction=validation_fraction,
        max_validation_fraction=0.5,
    )
    return calibration_train, calibration_validation


def _evaluate_weighted_nll(
    model: RouterV3Model,
    examples: Sequence[RouterTrainingExample],
    *,
    calibration_scale: float,
    calibration_bias: float,
    sample_weights: Sequence[float] | None = None,
) -> float:
    if not examples:
        return 0.0

    if sample_weights is None or len(sample_weights) != len(examples):
        sample_weights = [1.0 for _ in examples]

    weighted_loss = 0.0
    total_weight = 0.0
    for idx, ex in enumerate(examples):
        raw_logit = float(model.predict_logit(ex.features))
        calibrated_logit = (float(calibration_scale) * raw_logit) + float(calibration_bias)
        pred = _clamp(_sigmoid(calibrated_logit), 1.0e-12, 1.0 - 1.0e-12)
        label = _label_to_binary(ex.label)
        loss = -((label * math.log(pred)) + ((1.0 - label) * math.log(1.0 - pred)))
        weight = max(0.0, float(sample_weights[idx]))
        weighted_loss += weight * loss
        total_weight += weight

    if total_weight <= 0.0:
        return 0.0
    return float(weighted_loss / total_weight)


def _fit_router_v3_calibration_with_gate(
    model: RouterV3Model,
    examples: Sequence[RouterTrainingExample],
    *,
    seed: int,
) -> tuple[float, float]:
    calibration_train, calibration_validation = _split_calibration_examples_by_run_group(examples, seed=seed)
    if not calibration_train or not calibration_validation:
        return 1.0, 0.0

    calibration_train_weights = _build_class_balanced_sample_weights(calibration_train)
    fitted_scale, fitted_bias = fit_router_v3_calibration(
        model,
        calibration_train,
        sample_weights=calibration_train_weights,
    )

    calibration_validation_weights = _build_class_balanced_sample_weights(calibration_validation)
    identity_nll = _evaluate_weighted_nll(
        model,
        calibration_validation,
        calibration_scale=1.0,
        calibration_bias=0.0,
        sample_weights=calibration_validation_weights,
    )
    fitted_nll = _evaluate_weighted_nll(
        model,
        calibration_validation,
        calibration_scale=fitted_scale,
        calibration_bias=fitted_bias,
        sample_weights=calibration_validation_weights,
    )

    if fitted_nll + 1.0e-12 < identity_nll:
        return float(fitted_scale), float(fitted_bias)
    return 1.0, 0.0


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
