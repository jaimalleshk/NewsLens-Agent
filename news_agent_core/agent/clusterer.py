"""Story clustering and deduplication across multiple media outlets."""

from __future__ import annotations
import re
from typing import List, Dict
from ..search.base import RawArticle


class StoryClusterer:
    """Groups duplicate coverage of the same news event into consolidated clusters."""

    def __init__(self, similarity_threshold: float = 0.45):
        self.similarity_threshold = similarity_threshold

    def _normalize_title(self, title: str) -> set[str]:
        words = re.findall(r"\b[a-z0-9]{3,}\b", title.lower())
        # Filter common stopwords
        stopwords = {"the", "and", "for", "with", "this", "that", "from", "after", "over", "about", "into", "news", "report"}
        return {w for w in words if w not in stopwords}

    def _jaccard_similarity(self, set1: set[str], set2: set[str]) -> float:
        if not set1 or not set2:
            return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0.0

    def cluster(self, articles: List[RawArticle]) -> List[List[RawArticle]]:
        """Cluster list of articles into groups of related stories."""
        if not articles:
            return []

        clusters: List[List[RawArticle]] = []
        cluster_wordsets: List[set[str]] = []

        for art in articles:
            art_words = self._normalize_title(art.title)
            best_cluster_idx = -1
            best_sim = 0.0

            for idx, c_words in enumerate(cluster_wordsets):
                sim = self._jaccard_similarity(art_words, c_words)
                if sim > best_sim and sim >= self.similarity_threshold:
                    best_sim = sim
                    best_cluster_idx = idx

            if best_cluster_idx >= 0:
                clusters[best_cluster_idx].append(art)
                cluster_wordsets[best_cluster_idx].update(art_words)
            else:
                clusters.append([art])
                cluster_wordsets.append(set(art_words))

        return clusters
