"""Semantic search over fixed evidence sections using sentence-transformers.

Used only for the challenge/priority free-text paths — not for the main
recommendation retrieval, which uses fixed section IDs to ensure determinism
across experimental conditions.

Falls back to keyword overlap if the model cannot be loaded (e.g. offline).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .schemas import EvidenceSection

_MODEL_NAME = "all-MiniLM-L6-v2"
_STOP_WORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "of", "in", "to", "for", "is", "are",
        "where", "that", "this", "with", "shall", "not", "may", "be", "on",
        "at", "by", "it", "its", "has", "have",
    }
)


def _keyword_scores(query: str, sections: list["EvidenceSection"]) -> list[tuple[int, "EvidenceSection"]]:
    """Keyword overlap fallback (same logic as original EvidenceStore.search)."""
    q_words = set(re.findall(r"\w+", query.lower())) - _STOP_WORDS
    scored = []
    for s in sections:
        words = set(re.findall(r"\w+", (s.text + " " + s.heading).lower())) - _STOP_WORDS
        overlap = len(q_words & words)
        if overlap > 0:
            scored.append((overlap, s))
    scored.sort(key=lambda x: -x[0])
    return scored


class SemanticEvidenceSearch:
    """Embeds all evidence sections once at init; answers semantic search queries.

    Corpus is small (~30 sections) so numpy cosine similarity is used directly —
    no FAISS index needed.
    """

    def __init__(self, sections: list["EvidenceSection"]) -> None:
        self._sections = sections
        self._embeddings: np.ndarray | None = None
        self._available = False
        self._load(sections)

    def _load(self, sections: list["EvidenceSection"]) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model = SentenceTransformer(_MODEL_NAME)
            texts = [f"{s.heading}. {s.text}" for s in sections]
            raw = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            self._embeddings = np.array(raw, dtype=np.float32)
            self._model = model
            self._available = True
        except Exception:
            self._available = False

    def search(self, query: str, top_k: int = 8) -> list["EvidenceSection"]:
        """Return top-k sections most semantically similar to query.

        Falls back to keyword overlap if sentence-transformers is unavailable.
        """
        if not self._available or self._embeddings is None:
            scored = _keyword_scores(query, self._sections)
            return [s for _, s in scored[:top_k]]

        q_vec = self._model.encode([query], normalize_embeddings=True, show_progress_bar=False)
        q_vec = np.array(q_vec, dtype=np.float32)
        scores = (self._embeddings @ q_vec.T).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [self._sections[i] for i in top_indices]
