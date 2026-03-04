# MoAA-Prime

MoAA-Prime is a research prototype for a Mixture of Adaptive Agents workflow:

- contract-based specialist agents
- prompt router + decision metadata
- oracle scoring
- swarm deliberation
- memory hooks (ReasoningBank + E-MRE)
- contract evolution (GCEL)
- optional real-model execution via Ollama

## Quickstart

```bash
git clone https://github.com/maddwiz/moaa-prime.git
cd moaa-prime
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

If you only want local tests and do not need heavy dependencies immediately, use:

```bash
python -m pip install -e . --no-deps
```

## Test

```bash
python -m pytest -q
```

## CLI

Canonical module entrypoint:

```bash
python -m moaa_prime "Solve: 2x + 3 = 7. Return only x."
```

Explicit subcommands:

```bash
python -m moaa_prime hello
python -m moaa_prime route "Write Python: function add(a,b) returns a+b"
python -m moaa_prime swarm "Explain why 1/0 is undefined."
```

Console script (after install):

```bash
moaa-prime route "2+2?"
```

## Demo Bundle

```bash
python scripts/demo_run.py
python scripts/bench_run.py
python scripts/eval_run.py
python scripts/render_report.py
```

Generated files:

- `reports/demo_run.json`
- `reports/bench.json`
- `reports/eval_report.json`
- `reports/final_report.json`

`reports/` is generated output and is gitignored.

## Ollama (Optional)

```bash
export MOAA_LLM_PROVIDER=ollama
export MOAA_OLLAMA_HOST="http://127.0.0.1:11434"
export MOAA_OLLAMA_MODEL="llama3.1:8b-instruct-q4_K_M"
```

Sanity check:

```bash
curl -s http://127.0.0.1:11434/api/tags | head
```
