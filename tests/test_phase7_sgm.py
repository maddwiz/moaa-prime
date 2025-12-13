from moaa_prime.sgm import SharedGeometricManifold


def test_sgm_deterministic():
    sgm = SharedGeometricManifold(dim=32)
    a = sgm.embed("hello world").vec
    b = sgm.embed("hello world").vec
    c = sgm.embed("different").vec
    assert a == b
    assert a != c
    assert len(a) == 32
