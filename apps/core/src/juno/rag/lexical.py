"""Keyword rank over chunk text, fused with vector rank inside retrieve()."""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]{2,}")
_K1 = 1.5
_B = 0.75
_RRF_K = 60


def tokens(text: str) -> list[str]:
    return _TOKEN.findall((text or "").casefold())


def bm25_rank(query: str, docs: list[tuple[str, str]], *, limit: int = 8) -> list[str]:
    """Return document ids best-first. ``docs`` are ``(id, text)``."""
    q_terms = tokens(query)
    if not q_terms or limit < 1 or not docs:
        return []
    parsed: list[tuple[str, list[str]]] = []
    for doc_id, text in docs:
        doc_tokens = tokens(text)
        if doc_tokens:
            parsed.append((doc_id, doc_tokens))
    if not parsed:
        return []
    n_docs = len(parsed)
    avgdl = sum(len(toks) for _, toks in parsed) / n_docs
    df: Counter[str] = Counter()
    for _, toks in parsed:
        df.update(set(toks))
    q_counts = Counter(q_terms)
    scored: list[tuple[float, str]] = []
    for doc_id, toks in parsed:
        tf = Counter(toks)
        dl = len(toks)
        score = 0.0
        for term, qf in q_counts.items():
            if term not in tf:
                continue
            idf = math.log(1.0 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            freq = tf[term]
            denom = freq + _K1 * (1.0 - _B + _B * dl / avgdl)
            score += idf * (freq * (_K1 + 1.0) / denom) * qf
        if score > 0:
            scored.append((score, doc_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [doc_id for _, doc_id in scored[:limit]]


def reciprocal_rank_fusion(rankings: list[list[str]], *, k: int = _RRF_K) -> list[str]:
    """Merge ranked id lists. An empty list is ignored so one side can stand alone."""
    scores: dict[str, float] = {}
    order: list[str] = []
    for ranking in rankings:
        for index, doc_id in enumerate(ranking):
            if doc_id not in scores:
                order.append(doc_id)
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + index + 1)
    order.sort(key=lambda doc_id: (-scores[doc_id], doc_id))
    return order
