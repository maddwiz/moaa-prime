from moaa_prime.cli.phase9_stable_cmd import run_stable_swarm


def test_phase9_cli_stable_cmd_runs():
    out = run_stable_swarm("hello", rounds=3, min_stability=0.3)
    assert "best" in out
    assert "candidates" in out
    assert "sfc_value" in out
