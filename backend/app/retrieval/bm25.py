"""A compact, dependency-free BM25 Okapi ranker (PLAN_PART_5 §1.3).

The plan suggested ``rank-bm25``; we inline the ~30-line Okapi scoring instead so
the submission has zero extra runtime deps and the ranking is fully deterministic
and unit-testable offline. At our scale (≤50 short documents) the difference is
immaterial. Tokenization is a simple lowercase word split — adequate for English
marketing/news copy; an embedding retriever would replace this wholesale.
"""

from __future__ import annotations

import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Okapi BM25 free parameters (the canonical defaults).
_K1 = 1.5
_B = 0.75


def tokenize(text: str) -> list[str]:
    """Lowercase word tokenization (alphanumeric runs)."""
    return _TOKEN_RE.findall(text.lower())


class Bm25Index:
    """An in-memory BM25 Okapi index over a fixed corpus of documents."""

    def __init__(self, documents: list[str]) -> None:
        self._docs: list[list[str]] = [tokenize(doc) for doc in documents]
        self._doc_count = len(self._docs)
        self._doc_lengths = [len(doc) for doc in self._docs]
        self._avg_len = (
            sum(self._doc_lengths) / self._doc_count if self._doc_count else 0.0
        )
        # Per-document term frequencies and document frequency per term.
        self._term_freqs: list[dict[str, int]] = []
        doc_freq: dict[str, int] = {}
        for tokens in self._docs:
            freqs: dict[str, int] = {}
            for token in tokens:
                freqs[token] = freqs.get(token, 0) + 1
            self._term_freqs.append(freqs)
            for term in freqs:
                doc_freq[term] = doc_freq.get(term, 0) + 1
        # Smoothed IDF (always positive, so common terms never score negative).
        self._idf: dict[str, float] = {
            term: math.log(1 + (self._doc_count - df + 0.5) / (df + 0.5))
            for term, df in doc_freq.items()
        }

    def score(self, query: str, doc_index: int) -> float:
        """BM25 score of one document for ``query``."""
        if self._avg_len == 0:
            return 0.0
        freqs = self._term_freqs[doc_index]
        doc_len = self._doc_lengths[doc_index]
        score = 0.0
        for term in set(tokenize(query)):
            tf = freqs.get(term)
            if not tf:
                continue
            idf = self._idf.get(term, 0.0)
            denom = tf + _K1 * (1 - _B + _B * doc_len / self._avg_len)
            score += idf * (tf * (_K1 + 1)) / denom
        return score

    def top_k(self, query: str, k: int) -> list[int]:
        """Return up to ``k`` document indices ranked by descending BM25 score.

        Ties (e.g., all-zero scores when the query shares no terms) break by
        original order, so results are stable. Zero-score documents are still
        returned to fill ``k`` — callers wanting only matches can filter by score.
        """
        scored = [(self.score(query, i), i) for i in range(self._doc_count)]
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [i for _score, i in scored[:k]]
