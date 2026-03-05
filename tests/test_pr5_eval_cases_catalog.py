from __future__ import annotations

from collections import Counter

from moaa_prime.eval.cases import CATEGORY_ORDER, CORE_EVAL_CASES


def test_pr5_core_eval_cases_catalog_shape_is_deterministic() -> None:
    assert len(CORE_EVAL_CASES) >= 36

    ids = [str(case["id"]) for case in CORE_EVAL_CASES]
    prompts = [str(case["prompt"]) for case in CORE_EVAL_CASES]
    categories = [str(case["category"]) for case in CORE_EVAL_CASES]

    assert len(ids) == len(set(ids))
    assert all(prompt.strip() for prompt in prompts)
    assert all(category in CATEGORY_ORDER for category in categories)


def test_pr5_core_eval_cases_catalog_balances_required_categories() -> None:
    counts = Counter(str(case["category"]) for case in CORE_EVAL_CASES)
    expected = set(CATEGORY_ORDER)
    assert set(counts.keys()) == expected
    assert all(counts[category] >= 6 for category in CATEGORY_ORDER)


def test_pr5_core_eval_cases_catalog_exposes_routing_and_memory_deterministic_fields() -> None:
    routing_cases = [case for case in CORE_EVAL_CASES if str(case.get("category", "")) == "routing_intent"]
    memory_cases = [case for case in CORE_EVAL_CASES if str(case.get("category", "")) == "memory_behavior"]

    assert routing_cases
    assert memory_cases
    assert all(str(case.get("expected_intent", "")) in {"math", "code"} for case in routing_cases)
    assert all(str(case.get("setup_prompt", "")).strip() for case in memory_cases)
    assert all(str(case.get("expected_exact", "")).strip() for case in memory_cases)
