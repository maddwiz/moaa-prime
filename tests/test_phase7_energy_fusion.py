from moaa_prime.sgm import SharedGeometricManifold
from moaa_prime.fusion import EnergyFusion


def test_energy_fusion_picks_best_oracle():
    sgm = SharedGeometricManifold(dim=32)
    fusion = EnergyFusion(sgm)

    def oracle(prompt: str, answer: str) -> float:
        # pretend candidate "B" is best
        return {"A": 0.2, "B": 0.9, "C": 0.4}.get(answer, 0.0)

    pick = fusion.pick("p", ["A", "B", "C"], oracle_score=oracle)
    assert pick.text == "B"
