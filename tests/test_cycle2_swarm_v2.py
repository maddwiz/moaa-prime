from moaa_prime.contracts import Contract
from moaa_prime.oracle.verifier import OracleV2
from moaa_prime.router.router_v2 import RouterV2
from moaa_prime.swarm.manager import SwarmManager


class FixedAgent:
    def __init__(self, contract: Contract, response_text: str) -> None:
        self.contract = contract
        self._response_text = response_text

    def handle(self, prompt: str, task_id: str = "default"):
        class R:
            agent_name = self.contract.name
            text = self._response_text
            meta = {"task_id": task_id}

        return R()



def test_swarm_v2_selects_best_candidate_and_emits_trace():
    agents = [
        FixedAgent(
            Contract(name="math-agent", domains=["math"], competence=0.86, reliability=0.86, cost_prior=0.25),
            "x = 2",
        ),
        FixedAgent(
            Contract(name="code-agent", domains=["code"], competence=0.78, reliability=0.80, cost_prior=0.32),
            "not sure",
        ),
    ]

    router = RouterV2(agents, seed=5)
    oracle = OracleV2(seed=5)
    swarm = SwarmManager(router, oracle, mode="v2", seed=5)

    out = swarm.run(
        "Solve: 2x + 3 = 7. Return only x.",
        mode="v2",
        rounds=2,
        top_k=2,
        cross_check=True,
        task_metadata={"task_id": "swarm-v2"},
    )

    assert out["best"]["agent"] == "math-agent"
    assert len(out["candidates"]) == 4
    assert 0.0 <= float(out["confidence"]) <= 1.0
    assert set(out["trace"].keys()) == {"router", "swarm", "oracle", "final"}
    assert out["trace"]["swarm"]["cross_check"]["enabled"] is True
