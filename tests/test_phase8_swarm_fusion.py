from moaa_prime.swarm.manager import SwarmManager
from moaa_prime.fusion.mode import FusionMode
from moaa_prime.oracle.verifier import OracleVerifier
from moaa_prime.agents.base import AgentResult, BaseAgent


class DummyAgent(BaseAgent):
    def __init__(self, text: str):
        self.text = text

    def handle(self, prompt: str) -> AgentResult:
        return AgentResult(agent_name="dummy", text=self.text)


def test_swarm_energy_fusion_path():
    agents = [DummyAgent("A"), DummyAgent("B")]
    oracle = OracleVerifier()

    swarm = SwarmManager(
        agents,
        oracle,
        fusion_mode=FusionMode.ENERGY,
    )

    out = swarm.deliberate("test")
    assert out in {"A", "B"}
