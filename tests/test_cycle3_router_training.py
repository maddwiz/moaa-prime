from moaa_prime.router.training import records_to_examples, train_router_v3_model


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


def test_router_training_is_deterministic_for_seed():
    examples = records_to_examples(_records(), seed=13)

    model_a = train_router_v3_model(examples, seed=13, epochs=120)
    model_b = train_router_v3_model(examples, seed=13, epochs=120)

    assert model_a.bias == model_b.bias
    assert model_a.weights == model_b.weights
