# Filemap — moaa-prime

## Core entrypoints
- src/moaa_prime/core/app.py
  - MoAAPrime: constructs agents, router, oracle, swarm
  - run_once(prompt) -> {decision, result, oracle}
  - run_swarm(prompt) -> {best, candidates}

## Agents
- src/moaa_prime/agents/
  - MathAgent: stub math handler
  - CodeAgent: stub code handler

## Contracts
- src/moaa_prime/contracts/
  - Contract: name/domains/competence/tools (Phase 1-2)

## Routing
- src/moaa_prime/router/
  - MetaRouter: route(prompt), top_k(prompt,k)

## Oracle
- src/moaa_prime/oracle/verifier.py
  - OracleVerifier.score(prompt, answer) -> OracleVerdict
  - OracleVerifier.verify(prompt, answer, agent_name=None) -> OracleVerdict

## Swarm
- src/moaa_prime/swarm/manager.py
  - SwarmManager.run(prompt) -> {best, candidates}

## Tests
- tests/
  - test_phase4_swarm.py
  - other phase tests (must remain green)
