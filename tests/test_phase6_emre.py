from __future__ import annotations

from moaa_prime.memory import EpisodicLane, MemoryItem, ReasoningBank


def test_emre_lane_adaptive_k_and_shcos_present():
    lane = EpisodicLane(name="math", working_max=999)
    task_id = "t1"
    for i in range(10):
        lane.append(MemoryItem(task_id=task_id, text=f"Remember item {i}"))

    # low-entropy query => small k
    r1 = lane.recall("hi", task_id=task_id, kl_like=0.0)
    assert r1.local_hits in (1, 2)
    assert "SH-COS" in r1.global_text

    # higher-entropy query => larger k
    r2 = lane.recall("Explain why (a+b)^2 expands and show steps, include examples!", task_id=task_id, kl_like=0.0)
    assert r2.local_hits >= r1.local_hits
    assert "semantic" in r2.global_text.lower()


def test_reasoning_bank_returns_kl_like_and_global_text():
    bank = ReasoningBank()
    task_id = "t2"
    bank.write(MemoryItem(task_id=task_id, text="We decided the answer is 42."))
    bank.write(MemoryItem(task_id=task_id, text="We used sympy to verify x=2."))

    out = bank.recall("What was the answer again?", task_id=task_id, top_k=2)
    assert out["bank_hits"] == 2
    assert isinstance(out["kl_like"], float)
    assert "SH-COS" in out["global_text"]
