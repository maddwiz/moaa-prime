# MoAA-Prime Demo Bundle

## Prerequisite

Install the package first:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## Run (Order Matters)

```bash
python scripts/demo_run.py
python scripts/bench_run.py
python scripts/eval_run.py
python scripts/render_report.py
```

`render_report.py` expects the first three output files to exist.

## Outputs

- `reports/demo_run.json` (single-run + swarm + evolve payload)
- `reports/bench.json` (latency timing summary)
- `reports/eval_report.json` (eval case results)
- `reports/final_report.json` (aggregated final report)

## LLM Mode

Defaults:

- `MOAA_LLM_PROVIDER=stub`
- `MOAA_OLLAMA_HOST=http://127.0.0.1:11434`
- `MOAA_OLLAMA_MODEL=llama3.1:8b-instruct`

Ollama example:

```bash
export MOAA_LLM_PROVIDER=ollama
export MOAA_OLLAMA_HOST="http://127.0.0.1:11434"
export MOAA_OLLAMA_MODEL="llama3.1:8b-instruct"
```

`reports/` is generated output and should stay untracked.
