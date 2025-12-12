from moaa_prime.core.app import MoAAPrime


def test_run_once_includes_oracle():
    app = MoAAPrime()
    out = app.run_once("Solve 2x + 3 = 7")
    assert "oracle" in out
    assert 0.0 <= out["oracle"]["score"] <= 1.0
