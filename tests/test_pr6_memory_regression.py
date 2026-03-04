from __future__ import annotations

import pytest

from moaa_prime.agents.base import BaseAgent
from moaa_prime.contracts import Contract
from moaa_prime.llm import StubLLMClient
from moaa_prime.memory import EpisodicLane, MemoryItem, ReasoningBank


def _base_agent(*, name: str, bank: ReasoningBank) -> BaseAgent:
    return BaseAgent(
        Contract(name=name, domains=[name.split("-")[0]]),
        bank=bank,
        llm=StubLLMClient(model=f"stub-{name}"),
    )


def test_pr6_long_chain_recall_before_write_and_canonical_lane() -> None:
    bank = ReasoningBank()
    agent = _base_agent(name="math-agent", bank=bank)
    task_id = "pr6-chain"

    first = agent.handle("chain-step-0", task_id=task_id)
    first_memory = first.meta["memory"]
    assert first_memory["bank_hits"] == 0
    assert first_memory["local_hits"] == 0
    assert first_memory["bank_snippets"] == []
    assert first_memory["local_snippets"] == []
    assert isinstance(first_memory["kl_like"], float)
    assert isinstance(first_memory["global_text"], str)

    latest = first
    for idx in range(1, 20):
        latest = agent.handle(f"chain-step-{idx}", task_id=task_id)

    memory = latest.meta["memory"]
    assert memory["task_id"] == task_id
    assert "lane_recall" in memory["method"]
    assert isinstance(memory["bank_hits"], int)
    assert isinstance(memory["local_hits"], int)
    assert all(isinstance(snippet, str) for snippet in memory["bank_snippets"])
    assert all(isinstance(snippet, str) for snippet in memory["local_snippets"])
    assert all(item.task_id == task_id for item in bank.items)
    assert all((item.meta or {}).get("lane") == "math-agent" for item in bank.items)
    assert len(bank.items) == 20


def test_pr6_reasoning_bank_write_payload_validation_and_dict_support() -> None:
    bank = ReasoningBank()
    bank.write({"task_id": "task-a", "text": "stored text", "lane": "math-agent"})

    assert len(bank.items) == 1
    assert bank.items[0].task_id == "task-a"
    assert bank.items[0].text == "stored text"
    assert (bank.items[0].meta or {}).get("lane") == "math-agent"

    with pytest.raises(ValueError):
        bank.write({"task_id": "task-a"})
    with pytest.raises(ValueError):
        bank.write({"text": "missing task id"})
    with pytest.raises(ValueError):
        bank.write({})

    assert len(bank.items) == 1


def test_pr6_entropy_spike_novelty_bump_increases_recall_order() -> None:
    lane = EpisodicLane(name="math-agent", working_max=999)
    task_id = "pr6-entropy"
    for idx in range(12):
        lane.append(MemoryItem(task_id=task_id, text=f"entropy-item-{idx}"))

    # entropy_proxy(query) == 0.8 -> base k=4, novelty bump pushes to k=5.
    query = "aaaaabbbbbcccccdddddeeeeefffffggggghhhhhiiiiijjjjj"
    low_novelty = lane.recall(query=query, task_id=task_id, kl_like=0.0)
    high_novelty = lane.recall(query=query, task_id=task_id, kl_like=1.0)

    assert low_novelty.local_hits == 4
    assert high_novelty.local_hits == 5
    assert high_novelty.local_hits == low_novelty.local_hits + 1
    assert "SH-COS" in high_novelty.global_text


def test_pr6_pruning_events_occur_and_lane_stays_recallable() -> None:
    lane = EpisodicLane(name="math-agent", working_max=8, keep_top_frac=0.5, min_keep=3)
    task_id = "pr6-prune"

    saw_prune = False
    for idx in range(30):
        before = len(lane.items)
        lane.append(MemoryItem(task_id=task_id, text=f"segment-{idx}"))
        after = len(lane.items)
        if after < (before + 1):
            saw_prune = True

    assert saw_prune is True
    assert len(lane.items) < 30
    assert len(lane.items) >= 3

    recall = lane.recall(
        query="long chain long chain long chain long chain long chain",
        task_id=task_id,
        kl_like=0.0,
    )
    assert recall.local_hits >= 1
    assert "SH-COS" in recall.global_text


def test_pr6_recall_stability_under_unrelated_writes() -> None:
    bank = ReasoningBank()
    math_agent = _base_agent(name="math-agent", bank=bank)
    code_agent = _base_agent(name="code-agent", bank=bank)

    task_id = "pr6-stable"
    for idx in range(8):
        math_agent.handle(f"signal-{idx}", task_id=task_id)

    baseline = math_agent._bank_recall(task_id=task_id, prompt="signal-query")

    for idx in range(40):
        code_agent.handle(f"noise-{idx}", task_id="pr6-other")

    after = math_agent._bank_recall(task_id=task_id, prompt="signal-query")

    assert after["bank_hits"] == baseline["bank_hits"]
    assert after["local_hits"] == baseline["local_hits"]
    assert after["bank_snippets"] == baseline["bank_snippets"]
    assert after["local_snippets"] == baseline["local_snippets"]
