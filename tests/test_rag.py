"""Unit tests for RAG vector store and semantic search."""

import pytest
from news_agent_core.rag.vector_store import NewsVectorStore
from news_agent_core.search.base import RawArticle


def test_vector_store_indexing_and_temporal_search():
    store = NewsVectorStore(chunk_size=100, chunk_overlap=20)

    articles = [
        RawArticle(
            id="art1",
            title="NVIDIA announces new Blackwell Ultra GPU with high bandwidth memory",
            url="https://example.com/nvidia-blackwell",
            snippet="NVIDIA unveiled next-generation AI accelerators with enhanced HBM3e memory.",
            content="NVIDIA announced the Blackwell Ultra GPU designed for massive LLM training and inference workloads.",
            published_date="2026-09-22",
            source="TechNews",
            topic_id="ai_hardware"
        ),
        RawArticle(
            id="art2",
            title="Federal Reserve signals cautious interest rate trajectory amid inflation reports",
            url="https://example.com/fed-rates",
            snippet="The Fed announced policy interest rates will remain steady.",
            content="Central bankers discussed labor market data and inflation cooling at the latest FOMC meeting.",
            published_date="2026-09-24",
            source="MarketWatch",
            topic_id="macro_markets"
        )
    ]

    indexed_count = store.add_articles(articles)
    assert indexed_count >= 2

    # Query for GPU/AI
    results = store.search("Blackwell AI GPU accelerator", top_k=2)
    assert len(results) > 0
    assert "nvidia" in results[0].text.lower() or "gpu" in results[0].text.lower()

    # Query with date filter
    filtered = store.search("rates inflation", start_date="2026-09-23", end_date="2026-09-25")
    assert len(filtered) > 0
    assert filtered[0].article_id == "art2"
