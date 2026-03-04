import json

from moaa_prime.trace import TraceRecorder


def test_trace_recorder_writes_trace_and_dataset(tmp_path):
    traces = tmp_path / "reports" / "traces"
    dataset = tmp_path / "datasets" / "router_training.jsonl"

    recorder = TraceRecorder(trace_dir=str(traces), dataset_path=str(dataset))

    out = recorder.record(
        run_id="abc123",
        mode="v3",
        task_id="t1",
        prompt="explain fibonacci trading strategy",
        trace={
            "router": {"ranked": [{"agent": "finance-agent"}]},
            "final": {"confidence": 0.82},
        },
        candidates=[
            {
                "agent": "analysis-agent",
                "oracle": {"score": 0.71, "meta": {}},
                "latency_proxy": 1.4,
                "cost_proxy": 0.002,
                "confidence_proxy": 0.72,
            },
            {
                "agent": "finance-agent",
                "oracle": {"score": 0.89, "meta": {}},
                "latency_proxy": 1.3,
                "cost_proxy": 0.002,
                "confidence_proxy": 0.81,
            },
        ],
        best={"agent": "finance-agent"},
        contracts={
            "analysis-agent": {
                "domains": ["analysis"],
                "tools": ["calc"],
                "competence": 0.7,
                "reliability": 0.7,
                "cost_prior": 0.3,
                "description": "analysis",
                "tags": ["analysis"],
            },
            "finance-agent": {
                "domains": ["finance"],
                "tools": ["market-data"],
                "competence": 0.8,
                "reliability": 0.8,
                "cost_prior": 0.3,
                "description": "finance",
                "tags": ["finance"],
            },
        },
        budget_mode="balanced",
        avg_latency=1.35,
        avg_cost=0.002,
    )

    assert "trace_path" in out
    assert "dataset_path" in out
    assert (traces / "run_abc123.json").exists()
    assert dataset.exists()

    payload = json.loads((traces / "run_abc123.json").read_text(encoding="utf-8"))
    assert payload["winner"] == "finance-agent"
    assert payload["router_choice"] == "finance-agent"

    lines = dataset.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["run_id"] == "abc123"
