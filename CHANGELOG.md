# CHANGELOG — MoAA-Prime

Keep this short and factual. Update at the end of each phase.

## Phase 6 — E-MRE v1 (DONE)
- Added E-MRE lane memory (EpisodicLane) with:
  - AEDMC-lite Markov order selection (entropy -> k)
  - Grok riff: curiosity bump (+1 order when high entropy + novel)
  - SH-COS (multi-level carry-over summaries) producing `global_text`
  - GFO pruning to keep lanes bounded
- Added/updated ReasoningBank to support:
  - per-agent lanes + global store
  - backward-compatible `write(...)` API
  - lane recall with kl_like signal
- Updated BaseAgent memory handling while preserving Phase 5 behavior
- Tests passing; pushed to GitHub

