from __future__ import annotations

from moaa_prime.core.app import MoAAPrime


def test_phase5_memory_writes_and_reads() -> None:
    app = MoAAPrime()

    out1 = app.run_once("Remember: the answer is 42", task_id="t1")
    assert "memory" in out1["result"]["meta"]

    out2 = app.run_once("What was the answer?", task_id="t1")
    mem = out2["result"]["meta"]["memory"]
    assert "local_hits" in mem
    assert "bank_hits" in mem
