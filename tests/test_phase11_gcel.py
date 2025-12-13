from moaa_prime.contracts import Contract
from moaa_prime.evolution.gcel import GCEL


def test_gcel_preserves_names_and_length():
    contracts = [
        Contract(name="a", domains=["math"], competence=0.8, tools=["sympy"]),
        Contract(name="b", domains=["code"], competence=0.7, tools=["exec"]),
    ]
    fitness = {"a": 0.9, "b": 0.1}

    gcel = GCEL(seed=123, elite_frac=0.5, mutation_step=0.05)
    out = gcel.evolve(contracts, fitness)

    assert len(out) == 2
    assert [c.name for c in out] == ["a", "b"]


def test_gcel_competence_clamped():
    contracts = [
        Contract(name="a", domains=["math"], competence=0.99, tools=["sympy"]),
        Contract(name="b", domains=["code"], competence=0.01, tools=["exec"]),
    ]
    fitness = {"a": 1.0, "b": 0.0}

    gcel = GCEL(seed=999, elite_frac=0.5, mutation_step=0.5)
    out = gcel.evolve(contracts, fitness)

    for c in out:
        assert 0.05 <= c.competence <= 0.99


def test_app_evolve_contracts_smoke():
    from moaa_prime.core.app import MoAAPrime

    app = MoAAPrime()
    snap = app.evolve_contracts({"math-agent": 1.0, "code-agent": 0.2})

    assert "before" in snap and "after" in snap
    assert len(snap["before"]) == 2
    assert len(snap["after"]) == 2
