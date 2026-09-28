"""Embedding and semantic similarity computation for news RAG."""

from __future__ import annotations
import re
import math
import numpy as np
from typing import List, Dict, Optional
import httpx


class HybridSemanticEmbedder:
    """Computes dense and sparse semantic embeddings for news indexing and retrieval."""

    def __init__(self, ollama_base_url: Optional[str] = None):
        self.ollama_base_url = ollama_base_url
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        # Extract alphanumeric terms with 2+ characters
        return [w for w in re.findall(r"\b[a-z0-9_\-]{2,}\b", text)]

    def fit_corpus(self, corpus: List[str]) -> None:
        """Calculate IDF weights across current document corpus."""
        doc_count = len(corpus)
        if doc_count == 0:
            return

        df: Dict[str, int] = {}
        for text in corpus:
            tokens = set(self._tokenize(text))
            for t in tokens:
                df[t] = df.get(t, 0) + 1

        self.idf = {term: math.log((doc_count + 1) / (count + 1)) + 1.0 for term, count in df.items()}
        # Top 4096 most informative terms
        sorted_terms = sorted(self.idf.items(), key=lambda x: x[1], reverse=True)[:4096]
        self.vocab = {term: i for i, (term, _) in enumerate(sorted_terms)}

    def embed_text(self, text: str) -> np.ndarray:
        """Produce a normalized semantic TF-IDF vector."""
        if not self.vocab:
            # Create a 256-dim feature hash vector if vocab not fitted yet
            vec = np.zeros(256, dtype=np.float32)
            tokens = self._tokenize(text)
            for t in tokens:
                idx = abs(hash(t)) % 256
                vec[idx] += 1.0
            norm = np.linalg.norm(vec)
            return vec / (norm + 1e-9)

        dim = len(self.vocab)
        vec = np.zeros(dim, dtype=np.float32)
        tokens = self._tokenize(text)
        if not tokens:
            return vec

        tf: Dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        for term, count in tf.items():
            if term in self.vocab:
                idx = self.vocab[term]
                idf_weight = self.idf.get(term, 1.0)
                vec[idx] = (count / len(tokens)) * idf_weight

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))
