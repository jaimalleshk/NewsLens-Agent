"""SQLite storage and persistent caching layer for NewsLens."""

from __future__ import annotations
import json
import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Generator

from ..search.base import RawArticle, NewsItem, TopicNewsResult, AggregatedNewsDigest

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "newslens.db"


class SQLiteNewsCache:
    """Manages persistent SQLite storage and caching for news articles, topic results, and digests."""

    def __init__(self, db_path: Optional[str | Path] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS raw_articles (
                    id TEXT PRIMARY KEY,
                    url TEXT,
                    title TEXT,
                    source TEXT,
                    published_date TEXT,
                    snippet TEXT,
                    content TEXT,
                    topic_id TEXT,
                    fetched_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS topic_results (
                    topic_id TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    topic_title TEXT,
                    topic_icon TEXT,
                    strategy_applied TEXT,
                    executive_audio_script TEXT,
                    items_json TEXT,
                    cached_at TEXT,
                    PRIMARY KEY (topic_id, start_date, end_date)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS aggregated_digests (
                    digest_id TEXT PRIMARY KEY,
                    start_date TEXT,
                    end_date TEXT,
                    executive_overview TEXT,
                    executive_audio_script TEXT,
                    digest_json TEXT,
                    created_at TEXT
                )
            """)
            conn.commit()

    def save_raw_articles(self, articles: List[RawArticle], topic_id: str) -> None:
        """Cache raw retrieved articles into SQLite."""
        if not articles:
            return
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            for a in articles:
                conn.execute("""
                    INSERT OR REPLACE INTO raw_articles 
                    (id, url, title, source, published_date, snippet, content, topic_id, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    a.id,
                    a.url,
                    a.title,
                    a.source,
                    a.published_date,
                    a.snippet,
                    a.content,
                    topic_id,
                    now_str
                ))
            conn.commit()

    def save_topic_result(self, result: TopicNewsResult) -> None:
        """Save a fully analyzed TopicNewsResult into SQLite."""
        now_str = datetime.now(timezone.utc).isoformat()
        items_serialized = [it.model_dump() for it in result.items]
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO topic_results
                (topic_id, start_date, end_date, topic_title, topic_icon, strategy_applied, executive_audio_script, items_json, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.topic_id,
                result.start_date,
                result.end_date,
                result.topic_title,
                result.topic_icon,
                result.strategy_applied,
                result.executive_audio_script,
                json.dumps(items_serialized, ensure_ascii=False),
                now_str
            ))
            conn.commit()

    def get_topic_result(self, topic_id: str, start_date: str, end_date: str) -> Optional[TopicNewsResult]:
        """Retrieve cached TopicNewsResult if exists."""
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT * FROM topic_results
                WHERE topic_id = ? AND start_date = ? AND end_date = ?
            """, (topic_id, start_date, end_date))
            row = cur.fetchone()
            if not row:
                return None

            items_raw = json.loads(row["items_json"]) if row["items_json"] else []
            items = [NewsItem.model_validate(it) for it in items_raw]
            return TopicNewsResult(
                topic_id=row["topic_id"],
                topic_title=row["topic_title"],
                topic_icon=row["topic_icon"],
                strategy_applied=row["strategy_applied"],
                start_date=row["start_date"],
                end_date=row["end_date"],
                items=items,
                executive_audio_script=row["executive_audio_script"]
            )

    def save_digest(self, digest: AggregatedNewsDigest) -> None:
        """Save full AggregatedNewsDigest into SQLite."""
        digest_id = f"{digest.start_date}_{digest.end_date}"
        now_str = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO aggregated_digests
                (digest_id, start_date, end_date, executive_overview, executive_audio_script, digest_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                digest_id,
                digest.start_date,
                digest.end_date,
                digest.executive_overview,
                digest.executive_audio_script,
                json.dumps(digest.model_dump(), ensure_ascii=False),
                now_str
            ))
            conn.commit()

    def get_digest(self, start_date: str, end_date: str) -> Optional[AggregatedNewsDigest]:
        """Retrieve cached AggregatedNewsDigest for specific date window if exists."""
        digest_id = f"{start_date}_{end_date}"
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT digest_json FROM aggregated_digests WHERE digest_id = ?
            """, (digest_id,))
            row = cur.fetchone()
            if row:
                data = json.loads(row["digest_json"])
                return AggregatedNewsDigest.model_validate(data)

            # Fallback: check if topic_results exist for this date range
            cur_topics = conn.execute("""
                SELECT * FROM topic_results
                WHERE start_date = ? AND end_date = ?
                ORDER BY cached_at DESC
            """, (start_date, end_date))
            rows = cur_topics.fetchall()
            if rows:
                seen_topics = set()
                topic_results = []
                for r in rows:
                    tid = r["topic_id"]
                    if tid in seen_topics:
                        continue
                    seen_topics.add(tid)
                    items_raw = json.loads(r["items_json"]) if r["items_json"] else []
                    items = [NewsItem.model_validate(it) for it in items_raw]
                    topic_results.append(TopicNewsResult(
                        topic_id=r["topic_id"],
                        topic_title=r["topic_title"],
                        topic_icon=r["topic_icon"],
                        strategy_applied=r["strategy_applied"],
                        start_date=r["start_date"],
                        end_date=r["end_date"],
                        items=items,
                        executive_audio_script=r["executive_audio_script"]
                    ))
                if topic_results:
                    return AggregatedNewsDigest(
                        generated_at=datetime.now(timezone.utc).isoformat(),
                        start_date=start_date,
                        end_date=end_date,
                        executive_overview=f"Executive cross-sector intelligence digest across {len(topic_results)} monitored topics.",
                        executive_audio_script="",
                        topic_results=topic_results,
                        total_articles_indexed=sum(len(t.items) for t in topic_results)
                    )
            return None

    def get_latest_digest(self) -> Optional[AggregatedNewsDigest]:
        """Retrieve the most recently cached AggregatedNewsDigest from SQLite or construct from latest topic_results."""
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT digest_json FROM aggregated_digests 
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                data = json.loads(row["digest_json"])
                return AggregatedNewsDigest.model_validate(data)

            # Fallback: assemble from most recent topic_results table
            cur_topics = conn.execute("""
                SELECT * FROM topic_results
                ORDER BY cached_at DESC
            """)
            rows = cur_topics.fetchall()
            if not rows:
                return None

            seen_topics = set()
            topic_results = []
            s_date = ""
            e_date = ""
            for r in rows:
                tid = r["topic_id"]
                if tid in seen_topics:
                    continue
                seen_topics.add(tid)
                s_date = s_date or r["start_date"]
                e_date = e_date or r["end_date"]
                items_raw = json.loads(r["items_json"]) if r["items_json"] else []
                items = [NewsItem.model_validate(it) for it in items_raw]
                topic_results.append(TopicNewsResult(
                    topic_id=r["topic_id"],
                    topic_title=r["topic_title"],
                    topic_icon=r["topic_icon"],
                    strategy_applied=r["strategy_applied"],
                    start_date=r["start_date"],
                    end_date=r["end_date"],
                    items=items,
                    executive_audio_script=r["executive_audio_script"]
                ))

            if not topic_results:
                return None

            return AggregatedNewsDigest(
                generated_at=datetime.now(timezone.utc).isoformat(),
                start_date=s_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                end_date=e_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                executive_overview=f"Executive cross-sector intelligence digest across {len(topic_results)} monitored topics.",
                executive_audio_script="",
                topic_results=topic_results,
                total_articles_indexed=sum(len(t.items) for t in topic_results)
            )

    def clear_cache(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> None:
        """Clear cached entries, optionally filtered by date range."""
        with self._get_connection() as conn:
            if start_date and end_date:
                digest_id = f"{start_date}_{end_date}"
                conn.execute("DELETE FROM aggregated_digests WHERE digest_id = ?", (digest_id,))
                conn.execute("DELETE FROM topic_results WHERE start_date = ? AND end_date = ?", (start_date, end_date))
            else:
                conn.execute("DELETE FROM aggregated_digests")
                conn.execute("DELETE FROM topic_results")
                conn.execute("DELETE FROM raw_articles")
            conn.commit()

