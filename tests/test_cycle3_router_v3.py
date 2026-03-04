from moaa_prime.contracts import Contract
from moaa_prime.router.router_v3 import RouterV3


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
