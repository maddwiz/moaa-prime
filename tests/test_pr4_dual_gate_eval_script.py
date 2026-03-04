from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_eval_dual_gate_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "eval_dual_gate.py"
    spec = importlib.util.spec_from_file_location("eval_dual_gate_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pr4_eval_dual_gate_script_emits_deterministic_non_regression(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    module = _load_eval_dual_gate_module()

    exit_code_1 = module.main()
    report_path = tmp_path / "reports" / "dual_gated_eval.json"
    payload_1 = json.loads(report_path.read_text(encoding="utf-8"))

    exit_code_2 = module.main()
    payload_2 = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code_1 == 0
    assert exit_code_2 == 0
    assert payload_1 == payload_2
    assert payload_1["suite"] == "pr4_dual_gate"
    assert payload_1["summary"]["dual_gated"]["pass_rate_delta_vs_baseline"] >= 0.0
    assert payload_1["summary"]["dual_gated"]["oracle_delta_vs_baseline"] >= 0.0
