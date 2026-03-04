from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable, Sequence

from moaa_prime.contracts import Contract

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _stable_hash(token: str, seed: int, salt: str = "") -> int:
    raw = f"{seed}|{salt}|{token}".encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:16], 16)


def text_embedding(text: str, *, dim: int = 24, seed: int = 0) -> list[float]:
    if dim <= 0:
        raise ValueError("dim must be positive")

    tokens = _tokenize(text)
    if not tokens:
        return [0.0 for _ in range(dim)]

    vec = [0.0 for _ in range(dim)]
    for tok in tokens:
        idx = _stable_hash(tok, seed, "idx") % dim
        sign = 1.0 if (_stable_hash(tok, seed, "sgn") % 2 == 0) else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0.0:
        return vec
    return [v / norm for v in vec]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(float(a[i]) * float(b[i]) for i in range(n))
    na = math.sqrt(sum(float(a[i]) * float(a[i]) for i in range(n)))
    nb = math.sqrt(sum(float(b[i]) * float(b[i]) for i in range(n)))
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))


def contract_text(contract: Contract) -> str:
    parts: list[str] = [contract.name]
    if contract.description:
        parts.append(contract.description)
    parts.extend(contract.domains or [])
    parts.extend(contract.tools or [])
    parts.extend(contract.tags or [])
    return " ".join(str(p) for p in parts if str(p).strip())


def contract_embedding(contract: Contract, *, dim: int = 24, seed: int = 0) -> list[float]:
    return text_embedding(contract_text(contract), dim=dim, seed=seed)


def task_embedding(prompt: str, *, dim: int = 24, seed: int = 0) -> list[float]:
    return text_embedding(prompt, dim=dim, seed=seed)


def mean_embedding(vectors: Iterable[Sequence[float]], *, dim: int = 24) -> list[float]:
    out = [0.0 for _ in range(dim)]
    count = 0
    for vec in vectors:
        count += 1
        n = min(len(out), len(vec))
        for i in range(n):
            out[i] += float(vec[i])
    if count == 0:
        return out
    return [v / float(count) for v in out]
