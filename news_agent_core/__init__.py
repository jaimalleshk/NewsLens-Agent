"""News & Analysis Agent Core Library / SDK.

A modular AI-powered news intelligence framework providing live multi-source news ingestion,
temporal RAG indexing, DeepSeek and Local Ollama inference, strict 5-line executive summarization,
and natural broadcast voice synthesis.
"""

from .config import AppConfig, ConfigManager, TopicConfig, LLMConfig, SearchConfig, VoiceConfig, DateRange
from .search.base import RawArticle, NewsItem, NewsSummary5Lines, TopicNewsResult, AggregatedNewsDigest
from .search.ddg_search import DDGNewsSearch
from .search.rss_search import RSSNewsSearch
from .rag.vector_store import NewsVectorStore, DocumentChunk
from .llm.client import UnifiedLLMClient
from .agent.analyst import NewsAnalystAgent
from .agent.chat_agent import AgentDialogueManager, AgentChatResponse
from .voice.tts import NaturalVoiceBriefer

__version__ = "0.1.0"

__all__ = [
    "AppConfig",
    "ConfigManager",
    "TopicConfig",
    "LLMConfig",
    "SearchConfig",
    "VoiceConfig",
    "DateRange",
    "RawArticle",
    "NewsItem",
    "NewsSummary5Lines",
    "TopicNewsResult",
    "AggregatedNewsDigest",
    "DDGNewsSearch",
    "RSSNewsSearch",
    "NewsVectorStore",
    "DocumentChunk",
    "UnifiedLLMClient",
    "NewsAnalystAgent",
    "AgentDialogueManager",
    "AgentChatResponse",
    "NaturalVoiceBriefer",
]
