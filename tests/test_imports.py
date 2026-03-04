def test_imports():
    import moaa_prime  # noqa: F401
    from moaa_prime.core.app import MoAAPrime  # noqa: F401


def test_episodic_backcompat_imports() -> None:
    from moaa_prime.memory.episodic import Episode, EpisodicLane  # noqa: F401
