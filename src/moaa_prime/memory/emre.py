from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence
import hashlib
import math


# ============================================================
# Deterministic tiny "embeddings" (no deps, stable)
# ============================================================

def _hash_embed(text: str, dim: int = 64) -> List[float]:
    h = hashlib.sha256((text or "").encode("utf-8", errors="ignore")).digest()
    out: List[float] = []
    for i in range(dim):
        b = h[i % len(h)]
        out.append((b / 255.0) * 2.0 - 1.0)
    n = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / n for x in out]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


# ============================================================
# Entropy proxy (cheap AEDMC signal)
# ============================================================

def entropy_proxy(text: str) -> float:
    """
    Cheap entropy proxy in [0.1, 1.0]
    Low for tiny/repetitive text; higher for longer/more diverse text.
    """
    t = (text or "").strip()
    if len(t) <= 6:
        return 0.15
    uniq = len(set(t.lower()))
    score = (uniq / max(10, len(t))) * 4.0
    return float(max(0.1, min(1.0, score)))


# ============================================================
# AEDMC-lite (adaptive Markov order)
# ============================================================

def choose_markov_order(entropy: float, k_min: int = 1, k_max: int = 5) -> int:
    e = float(max(0.0, min(1.0, entropy)))
    k = k_min + int(round(e * (k_max - k_min)))
    return int(max(k_min, min(k_max, k)))


# ============================================================
# Grok riff: curiosity bump (+1 order when high entropy + novel)
# ============================================================

def curiosity_bump_order(entropy: float, base_k: int, kl_like: float, bump_thresh: float = 0.65) -> int:
    """
    If the query is high-entropy AND feels novel (kl_like high), bump k by +1.
    """
    k = int(base_k)
    if float(entropy) >= bump_thresh and float(kl_like) >= 0.50:
        k += 1
    return int(max(1, min(5, k)))


# ============================================================
# SH-COS (superposed hierarchical COS) — text-only v1
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


def build_sh_cos(texts: Sequence[str]) -> SHCOS:
    """
    v1 heuristic:
      - semantic: first 1 item
      - mid: first 3 items
      - episodic: last 5 items
    """
    arr = [t for t in texts if (t or "").strip()]
    if not arr:
        return SHCOS(semantic="", mid="", episodic="")
    semantic = arr[0]
    mid = "\n".join(arr[:3])
    episodic = "\n".join(arr[-5:])
    return SHCOS(semantic=semantic, mid=mid, episodic=episodic)


# ============================================================
# GFO (geometric forgetting oracle) — anchor-guided keep mask
# ============================================================

def gfo_keep_mask(
    segments: Sequence[str],
    task_anchor: str,
    keep_top_frac: float = 0.85,
    min_keep: int = 16,
) -> List[bool]:
    """
    Keep the segments most similar to the task anchor (cheap cosine over hash-embeds).
    """
    segs = list(segments)
    if not segs:
        return []

    anchor_v = _hash_embed(task_anchor)
    scores = [float(_cosine(_hash_embed(s), anchor_v)) for s in segs]

    # compute keep_n
    keep_n = int(math.ceil(len(segs) * float(keep_top_frac)))
    keep_n = max(int(min_keep), keep_n)
    keep_n = min(len(segs), keep_n)

    # score cutoff = kth best
    sorted_scores = sorted(scores, reverse=True)
    cutoff = sorted_scores[keep_n - 1] if keep_n - 1 < len(sorted_scores) else sorted_scores[-1]

    return [s >= cutoff for s in scores]
