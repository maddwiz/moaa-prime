# MoAA-Prime Demo Bundle

## Run

```bash
python -m pytest -q
python scripts/demo_run.py
python scripts/bench_run.py
python scripts/eval_run.py
python scripts/render_report.py
```

## Outputs

- `reports/demo_run.json`: raw single-run and swarm outputs
- `reports/bench.json`: timing summary
- `reports/eval_report.json`: eval cases and outcomes
- `reports/final_report.json`: aggregated summary report

## Notes

- `reports/` is generated output and must stay gitignored.
- Default LLM mode is stub for deterministic local runs.
- Optional Ollama mode is controlled by `MOAA_LLM_PROVIDER=ollama`.
