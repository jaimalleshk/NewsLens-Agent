"""In-memory and file-backed temporal RAG Vector Store for news analysis."""

from __future__ import annotations
import re
from typing import List, Dict, Optional, Any
import numpy as np
from pydantic import BaseModel, Field

from .embeddings import HybridSemanticEmbedder
from ..search.base import RawArticle


class DocumentChunk(BaseModel):
    """Chunk of an indexed news article with metadata."""
    chunk_id: str
    article_id: str
    title: str
    url: str
    published_date: str
    source: str
    topic_id: Optional[str]
    text: str
    score: float = 0.0


class NewsVectorStore:
    """Stores article chunks and performs temporal semantic retrieval."""

    def __init__(self, chunk_size: int = 450, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunks: List[DocumentChunk] = []
        self.vectors: Optional[np.ndarray] = None
        self.embedder = HybridSemanticEmbedder()
        self.articles_map: Dict[str, RawArticle] = {}

    def clear(self) -> None:
        self.chunks.clear()
        self.vectors = None
        self.articles_map.clear()

    def add_articles(self, articles: List[RawArticle]) -> int:
        """Process, chunk, and index incoming news articles."""
        new_chunks: List[DocumentChunk] = []
        all_texts: List[str] = []

        for art in articles:
            self.articles_map[art.id] = art
            # Create full text body from content or snippet
            body = art.content.strip() or art.snippet.strip()
            full_text = f"{art.title}. {body}"

            # Split into chunks
            words = full_text.split()
            if len(words) <= self.chunk_size:
                chunks_text = [" ".join(words)]
            else:
                chunks_text = []
                for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
                    chunk = " ".join(words[i : i + self.chunk_size])
                    if len(chunk) > 30:
                        chunks_text.append(chunk)

            for idx, c_text in enumerate(chunks_text):
                c_id = f"{art.id}_chk_{idx}"
                doc_chunk = DocumentChunk(
                    chunk_id=c_id,
                    article_id=art.id,
                    title=art.title,
                    url=art.url,
                    published_date=art.published_date or "",
                    source=art.source,
                    topic_id=art.topic_id,
                    text=c_text
                )
                new_chunks.append(doc_chunk)
                all_texts.append(c_text)

        if not new_chunks:
            return 0

        self.chunks.extend(new_chunks)

        # Re-fit embedder on all chunk texts
        corpus = [c.text for c in self.chunks]
        self.embedder.fit_corpus(corpus)

        # Compute vectors
        matrix = [self.embedder.embed_text(c.text) for c in self.chunks]
        self.vectors = np.array(matrix, dtype=np.float32)

        return len(new_chunks)

    def search(
        self,
        query: str,
        topic_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        top_k: int = 5
    ) -> List[DocumentChunk]:
        """Query the vector store with semantic similarity and temporal filtering."""
        if not self.chunks or self.vectors is None or len(self.vectors) == 0:
            return []

        query_vec = self.embedder.embed_text(query)
        if np.linalg.norm(query_vec) == 0:
            return self.chunks[:top_k]

        # Compute cosine similarities
        scores = np.dot(self.vectors, query_vec)

        # Filter and rank
        results: List[DocumentChunk] = []
        for i, score in enumerate(scores):
            chunk = self.chunks[i]

            # Topic filter
            if topic_id and chunk.topic_id and chunk.topic_id != topic_id:
                continue

            # Date filters
            if start_date and chunk.published_date and chunk.published_date < start_date:
                continue
            if end_date and chunk.published_date and chunk.published_date > end_date:
                continue

            chunk_copy = chunk.model_copy(update={"score": float(score)})
            results.append(chunk_copy)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def get_articles_for_topic(self, topic_id: str) -> List[RawArticle]:
        return [art for art in self.articles_map.values() if art.topic_id == topic_id]
