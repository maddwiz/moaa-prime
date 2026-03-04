import json

from moaa_prime.oracle.verifier import OracleV2



def test_oracle_v2_scores_with_weighted_components():
    oracle = OracleV2(seed=7)
    verdict = oracle.verdict("Solve: 2x + 3 = 7. Return only x.", "x = 2")

    assert 0.0 <= verdict.score <= 1.0
    assert "components" in (verdict.meta or {})
    components = (verdict.meta or {})["components"]
    assert set(components.keys()) == {
        "correctness_proxy",
        "coherence",
        "constraint_adherence",
        "safety_overreach",
        "grounding",
    }



def test_oracle_v2_consistency_check_has_low_variance():
    oracle = OracleV2(seed=11)
    check = oracle.consistency_check("Write Python code", "def add(a, b):\n    return a + b", repeats=6)

    assert check["stable"] is True
    assert float(check["variance"]) <= 1.0e-12
    assert float(check["max_delta"]) <= 1.0e-12



def test_oracle_v2_uses_external_rubric_json(tmp_path):
    rubric_path = tmp_path / "rubric.json"
    rubric_path.write_text(
        json.dumps(
            {
                "weights": {
                    "correctness_proxy": 0.0,
                    "coherence": 1.0,
                    "constraint_adherence": 0.0,
                    "safety_overreach": 0.0,
                    "grounding": 0.0,
                }
            }
        ),
        encoding="utf-8",
    )

    oracle = OracleV2(rubric_path=str(rubric_path), seed=1)
    verdict = oracle.verdict("Any prompt", "short coherent answer")

    coherence = float((verdict.meta or {})["components"]["coherence"])
    assert abs(float(verdict.score) - coherence) <= 1.0e-9
