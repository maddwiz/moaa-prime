from moaa_prime.swarm.dual_brain_runner import DualBrainRunner


def test_dual_brain_happy_path():
    runner = DualBrainRunner()
    out = runner.run("build a plan")

    assert "architect" in out
    assert "oracle" in out
    assert out["oracle"]["approved"] is True


def test_dual_brain_veto():
    runner = DualBrainRunner()
    out = runner.run("dangerous plan")

    assert out["oracle"]["approved"] is False
