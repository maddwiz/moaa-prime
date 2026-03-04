from moaa_prime.contracts import Contract
from moaa_prime.evolution.gcel import GCELV2



def test_gcel_v2_gates_when_eval_does_not_improve():
    contracts = [
        Contract(name="a", domains=["math"], competence=0.80, reliability=0.80, cost_prior=0.20),
        Contract(name="b", domains=["code"], competence=0.70, reliability=0.78, cost_prior=0.30),
    ]

    metrics = {
        "a": {"oracle_score": 0.8, "eval_success": 0.8, "budget_efficiency": 0.8},
        "b": {"oracle_score": 0.7, "eval_success": 0.7, "budget_efficiency": 0.7},
    }

    target_comp = {"a": 0.80, "b": 0.70}

    def evaluator(cs, _fitness):
        return sum(1.0 - abs(c.competence - target_comp[c.name]) for c in cs) / len(cs)

    gcel = GCELV2(seed=123, mutation_step=0.03, reliability_step=0.03, cost_step=0.03)
    outcome = gcel.evolve(contracts, metrics, evaluator=evaluator)

    assert outcome.accepted is False
    assert [c.name for c in outcome.contracts] == ["a", "b"]
    assert [c.competence for c in outcome.contracts] == [0.80, 0.70]



def test_gcel_v2_is_deterministic_for_same_seed():
    contracts = [
        Contract(name="a", domains=["math"], competence=0.80, reliability=0.80, cost_prior=0.20),
        Contract(name="b", domains=["code"], competence=0.70, reliability=0.78, cost_prior=0.30),
    ]

    metrics = {
        "a": {"oracle_score": 0.9, "eval_success": 0.8, "budget_efficiency": 0.8},
        "b": {"oracle_score": 0.6, "eval_success": 0.7, "budget_efficiency": 0.7},
    }

    g1 = GCELV2(seed=77)
    g2 = GCELV2(seed=77)

    o1 = g1.evolve(contracts, metrics)
    o2 = g2.evolve(contracts, metrics)

    assert o1.accepted == o2.accepted
    assert o1.baseline_score == o2.baseline_score
    assert o1.candidate_score == o2.candidate_score
    assert [(c.name, c.competence, c.reliability, c.cost_prior) for c in o1.contracts] == [
        (c.name, c.competence, c.reliability, c.cost_prior) for c in o2.contracts
    ]
