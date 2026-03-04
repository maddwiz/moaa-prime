from __future__ import annotations

from collections import Counter

from moaa_prime.eval.cases import CATEGORY_ORDER, CORE_EVAL_CASES


def test_pr5_core_eval_cases_catalog_shape_is_deterministic() -> None:
    assert len(CORE_EVAL_CASES) >= 30

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
    assert all(counts[category] >= 5 for category in CATEGORY_ORDER)
