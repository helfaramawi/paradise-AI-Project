"""Local, deterministic text embeddings (feature hashing of word tokens and character n-grams).

This is a lexical-semantic vector that works offline for Arabic and English and is stored in pgvector.
It is *not* a neural embedding; when an external embedding provider is configured it can be swapped in
behind :func:`embed` without schema changes (same dimension).
"""

from __future__ import annotations

import hashlib
import math

from ..config import get_settings
from ..core.text import norm, tokens

DIM = get_settings().embedding_dim
PROVIDER = "local-hashing-v1"


def _h(s: str) -> tuple[int, float]:
    d = hashlib.blake2b(s.encode(), digest_size=8).digest()
    v = int.from_bytes(d, "little")
    return v % DIM, 1.0 if (v >> 63) & 1 else -1.0


def embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    toks = tokens(text)
    for t in toks:
        i, s = _h("w:" + t)
        vec[i] += s * 1.0
        for k in range(len(t) - 2):
            i, s = _h("c:" + t[k:k + 3])
            vec[i] += s * 0.35
    for a, b in zip(toks, toks[1:], strict=False):
        i, s = _h("b:" + a + "_" + b)
        vec[i] += s * 0.6
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        i += size - overlap
    return out


__all__ = ["embed", "cosine", "chunk_text", "norm", "PROVIDER"]
