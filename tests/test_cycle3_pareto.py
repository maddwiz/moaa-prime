from moaa_prime.swarm.pareto import pareto_frontier


def test_pareto_frontier_filters_dominated_points():
    points = [
        {"id": 0.0, "score": 0.91, "confidence": 0.83, "latency": 2.3, "cost": 0.02},
        {"id": 1.0, "score": 0.88, "confidence": 0.80, "latency": 1.1, "cost": 0.01},
        {"id": 2.0, "score": 0.86, "confidence": 0.75, "latency": 2.8, "cost": 0.03},
    ]

    frontier = pareto_frontier(points)
    ids = {int(p["id"]) for p in frontier}

    # Point 2 is dominated by point 0 on all dimensions.
    assert ids == {0, 1}
