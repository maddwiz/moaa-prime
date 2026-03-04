from moaa_prime.contracts import Contract
from moaa_prime.router.router_v2 import RouterV2


class DummyAgent:
    def __init__(self, contract: Contract) -> None:
        self.contract = contract



def test_router_v2_ranks_code_for_code_prompt_deterministically():
    agents = [
        DummyAgent(Contract(name="math-agent", domains=["math"], competence=0.80, reliability=0.82, cost_prior=0.22)),
        DummyAgent(Contract(name="code-agent", domains=["code"], competence=0.78, reliability=0.85, cost_prior=0.28)),
    ]

    router_a = RouterV2(agents, seed=42)
    router_b = RouterV2(agents, seed=42)

    kwargs = {
        "task_metadata": {"task_id": "r1", "required_domains": ["code"]},
        "memory_hints": {"code-agent": 0.9, "math-agent": 0.2},
        "budget": {"max_latency_ms": 1000.0, "max_cost_tokens": 256.0},
        "history_stats": {
            "math-agent": {"success_rate": 0.62, "avg_latency_ms": 220.0, "avg_cost_tokens": 120.0},
            "code-agent": {"success_rate": 0.84, "avg_latency_ms": 210.0, "avg_cost_tokens": 118.0},
        },
    }

    agents_a, decisions_a = router_a.route_top_k("My python function throws an error", k=2, **kwargs)
    agents_b, decisions_b = router_b.route_top_k("My python function throws an error", k=2, **kwargs)

    assert [a.contract.name for a in agents_a] == [a.contract.name for a in agents_b]
    assert [d.agent_name for d in decisions_a] == [d.agent_name for d in decisions_b]
    assert decisions_a[0].agent_name == "code-agent"
    assert 0.0 <= decisions_a[0].expected_utility <= 1.0
    assert 0.0 <= decisions_a[0].exploration_probability <= 1.0



def test_router_v2_route_selection_is_seeded():
    agents = [
        DummyAgent(Contract(name="math-agent", domains=["math"], competence=0.81, reliability=0.82, cost_prior=0.20)),
        DummyAgent(Contract(name="code-agent", domains=["code"], competence=0.80, reliability=0.81, cost_prior=0.20)),
    ]

    router_x = RouterV2(agents, seed=999)
    router_y = RouterV2(agents, seed=999)

    agent_x, decision_x = router_x.route("Solve this equation: 2x + 3 = 7", task_metadata={"task_id": "seeded"})
    agent_y, decision_y = router_y.route("Solve this equation: 2x + 3 = 7", task_metadata={"task_id": "seeded"})

    assert agent_x.contract.name == agent_y.contract.name
    assert decision_x.selected_by_exploration == decision_y.selected_by_exploration
    assert decision_x.exploration_probability == decision_y.exploration_probability
