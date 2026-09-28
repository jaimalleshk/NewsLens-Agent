"""DuckDuckGo News search engine implementation with date filtering."""

from __future__ import annotations
import hashlib
import logging
from typing import List, Optional
from datetime import datetime, timezone
from urllib.parse import urlparse
from duckduckgo_search import DDGS

from .base import BaseSearchEngine, RawArticle
from .extractor import ArticleExtractor

logger = logging.getLogger(__name__)


class DDGNewsSearch(BaseSearchEngine):
    """Searches news using DuckDuckGo News."""

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
        import asyncio
        articles: List[RawArticle] = []

        def _fetch():
            try:
                with DDGS() as ddgs:
                    return list(ddgs.news(
                        keywords=query,
                        region="wt-wt",
                        safesearch="moderate",
                        max_results=max_results * 2
                    ))
            except Exception as ex:
                logger.debug(f"DDGS fetch error: {ex}")
                return []

        try:
            raw_results = await asyncio.wait_for(asyncio.to_thread(_fetch), timeout=4.0)

            for item in raw_results:
                title = item.get("title", "").strip()
                url = item.get("url") or item.get("link", "")
                snippet = item.get("body", "") or item.get("snippet", "")
                date_str = item.get("date", "")
                source = item.get("source", "")

                if not title or not url:
                    continue

                pub_date_iso = None
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        pub_date_iso = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pub_date_iso = date_str[:10] if len(date_str) >= 10 else None

                # Apply date filter if bounds provided
                if pub_date_iso and start_date and pub_date_iso < start_date:
                    continue
                if pub_date_iso and end_date and pub_date_iso > end_date:
                    continue

                if not source:
                    try:
                        source = urlparse(url).netloc.replace("www.", "")
                    except Exception:
                        source = "Web"

                art_id = hashlib.sha256(f"{title}_{url}".encode("utf-8")).hexdigest()[:16]

                articles.append(RawArticle(
                    id=art_id,
                    title=title,
                    url=url,
                    snippet=snippet,
                    published_date=pub_date_iso or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    source=source,
                    topic_id=topic_id
                ))

                if len(articles) >= max_results:
                    break

        except Exception as e:
            logger.warning(f"DuckDuckGo search error for '{query}': {e}")

        return articles
