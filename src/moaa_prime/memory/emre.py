from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Optional, Dict, Any, Tuple
import hashlib
import math


# ============================================================
# Deterministic tiny "embeddings" (no dependencies, stable)
# ============================================================
def _hash_embed(text: str, dim: int = 64) -> List[float]:
    h = hashlib.sha256((text or "").encode("utf-8")).digest()
    out: List[float] = []
    for i in range(dim):
        b = h[i % len(h)]
        out.append((b / 255.0) * 2.0 - 1.0)
    return out


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a)) + 1e-9
    db = math.sqrt(sum(y * y for y in b)) + 1e-9
    return float(num / (da * db))


# ============================================================
# Entropy proxy (cheap AEDMC signal)
# ============================================================
def entropy_proxy(text: str) -> float:
    """
    0.0 ~ predictable / tiny
    1.0 ~ high variety / longer / messier
    """
    t = (text or "").strip()
    if len(t) <= 6:
        return 0.15
    uniq = len(set(t.lower()))
    score = (uniq / max(10, len(t))) * 4.0
    return float(max(0.1, min(1.0, score)))


# ============================================================
# AEDMC-lite: choose Markov order k based on entropy
# ============================================================
def aedmc_order(entropy: float, k_min: int = 1, k_max: int = 5) -> int:
    e = float(max(0.0, min(1.0, entropy)))
    # map [0,1] -> [k_min,k_max]
    k = k_min + int(round(e * (k_max - k_min)))
    return int(max(k_min, min(k_max, k)))


# ============================================================
# Grok riff: curiosity bump (+1 order when high entropy + novel)
# ============================================================
def curiosity_bump_order(
    base_k: int,
    entropy: float,
    kl_to_global: float,
    kl_thresh: float = 0.50,
    k_max: int = 5,
) -> int:
    """
    If a segment is BOTH:
      - high entropy (messy / OOD-ish)
      - high KL vs global bank (novel / under-explored)
    then bump Markov order by +1 to pull a bit more history.
    """
    bump = 1 if (entropy >= 0.70 and kl_to_global >= kl_thresh) else 0
    return int(min(k_max, max(1, int(base_k) + bump)))


# ============================================================
# SH-COS (text-only v1): semantic + mid + episodic summaries
# ============================================================
@dataclass(frozen=True)
class SHCOS:
    semantic: str
    mid: str
    episodic: str

    def as_text(self) -> str:
        return (
            "## SH-COS (semantic)\n"
            f"{self.semantic}\n\n"
            "## SH-COS (mid)\n"
            f"{self.mid}\n\n"
            "## SH-COS (episodic)\n"
            f"{self.episodic}\n"
        )


def build_shcos(segments: Sequence[str], max_chars: int = 1200) -> SHCOS:
    """
    Cheap summarizer (no model): we keep it deterministic.
    - episodic: last few raw snippets
    - mid: compact bullet of last N
    - semantic: very compact "what is this lane about" guess
    """
    segs = [s.strip() for s in segments if (s or "").strip()]
    if not segs:
        return SHCOS(semantic="", mid="", episodic="")

    last = segs[-6:]
    episodic = "\n".join(f"- {s[:240]}" for s in last)

    mid = "\n".join(f"- {s[:120]}" for s in segs[-12:])

    # semantic: hash-based "topic hint" (still deterministic)
    joined = " ".join(segs[-20:])
    hint = joined[:400]
    semantic = f"Lane theme hint: {hint}"

    # clamp
    def clamp(x: str) -> str:
        x = x.strip()
        if len(x) <= max_chars:
            return x
        return x[: max_chars - 3] + "..."

    return SHCOS(
        semantic=clamp(semantic),
        mid=clamp(mid),
        episodic=clamp(episodic),
    )


# ============================================================
# GFO-lite helpers (geometric-ish pruning stubs)
# ============================================================
def sim_score(query: str, text: str, dim: int = 64) -> float:
    return _cosine(_hash_embed(query, dim=dim), _hash_embed(text, dim=dim))


def kl_proxy(local_text: str, global_text: str) -> float:
    """
    Not true KL. Just a bounded novelty proxy in [0,1].
    Higher = more different from global memory.
    """
    if not global_text.strip():
        return 1.0
    s = sim_score(local_text, global_text)
    # sim in [-1,1] => novelty in [0,1]
    novelty = (1.0 - ((s + 1.0) / 2.0))
    return float(max(0.0, min(1.0, novelty)))


def gfo_keep_mask(
    query: str,
    items: Sequence[str],
    keep_quantile: float = 0.90,
) -> List[bool]:
    """
    Keep top (keep_quantile) by similarity to query anchor.
    Very simple "forgetting oracle" v0.
    """
    if not items:
        return []
    scores = [sim_score(query, it) for it in items]
    # threshold at quantile
    sorted_scores = sorted(scores)
    idx = int(max(0, min(len(sorted_scores) - 1, round((1.0 - keep_quantile) * (len(sorted_scores) - 1)))))
    thresh = sorted_scores[idx]
    return [s >= thresh for s in scores]


