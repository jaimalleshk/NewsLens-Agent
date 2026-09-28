"""RSS and Google News search provider implementation."""

from __future__ import annotations
import hashlib
import logging
from typing import List, Optional
from datetime import datetime, timezone
from urllib.parse import quote_plus
import feedparser
import httpx

from .base import BaseSearchEngine, RawArticle
from .extractor import ArticleExtractor

logger = logging.getLogger(__name__)


class RSSNewsSearch(BaseSearchEngine):
    """Fetches real-time news via Google News RSS & structured feeds."""

    GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    def __init__(self, extractor: Optional[ArticleExtractor] = None):
        self.extractor = extractor or ArticleExtractor()

    async def search(
        self,
        query: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_results: int = 5,
        topic_id: Optional[str] = None
    ) -> List[RawArticle]:
        articles: List[RawArticle] = []

        rss_query = query
        if start_date and end_date:
            rss_query = f"{query} after:{start_date} before:{end_date}"
        elif start_date:
            rss_query = f"{query} after:{start_date}"

        url = self.GOOGLE_NEWS_RSS_URL.format(query=quote_plus(rss_query))

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []

                feed = feedparser.parse(resp.text)

                for entry in feed.entries:
                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    summary = getattr(entry, "summary", "").strip()
                    published_parsed = getattr(entry, "published_parsed", None)

                    if not title or not link:
                        continue

                    source = "News"
                    if " - " in title:
                        parts = title.rsplit(" - ", 1)
                        title = parts[0].strip()
                        source = parts[1].strip()

                    pub_date_iso = None
                    if published_parsed:
                        pub_date_iso = datetime(*published_parsed[:6]).strftime("%Y-%m-%d")

                    if pub_date_iso and start_date and pub_date_iso < start_date:
                        continue
                    if pub_date_iso and end_date and pub_date_iso > end_date:
                        continue

                    art_id = hashlib.sha256(f"{title}_{link}".encode("utf-8")).hexdigest()[:16]
                    clean_summary = self.extractor.clean_html(summary) if summary else ""

                    articles.append(RawArticle(
                        id=art_id,
                        title=title,
                        url=link,
                        snippet=clean_summary or title,
                        published_date=pub_date_iso or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        source=source,
                        topic_id=topic_id
                    ))

                    if len(articles) >= max_results:
                        break

        except Exception as e:
            logger.warning(f"RSS News search error for '{query}': {e}")

        return articles
