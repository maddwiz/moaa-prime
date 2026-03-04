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


def _binary_calibration_examples():
    examples = []
    for run_id in ["g1", "g2", "g3", "g4"]:
        examples.append(
            RouterTrainingExample(
                run_id=run_id,
                prompt=f"prompt-{run_id}",
                agent_name="neg",
                budget_mode="balanced",
                features={"similarity": 0.0},
                label=0.0,
            )
        )
        examples.append(
            RouterTrainingExample(
                run_id=run_id,
                prompt=f"prompt-{run_id}",
                agent_name="pos",
                budget_mode="balanced",
                features={"similarity": 1.0},
                label=1.0,
            )
        )
    return examples


def _imbalanced_constant_feature_examples():
    examples = []
    for run_idx in range(12):
        run_id = f"imb-{run_idx:02d}"
        for neg_idx in range(19):
            examples.append(
                RouterTrainingExample(
                    run_id=run_id,
                    prompt=f"prompt-{run_id}",
                    agent_name=f"neg-{neg_idx:02d}",
                    budget_mode="balanced",
                    features={"similarity": 0.0},
                    label=0.0,
                )
            )
        examples.append(
            RouterTrainingExample(
                run_id=run_id,
                prompt=f"prompt-{run_id}",
                agent_name="pos-00",
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


def test_records_to_examples_includes_budget_mode_feature_value():
    examples = records_to_examples(_records(), seed=13)

    by_run = {}
    for ex in examples:
        by_run.setdefault(ex.run_id, []).append(float(ex.features["budget_mode_value"]))

    assert sorted(set(by_run["r1"])) == [0.5]
    assert sorted(set(by_run["r2"])) == [0.0]


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
        weights={"similarity": 2.0},
        bias=-1.0,
        calibration_scale=1.0,
        calibration_bias=0.0,
        seed=0,
    )

    monkeypatch.setattr(
        "moaa_prime.router.training.fit_router_v3_calibration",
        lambda *_args, **_kwargs: (2.0, 0.0),
    )
    scale, bias = _fit_router_v3_calibration_with_gate(model, _binary_calibration_examples(), seed=3)
    assert scale == 2.0
    assert bias == 0.0


def test_router_training_calibration_gate_falls_back_when_validation_nll_worsens(monkeypatch):
    model = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 2.0},
        bias=-1.0,
        calibration_scale=1.0,
        calibration_bias=0.0,
        seed=0,
    )

    monkeypatch.setattr(
        "moaa_prime.router.training.fit_router_v3_calibration",
        lambda *_args, **_kwargs: (0.5, 0.0),
    )
    scale, bias = _fit_router_v3_calibration_with_gate(model, _binary_calibration_examples(), seed=3)
    assert scale == 1.0
    assert bias == 0.0


def test_router_training_calibration_gate_skips_single_class_splits(monkeypatch):
    model = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 0.0},
        bias=0.0,
        calibration_scale=1.0,
        calibration_bias=0.0,
        seed=0,
    )
    called = {"count": 0}

    def _fake_fit(*_args, **_kwargs):
        called["count"] += 1
        return 1.5, 0.5

    monkeypatch.setattr("moaa_prime.router.training.fit_router_v3_calibration", _fake_fit)
    scale, bias = _fit_router_v3_calibration_with_gate(model, _positive_calibration_examples(), seed=3)
    assert called["count"] == 0
    assert scale == 1.0
    assert bias == 0.0


def test_router_training_calibration_gate_preserves_imbalanced_prevalence():
    examples = _imbalanced_constant_feature_examples()
    empirical_prevalence = sum(float(ex.label) for ex in examples) / float(len(examples))
    base_logit = math.log(empirical_prevalence / (1.0 - empirical_prevalence))
    model = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 0.0},
        bias=base_logit,
        calibration_scale=1.0,
        calibration_bias=0.0,
        seed=0,
    )

    scale_a, bias_a = _fit_router_v3_calibration_with_gate(model, examples, seed=17)
    scale_b, bias_b = _fit_router_v3_calibration_with_gate(model, examples, seed=17)

    assert scale_a == scale_b
    assert bias_a == bias_b

    calibrated_model = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 0.0},
        bias=base_logit,
        calibration_scale=scale_a,
        calibration_bias=bias_a,
        seed=0,
    )
    calibrated_prevalence = sum(
        calibrated_model.predict_expected_success(ex.features) for ex in examples
    ) / float(len(examples))
    assert abs(calibrated_prevalence - empirical_prevalence) < 1.0e-3


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
