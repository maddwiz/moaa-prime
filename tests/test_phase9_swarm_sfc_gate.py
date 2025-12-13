from moaa_prime.sfc import StabilityFieldController
from moaa_prime.swarm import StableSwarmRunner, SwarmManager

try:
    from moaa_prime.oracle.verifier import OracleVerifier
except Exception:  # pragma: no cover
    OracleVerifier = None


class DummyAgent:
    def __init__(self, name: str) -> None:
        self.name = name

    def handle(self, prompt: str):
        class R:
            agent_name = "dummy"
            text = f"{prompt} -> {self.name}"
            meta = {}
        return R()


def test_phase9_stable_runner_stops_when_unstable():
    agents = [DummyAgent("A"), DummyAgent("B")]

    oracle = OracleVerifier() if OracleVerifier else None
    swarm = SwarmManager(agents, oracle)  # direct list path works in your Phase 8+ SwarmManager
    sfc = StabilityFieldController(decay=0.2, reward=0.0)  # make it drop fast

    stable = StableSwarmRunner(swarm=swarm, oracle=oracle, sfc=sfc, min_stability=0.3)
    result = stable.run("test", rounds=10)

    # should stop early because we made decay aggressive
    assert result.stopped_early is True
    assert result.sfc_value < 0.3
