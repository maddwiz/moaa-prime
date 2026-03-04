# Architecture Cycle 3 — Learning System

## Goal
Cycle 3 converts MoAA-Prime from a static orchestrator into a self-improving loop.

Added capabilities:
- learned routing (`RouterV3`)
- per-run trace capture for training
- contract embeddings
- adaptive budget modes (`cheap`, `balanced`, `max_quality`)
- Pareto swarm selection for score/latency/cost/confidence tradeoffs

## End-to-End Flow
1. Prompt enters `MoAAPrime.run_swarm(...)`.
2. `RouterV3` ranks agents via learned expected-success model.
3. Swarm generates candidates and oracle scores.
4. `SwarmManager(mode="v3")` builds Pareto frontier and selects candidate by budget profile.
5. Run trace is written to `reports/traces/run_<id>.json`.
6. Training row is appended to `datasets/router_training.jsonl`.
7. `scripts/train_router.py` retrains and saves `models/router_v3.pt`.

## RouterV3
File:
- `src/moaa_prime/router/router_v3.py`

Inputs:
- task prompt and metadata
- contract embedding + priors
- historical success/oracle/latency/cost
- memory alignment hints
- budget mode

Feature vector:
- `similarity`
- `competence`
- `reliability`
- `success_rate`
- `oracle_history`
- `latency_efficiency`
- `cost_efficiency`
- `memory_alignment`
- `budget_mode_value` (`cheap=0.0`, `balanced=0.5`, `max_quality=1.0`, fallback `0.5`)

Model:
- deterministic logistic model (`RouterV3Model`)
- loaded from `models/router_v3.pt` when present
- fallback to stable default weights when model file is missing
- expected-success logits can be conditioned on normalized budget mode via `budget_mode_value`
- post-logit calibration (`calibration_scale`, `calibration_bias`) is applied deterministically
- calibration parameters are persisted in `models/router_v3.pt`

Budget weighting:
- `cheap`: prioritize cost/latency more
- `balanced`: mixed trade-off
- `max_quality`: prioritize expected success

## Contract Embeddings
Files:
- `src/moaa_prime/contracts/contract.py`
- `src/moaa_prime/router/embeddings.py`

Contract schema additions:
- `tags`
- `description`
- `embedding`

Embedding approach:
- deterministic hashed bag-of-words vector
- cosine similarity with task embedding
- no external model dependency required

## SwarmV3 Selection
Files:
- `src/moaa_prime/swarm/manager.py`
- `src/moaa_prime/swarm/pareto.py`

Candidate metrics used for Pareto set:
- oracle `score` (higher better)
- `confidence` (higher better)
- `latency` (lower better)
- `cost` (lower better)

Selector behavior:
- compute Pareto frontier
- apply budget profile weights
- choose best utility point from frontier
- include Pareto details in trace (`trace.swarm.pareto`)

## Trace Dataset Pipeline
File:
- `src/moaa_prime/trace/recorder.py`

Per-run trace output:
- `reports/traces/run_<id>.json`

Aggregated training dataset:
- `datasets/router_training.jsonl`

Stored fields include:
- task/prompt
- agent list
- router choice
- oracle scores
- winner
- latency/cost/confidence
- per-agent metrics
- contract snapshot (including embeddings)

## Training Pipeline
Files:
- `src/moaa_prime/router/training.py`
- `scripts/train_router.py`

Workflow:
1. load traces + dataset rows
2. extract per-agent training examples, including deterministic budget-mode numeric conditioning
3. split examples deterministically by `run_id` group for base-training train/validation
4. train deterministic logistic model with seed and class-balanced sample weighting
5. apply deterministic validation-NLL early stopping for base training and restore best epoch parameters
6. if run-group validation cannot be formed (for example a single `run_id`), train on all examples without early stopping
7. split examples deterministically by `run_id` group for calibration train/validation
8. require binary label support (both positive and negative labels) in calibration-train and calibration-validation; otherwise skip calibration
9. fit deterministic post-logit calibration parameters on calibration-train split with empirical (unweighted) prevalence
10. keep calibration only when empirical (unweighted) validation NLL improves vs identity (`scale=1`, `bias=0`)
11. save model to `models/router_v3.pt`
12. write report `reports/router_train_report.json` including:
   - `training_accuracy`
   - `training_brier_score`
   - `training_ece`
   - calibration parameters (`calibration_scale`, `calibration_bias`)

## Router Eval Pipeline
File:
- `scripts/eval_router.py`

Compares `v2` vs `v3` and writes:
- `reports/eval_router.json`

Metrics:
- `routing_accuracy`
- `oracle_score_gain`
- `latency_efficiency`
- `cost_efficiency`
