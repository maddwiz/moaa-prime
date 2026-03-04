import math

from moaa_prime.contracts import Contract
from moaa_prime.router.router_v3 import RouterV3, RouterV3Model, load_router_v3_model, save_router_v3_model


class DummyAgent:
    def __init__(self, contract: Contract) -> None:
        self.contract = contract


def test_router_v3_prediction_is_stable_and_ranked():
    agents = [
        DummyAgent(
            Contract(
                name="math-agent",
                domains=["math"],
                competence=0.82,
                reliability=0.84,
                cost_prior=0.23,
                description="mathematical reasoning",
                tags=["equation", "algebra"],
            )
        ),
        DummyAgent(
            Contract(
                name="code-agent",
                domains=["code"],
                competence=0.79,
                reliability=0.82,
                cost_prior=0.30,
                description="python debugging and implementation",
                tags=["python", "debug"],
            )
        ),
    ]

    r1 = RouterV3(agents, seed=9, model_path="/tmp/nonexistent-router-v3.pt")
    r2 = RouterV3(agents, seed=9, model_path="/tmp/nonexistent-router-v3.pt")

    kwargs = {
        "task_metadata": {"task_id": "v3-stable", "required_domains": ["code"]},
        "memory_hints": {"code-agent": 0.8, "math-agent": 0.3},
        "history_stats": {
            "math-agent": {"success_rate": 0.65, "avg_oracle_score": 0.62, "avg_latency_ms": 180.0, "avg_cost_tokens": 90.0},
            "code-agent": {"success_rate": 0.88, "avg_oracle_score": 0.86, "avg_latency_ms": 170.0, "avg_cost_tokens": 88.0},
        },
        "budget": {"mode": "balanced", "max_latency_ms": 1000.0, "max_cost_tokens": 256.0},
    }

    agents_1, decisions_1 = r1.route_top_k("My python function throws a traceback", k=2, **kwargs)
    agents_2, decisions_2 = r2.route_top_k("My python function throws a traceback", k=2, **kwargs)

    assert [a.contract.name for a in agents_1] == [a.contract.name for a in agents_2]
    assert [d.agent_name for d in decisions_1] == [d.agent_name for d in decisions_2]
    assert decisions_1[0].agent_name == "code-agent"
    assert 0.0 <= decisions_1[0].expected_utility <= 1.0


def test_router_v3_model_post_logit_calibration_is_applied():
    features = {"similarity": 0.9}
    raw = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 2.0},
        bias=-1.0,
        calibration_scale=1.0,
        calibration_bias=0.0,
        seed=3,
    )
    calibrated = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 2.0},
        bias=-1.0,
        calibration_scale=0.6,
        calibration_bias=0.25,
        seed=3,
    )

    raw_logit = raw.predict_logit(features)
    expected = 1.0 / (1.0 + math.exp(-((0.6 * raw_logit) + 0.25)))
    assert abs(calibrated.predict_expected_success(features) - expected) < 1.0e-12
    assert raw.predict_expected_success(features) != calibrated.predict_expected_success(features)


def test_router_v3_model_calibration_persists_roundtrip(tmp_path):
    path = tmp_path / "router_v3.pt"
    model = RouterV3Model(
        feature_names=["similarity"],
        weights={"similarity": 1.75},
        bias=-0.4,
        calibration_scale=1.3,
        calibration_bias=-0.2,
        seed=8,
    )
    save_router_v3_model(path, model)

    loaded = load_router_v3_model(path, seed=999)
    assert loaded.calibration_scale == model.calibration_scale
    assert loaded.calibration_bias == model.calibration_bias
    assert loaded.predict_expected_success({"similarity": 0.5}) == model.predict_expected_success({"similarity": 0.5})


def test_router_v3_model_legacy_payload_defaults_identity_calibration():
    model = RouterV3Model.from_dict(
        {
            "version": "router_v3",
            "seed": 1,
            "bias": -0.2,
            "feature_names": ["similarity"],
            "weights": {"similarity": 0.9},
        }
    )
    assert model.calibration_scale == 1.0
    assert model.calibration_bias == 0.0
