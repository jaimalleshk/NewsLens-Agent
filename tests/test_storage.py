"""Unit tests for SQLite persistent caching layer in NewsLens."""

import os
import tempfile
import pytest
from pathlib import Path
from news_agent_core.storage.sqlite_db import SQLiteNewsCache
from news_agent_core.search.base import (
    RawArticle,
    NewsItem,
    NewsSummary5Lines,
    TopicNewsResult,
    AggregatedNewsDigest
)
from news_agent_core.config import TopicConfig, ConfigManager
from news_agent_core.agent.analyst import NewsAnalystAgent


@pytest.fixture
def temp_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_newslens.db"
        cache = SQLiteNewsCache(db_path=db_path)
        yield cache


def test_sqlite_cache_raw_articles(temp_cache: SQLiteNewsCache):
    articles = [
        RawArticle(
            id="art-1",
            url="https://example.com/art1",
            title="NVIDIA Unveils New AI Architecture",
            source="TechNews",
            published_date="2026-09-25",
            snippet="NVIDIA announces high efficiency compute.",
            content="Full body text of the announcement."
        ),
        RawArticle(
            id="art-2",
            url="https://example.com/art2",
            title="Cloud Infrastructure Expands",
            source="CloudWeekly",
            published_date="2026-09-26",
            snippet="Major investments in data centers.",
            content="Full body details."
        )
    ]

    temp_cache.save_raw_articles(articles, topic_id="ai")
    
    with temp_cache._get_connection() as conn:
        rows = conn.execute("SELECT * FROM raw_articles WHERE topic_id = 'ai'").fetchall()
        assert len(rows) == 2
        assert rows[0]["id"] == "art-1"
        assert rows[0]["title"] == "NVIDIA Unveils New AI Architecture"


def test_sqlite_cache_topic_result(temp_cache: SQLiteNewsCache):
    summary = NewsSummary5Lines(
        line1_what="Major chip release boosting AI inference.",
        line2_context="Semiconductor industry competition intensifies.",
        line3_impact="Hyperscalers upgrade hardware stacks.",
        line4_data="40% efficiency gains reported.",
        line5_outlook="Commercial availability in Q4."
    )
    item = NewsItem(
        id="item-1",
        title="Next Gen GPU Launch",
        url="https://example.com/gpu",
        publisher="SiliconReview",
        published_date="2026-09-27",
        topic_id="ai",
        summary=summary,
        natural_speech="In artificial intelligence, Next Gen GPU launched today."
    )
    result = TopicNewsResult(
        topic_id="ai",
        topic_title="Artificial Intelligence & Autonomous Systems",
        topic_icon="🤖",
        strategy_applied="Track breakthrough AI foundation models.",
        start_date="2026-09-20",
        end_date="2026-09-27",
        items=[item],
        executive_audio_script="Here is your AI briefing."
    )

    # Save to SQLite
    temp_cache.save_topic_result(result)

    # Retrieve from SQLite
    cached = temp_cache.get_topic_result("ai", "2026-09-20", "2026-09-27")
    assert cached is not None
    assert cached.topic_id == "ai"
    assert len(cached.items) == 1
    assert cached.items[0].title == "Next Gen GPU Launch"
    assert cached.items[0].summary.line1_what == "Major chip release boosting AI inference."

    # Non-existent range returns None
    missing = temp_cache.get_topic_result("ai", "2026-01-01", "2026-01-07")
    assert missing is None


def test_sqlite_cache_digest(temp_cache: SQLiteNewsCache):
    summary = NewsSummary5Lines(
        line1_what="Federal Reserve keeps rates unchanged.",
        line2_context="Inflation stabilized at targeted rate.",
        line3_impact="Bond yields remain steady.",
        line4_data="Labor market adds 180k jobs.",
        line5_outlook="Next policy meeting in November."
    )
    item = NewsItem(
        id="fin-1",
        title="Central Bank Holds Rates Steady",
        url="https://example.com/fed",
        publisher="FinancialWire",
        published_date="2026-09-27",
        topic_id="finance",
        summary=summary
    )
    topic_res = TopicNewsResult(
        topic_id="finance",
        topic_title="Financial Markets & Macro Economy",
        topic_icon="📈",
        strategy_applied="Track macro trends.",
        start_date="2026-09-20",
        end_date="2026-09-27",
        items=[item],
        executive_audio_script="Here is your finance update."
    )
    digest = AggregatedNewsDigest(
        generated_at="2026-09-27T12:00:00Z",
        start_date="2026-09-20",
        end_date="2026-09-27",
        executive_overview="Macro summary across sectors.",
        executive_audio_script="Executive spoken audio broadcast.",
        topic_results=[topic_res],
        total_articles_indexed=10
    )

    temp_cache.save_digest(digest)

    cached_digest = temp_cache.get_digest("2026-09-20", "2026-09-27")
    assert cached_digest is not None
    assert cached_digest.start_date == "2026-09-20"
    assert cached_digest.executive_overview == "Macro summary across sectors."
    assert len(cached_digest.topic_results) == 1
    assert cached_digest.topic_results[0].items[0].title == "Central Bank Holds Rates Steady"


def test_sqlite_cache_clear(temp_cache: SQLiteNewsCache):
    summary = NewsSummary5Lines(
        line1_what="Medical trials show positive results.",
        line2_context="Phase 3 trial completed.",
        line3_impact="Potential FDA approval next year.",
        line4_data="85% efficacy observed.",
        line5_outlook="Application filing planned."
    )
    item = NewsItem(
        id="med-1",
        title="New Therapy Approved",
        url="https://example.com/med",
        publisher="HealthToday",
        published_date="2026-09-27",
        topic_id="health",
        summary=summary
    )
    topic_res = TopicNewsResult(
        topic_id="health",
        topic_title="Health & BioTech",
        topic_icon="🧬",
        strategy_applied="Track medical innovations.",
        start_date="2026-09-20",
        end_date="2026-09-27",
        items=[item],
        executive_audio_script="Health updates."
    )
    digest = AggregatedNewsDigest(
        generated_at="2026-09-27T12:00:00Z",
        start_date="2026-09-20",
        end_date="2026-09-27",
        executive_overview="Health overview.",
        executive_audio_script="Health audio.",
        topic_results=[topic_res],
        total_articles_indexed=5
    )

    temp_cache.save_topic_result(topic_res)
    temp_cache.save_digest(digest)

    # Verify present
    assert temp_cache.get_topic_result("health", "2026-09-20", "2026-09-27") is not None
    assert temp_cache.get_digest("2026-09-20", "2026-09-27") is not None

    # Clear specific date range
    temp_cache.clear_cache(start_date="2026-09-20", end_date="2026-09-27")
    assert temp_cache.get_topic_result("health", "2026-09-20", "2026-09-27") is None
    assert temp_cache.get_digest("2026-09-20", "2026-09-27") is None
