# FILEMAP — MoAA-Prime
Canonical repo map. Update ONLY after phase completion.

---

## Root
- MASTER_HANDOFF.md
- FILEMAP.md
- CHANGELOG.md
- pyproject.toml
- src/
- tests/

---

## Core
- src/moaa_prime/core/app.py        → MoAAPrime entry object

---

## CLI
- src/moaa_prime/cli/__main__.py
- src/moaa_prime/cli/phase9_stable_cmd.py

---

## Agents
- src/moaa_prime/agents/base.py
- src/moaa_prime/agents/math_agent.py
- src/moaa_prime/agents/code_agent.py

---

## Contracts
- src/moaa_prime/contracts/contract.py

---

## Routing
- src/moaa_prime/router/meta_router.py

---

## Oracle
- src/moaa_prime/oracle/verifier.py

---

## Swarm
- src/moaa_prime/swarm/manager.py
- src/moaa_prime/swarm/stable_runner.py

---

## Memory
- src/moaa_prime/memory/agent_lane.py
- src/moaa_prime/memory/reasoning_bank.py
- src/moaa_prime/memory/cos.py

---

## E-MRE
- src/moaa_prime/mre/aedmc.py
- src/moaa_prime/mre/sh_cos.py
- src/moaa_prime/mre/gfo.py

---

## Fusion / Geometry
- src/moaa_prime/sgm.py
- src/moaa_prime/fusion.py

---

## Stability
- src/moaa_prime/sfc.py

---

## Tests
- tests/test_phase1_smoke.py
- tests/test_phase2_router.py
- tests/test_phase3_oracle.py
- tests/test_phase4_swarm.py
- tests/test_phase5_memory.py
- tests/test_phase6_emre.py
- tests/test_phase7_sgm.py
- tests/test_phase8_fusion.py
- tests/test_phase9_swarm_sfc_gate.py
- tests/test_phase9_cli_stable_cmd.py

