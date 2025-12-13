from moaa_prime.sfc import StabilityFieldController


def test_sfc_stability_moves():
    sfc = StabilityFieldController()

    # good reasoning
    v1 = sfc.update(oracle_score=0.9, energy=0.1, kl_like=0.1)
    assert v1 > 0.9

    # chaotic reasoning
    v2 = sfc.update(oracle_score=0.2, energy=0.9, kl_like=0.9)
    assert v2 < v1

    # collapse stops continuation
    for _ in range(20):
        sfc.update(oracle_score=0.1, energy=1.0, kl_like=1.0)

    assert not sfc.should_continue()
