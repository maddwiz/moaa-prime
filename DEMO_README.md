# MoAA-Prime — Demo Bundle

This repository demonstrates a Mixture of Adaptive Agents system with:

- Verifiable agent routing
- Multi-agent swarm reasoning
- Memory with E-MRE (anti-rot)
- Oracle-based truth scoring
- Dual-brain architecture
- Evolutionary contract updates
- Real model inference (Ollama)

## One-command demo
```bash
pytest -q
python scripts/demo_run.py
python scripts/bench_run.py
python scripts/eval_run.py
python scripts/render_report.py                                                            Outputs
	•	reports/demo_run.json      -> raw agent outputs
	•	reports/bench.json         -> latency
	•	reports/eval_report.json   -> correctness
	•	reports/final_report.json  -> human-readable summary

This is a research prototype intended for evaluation and acquisition discussions.
