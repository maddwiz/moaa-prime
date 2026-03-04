import math

from moaa_prime.router.router_v3 import RouterV3Model
from moaa_prime.router.training import (
    RouterTrainingExample,
    _fit_router_v3_calibration_with_gate,
    _split_calibration_examples_by_run_group,
    _split_training_examples_by_run_group,
    evaluate_brier_score,
    evaluate_expected_calibration_error,
    records_to_examples,
    train_router_v3_model,
)


def _records():
    return [
        {
            "run_id": "r1",
            "task": "Solve equation quickly",
            "winner": "math-agent",
            "budget_mode": "balanced",
            "contracts": {
                "math-agent": {
                    "domains": ["math"],
                    "tools": ["sympy"],
                    "competence": 0.82,
                    "reliability": 0.85,
                    "cost_prior": 0.25,
                    "description": "math reasoning",
                    "tags": ["algebra"],
                },
                "code-agent": {
                    "domains": ["code"],
                    "tools": ["exec"],
                    "competence": 0.78,
                    "reliability": 0.80,
                    "cost_prior": 0.32,
                    "description": "code debugging",
                    "tags": ["python"],
                },
            },
            "agent_metrics": {
                "math-agent": {"oracle_score": 0.91, "latency": 110.0, "cost": 40.0, "confidence": 0.8},
                "code-agent": {"oracle_score": 0.62, "latency": 130.0, "cost": 55.0, "confidence": 0.6},
            },
        },
        {
            "run_id": "r2",
            "task": "Fix python function",
            "winner": "code-agent",
            "budget_mode": "cheap",
            "contracts": {
                "math-agent": {
                    "domains": ["math"],
                    "tools": ["sympy"],
                    "competence": 0.82,
                    "reliability": 0.85,
                    "cost_prior": 0.25,
                    "description": "math reasoning",
                    "tags": ["algebra"],
                },
                "code-agent": {
                    "domains": ["code"],
                    "tools": ["exec"],
                    "competence": 0.78,
                    "reliability": 0.80,
                    "cost_prior": 0.32,
                    "description": "code debugging",
                    "tags": ["python"],
                },
            },
            "agent_metrics": {
                "math-agent": {"oracle_score": 0.55, "latency": 115.0, "cost": 41.0, "confidence": 0.5},
                "code-agent": {"oracle_score": 0.89, "latency": 108.0, "cost": 37.0, "confidence": 0.9},
            },
        },
    ]


def _positive_calibration_examples():
    examples = []
    for run_id in ["g1", "g2", "g3", "g4"]:
        for agent_name in ["a0", "a1"]:
            examples.append(
                RouterTrainingExample(
                    run_id=run_id,
                    prompt=f"prompt-{run_id}",
                    agent_name=agent_name,
                    budget_mode="balanced",
                    features={"similarity": 0.0},
                    label=1.0,
                )
            )
    return examples


def test_router_training_is_deterministic_for_seed():
    examples = records_to_examples(_records(), seed=13)

    model_a = train_router_v3_model(
        examples,
        seed=13,
        epochs=120,
        early_stopping=True,
        early_stopping_patience=2,
        early_stopping_min_epochs=3,
        early_stopping_min_delta=1.0,
    )
    model_b = train_router_v3_model(
        examples,
        seed=13,
        epochs=120,
        early_stopping=True,
        early_stopping_patience=2,
        early_stopping_min_epochs=3,
        early_stopping_min_delta=1.0,
    )

    assert model_a.bias == model_b.bias
    assert model_a.weights == model_b.weights
    assert model_a.calibration_scale == model_b.calibration_scale
    assert model_a.calibration_bias == model_b.calibration_bias


def test_router_training_supports_deterministic_calibration_toggle():
    examples = records_to_examples(_records(), seed=21)

    model_uncalibrated = train_router_v3_model(examples, seed=21, epochs=100, fit_calibration=False)
    model_calibrated = train_router_v3_model(examples, seed=21, epochs=100, fit_calibration=True)

    assert model_uncalibrated.calibration_scale == 1.0
    assert model_uncalibrated.calibration_bias == 0.0
    assert model_calibrated.calibration_scale != 0.0
    calibrated_repeat = train_router_v3_model(
        examples,
        seed=21,
        epochs=100,
        fit_calibration=True,
    )
    assert model_calibrated.calibration_scale == calibrated_repeat.calibration_scale
    assert model_calibrated.calibration_bias == calibrated_repeat.calibration_bias


