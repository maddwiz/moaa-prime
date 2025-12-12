from moaa_prime.core.app import MoAAPrime


def test_run_swarm_has_best_and_candidates():
    app = MoAAPrime()
    out = app.run_swarm("Solve 2x + 3 = 7")
    assert "best" in out
    assert "candidates" in out
    assert len(out["candidates"]) >= 2
    assert 0.0 <= out["best"]["oracle"]["score"] <= 1.0
