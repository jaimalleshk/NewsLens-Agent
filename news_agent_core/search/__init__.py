"""Search package exports."""

from .base import RawArticle, NewsItem, NewsSummary5Lines, TopicNewsResult, AggregatedNewsDigest, BaseSearchEngine
from .extractor import ArticleExtractor
from .ddg_search import DDGNewsSearch
from .rss_search import RSSNewsSearch

__all__ = [
    "RawArticle",
    "NewsItem",
    "NewsSummary5Lines",
    "TopicNewsResult",
    "AggregatedNewsDigest",
    "BaseSearchEngine",
    "ArticleExtractor",
    "DDGNewsSearch",
    "RSSNewsSearch"
]