def test_router_training_calibration_split_is_run_group_deterministic():
    examples = records_to_examples(_records(), seed=5)

    train_a, val_a = _split_calibration_examples_by_run_group(examples, seed=41)
    train_b, val_b = _split_calibration_examples_by_run_group(examples, seed=41)

    assert [(ex.run_id, ex.agent_name) for ex in train_a] == [(ex.run_id, ex.agent_name) for ex in train_b]
    assert [(ex.run_id, ex.agent_name) for ex in val_a] == [(ex.run_id, ex.agent_name) for ex in val_b]

    train_runs = {ex.run_id for ex in train_a}
    val_runs = {ex.run_id for ex in val_a}
    assert train_runs.isdisjoint(val_runs)
    assert train_runs | val_runs == {ex.run_id for ex in examples}


def test_router_training_split_is_run_group_deterministic():
    examples = records_to_examples(_records(), seed=7)

    train_a, val_a = _split_training_examples_by_run_group(examples, seed=29)
    train_b, val_b = _split_training_examples_by_run_group(examples, seed=29)

    assert [(ex.run_id, ex.agent_name) for ex in train_a] == [(ex.run_id, ex.agent_name) for ex in train_b]
    assert [(ex.run_id, ex.agent_name) for ex in val_a] == [(ex.run_id, ex.agent_name) for ex in val_b]

    train_runs = {ex.run_id for ex in train_a}
    val_runs = {ex.run_id for ex in val_a}
    assert train_runs.isdisjoint(val_runs)
    assert train_runs | val_runs == {ex.run_id for ex in examples}


def test_router_training_handles_no_validation_split_available():
    examples = records_to_examples([_records()[0]], seed=11)

    model = train_router_v3_model(
        examples,
        seed=11,
        epochs=80,
        early_stopping=True,
        early_stopping_patience=2,
        early_stopping_min_epochs=3,
    )

    assert isinstance(model, RouterV3Model)
    assert math.isfinite(model.bias)
    assert set(model.weights.keys()) == set(model.feature_names)


def test_router_training_calibration_gate_accepts_when_validation_nll_improves(monkeypatch):
    model = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 0.0},
        bias=0.0,
        calibration_scale=1.0,
        calibration_bias=0.0,
        seed=0,
    )

    monkeypatch.setattr(
        "moaa_prime.router.training.fit_router_v3_calibration",
        lambda *_args, **_kwargs: (1.0, 2.0),
    )
    scale, bias = _fit_router_v3_calibration_with_gate(model, _positive_calibration_examples(), seed=3)
    assert scale == 1.0
    assert bias == 2.0


def test_router_training_calibration_gate_falls_back_when_validation_nll_worsens(monkeypatch):
    model = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 0.0},
        bias=0.0,
        calibration_scale=1.0,
        calibration_bias=0.0,
        seed=0,
    )

    monkeypatch.setattr(
        "moaa_prime.router.training.fit_router_v3_calibration",
        lambda *_args, **_kwargs: (1.0, -20.0),
    )
    scale, bias = _fit_router_v3_calibration_with_gate(model, _positive_calibration_examples(), seed=3)
    assert scale == 1.0
    assert bias == 0.0


def test_router_training_metrics_brier_and_ece():
    model = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 6.0},
        bias=-3.0,
        calibration_scale=1.0,
        calibration_bias=0.0,
        seed=0,
    )
    examples = [
        RouterTrainingExample(
            run_id="r1",
            prompt="p1",
            agent_name="a0",
            budget_mode="balanced",
            features={"similarity": 0.0},
            label=0.0,
        ),
        RouterTrainingExample(
            run_id="r1",
            prompt="p1",
            agent_name="a1",
            budget_mode="balanced",
            features={"similarity": 1.0},
            label=1.0,
        ),
    ]

    p0 = 1.0 / (1.0 + math.exp(3.0))
    p1 = 1.0 / (1.0 + math.exp(-3.0))
    expected_brier = (((p0 - 0.0) ** 2) + ((p1 - 1.0) ** 2)) / 2.0
    expected_ece = (abs(0.0 - p0) * 0.5) + (abs(1.0 - p1) * 0.5)

    assert abs(evaluate_brier_score(model, examples) - expected_brier) < 1.0e-12
    assert abs(evaluate_expected_calibration_error(model, examples, num_bins=10) - expected_ece) < 1.0e-12
