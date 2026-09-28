"""Configuration models and persistence manager for News & Analysis Agent (supporting YAML & JSON)."""

from __future__ import annotations
import os
import re
import json
import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class TopicConfig(BaseModel):
    """Configuration for a dynamic news topic/tab."""
    id: str = Field(..., description="Unique slug ID for the topic (e.g. 'ai_ml')")
    title: str = Field(..., description="Display title for the dynamic tab (e.g. 'AI & Machine Learning')")
    icon: str = Field("📰", description="Emoji icon for the tab")
    enabled: bool = Field(True, description="Whether this topic is active in UI and aggregation")
    max_articles: Optional[int] = Field(None, ge=1, le=100, description="Optional custom maximum articles count for this topic")
    strategy_prompt: str = Field(..., description="Strategic focus prompt guiding the RAG and LLM summarizer")
    search_queries: List[str] = Field(default_factory=list, description="Target search query templates for ingestion")
    priority_sources: List[str] = Field(default_factory=list, description="Optional preferred domains or publications")


class LLMConfig(BaseModel):
    """Configuration for LLM inference (DeepSeek AI or Local Ollama/OpenAI-compatible)."""
    provider: str = Field("local", description="'local' (Ollama / local server) or 'deepseek' (online API)")
    model: str = Field("deepseek-r1:8b", description="Model name (e.g. 'deepseek-r1:8b', 'llama3.3', 'deepseek-chat')")
    api_key: str = Field("", description="API key for DeepSeek or OpenRouter")
    api_base: str = Field("https://api.deepseek.com/v1", description="API Base URL for online provider")
    local_api_base: str = Field("http://localhost:11434/v1", description="API Base URL for local Ollama / OpenAI server")
    temperature: float = Field(0.3, ge=0.0, le=1.0)
    max_tokens: int = Field(2000, gt=100)


class SearchConfig(BaseModel):
    """Configuration for news search and retrieval."""
    max_results_per_topic: int = Field(20, ge=1, le=50)
    backend: str = Field("hybrid", description="'ddg_news', 'rss', or 'hybrid'")
    timeout_seconds: int = Field(15, ge=3, le=60)
    user_agent: str = Field(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )


class VoiceConfig(BaseModel):
    """Configuration for natural broadcast voice synthesis."""
    tts_voice: str = Field("en-US-AndrewMultilingualNeural", description="Microsoft Edge Neural Voice model")
    tts_rate: str = Field("+0%", description="Speech speed adjustment, e.g. '+5%'")
    tts_pitch: str = Field("+0Hz", description="Pitch adjustment")
    broadcast_style: bool = Field(True, description="Synthesize executive conversational briefing rather than flat text reading")
    enable_local_playback: bool = Field(True)


class UIConfig(BaseModel):
    """Configuration for UI display preferences."""
    # Default is 1 precise all-covering concise line
    view_mode: str = Field("compact", description="'compact' (1 precise all-covering line) or 'full' (1 line + 5-line analysis)")


class DateRange(BaseModel):
    """Date filtering bounds for news search and RAG."""
    start_date: str = Field(..., description="ISO format date (YYYY-MM-DD)")
    end_date: str = Field(..., description="ISO format date (YYYY-MM-DD)")


class AppConfig(BaseModel):
    """Root configuration object."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    topics: List[TopicConfig] = Field(default_factory=list)


class ConfigManager:
    """Manages reading, updating, saving, and format conversion (YAML / JSON) on configuration."""

    DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.default.yaml"
    USER_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.user.yaml"

    def __init__(self, config_path: Optional[str | Path] = None):
        self.config_path = Path(config_path) if config_path else self._resolve_config_path()
        self.config: AppConfig = self.load()

    def _resolve_config_path(self) -> Path:
        if self.USER_CONFIG_PATH.exists():
            return self.USER_CONFIG_PATH
        return self.DEFAULT_CONFIG_PATH

    def load(self) -> AppConfig:
        """Load configuration from YAML or JSON file."""
        path = self.config_path
        if not path.exists():
            path = self.DEFAULT_CONFIG_PATH

        if not path.exists():
            return AppConfig()

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if str(path).endswith(".json"):
            raw = json.loads(content) or {}
        else:
            raw = yaml.safe_load(content) or {}

        config = AppConfig(**raw)

        env_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if env_key and not config.llm.api_key:
            config.llm.api_key = env_key

        return config

    def get_formatted_config(self, fmt: str = "yaml") -> tuple[str, str]:
        """Get configuration formatted as YAML or JSON with path."""
        data = self.config.model_dump()
        target_path = self.config_path if self.config_path.exists() else self.DEFAULT_CONFIG_PATH

        if fmt.lower() == "json":
            return json.dumps(data, indent=2, ensure_ascii=False), str(target_path)
        else:
            return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True), str(target_path)

    def get_raw_yaml(self) -> tuple[str, str]:
        return self.get_formatted_config("yaml")

    def save_formatted_config(self, raw_content: str, fmt: str = "yaml") -> AppConfig:
        """Parse, validate, and persist configuration from YAML or JSON string."""
        if fmt.lower() == "json" or raw_content.strip().startswith("{"):
            parsed = json.loads(raw_content)
        else:
            parsed = yaml.safe_load(raw_content)

        if not isinstance(parsed, dict):
            raise ValueError("Configuration content must be a valid dictionary/object.")

        validated_config = AppConfig(**parsed)

        dest = self.config_path if self.config_path else self.USER_CONFIG_PATH
        dest.parent.mkdir(parents=True, exist_ok=True)

        with open(dest, "w", encoding="utf-8") as f:
            yaml.dump(validated_config.model_dump(), f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        self.config_path = dest
        self.config = validated_config
        return self.config

    def save_raw_yaml(self, raw_yaml_content: str) -> AppConfig:
        return self.save_formatted_config(raw_yaml_content, "yaml")

    def save(self, target_path: Optional[str | Path] = None) -> Path:
        """Save current configuration to user config file."""
        dest = Path(target_path) if target_path else (self.config_path if self.config_path else self.USER_CONFIG_PATH)
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = self.config.model_dump()
        with open(dest, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        self.config_path = dest
        return dest

    def get_topic(self, topic_id: str) -> Optional[TopicConfig]:
        for topic in self.config.topics:
            if topic.id == topic_id:
                return topic
        return None

    def find_topic(self, identifier: str) -> Optional[TopicConfig]:
        """Find topic by ID (exact or slug) or by title (case-insensitive fuzzy/contains)."""
        if not identifier:
            return None
        clean_id = identifier.strip().lower()
        # 1. Match exact ID
        for t in self.config.topics:
            if t.id.lower() == clean_id:
                return t
        # 2. Match exact or substring Title
        for t in self.config.topics:
            if clean_id in t.title.lower() or t.title.lower() in clean_id:
                return t
        # 3. Match in search queries
        for t in self.config.topics:
            if any(clean_id in q.lower() for q in t.search_queries):
                return t
        return None

    def upsert_topic(self, topic: TopicConfig) -> None:
        for i, t in enumerate(self.config.topics):
            if t.id == topic.id:
                self.config.topics[i] = topic
                self.save()
                return
        self.config.topics.append(topic)
        self.save()

    def delete_topic(self, topic_id: str) -> bool:
        initial_len = len(self.config.topics)
        self.config.topics = [t for t in self.config.topics if t.id != topic_id]
        if len(self.config.topics) < initial_len:
            self.save()
            return True
        return False

    def add_keywords_to_topic(self, topic_identifier: str, keywords: List[str]) -> Optional[TopicConfig]:
        """Append unique search keywords/queries to a topic and immediately persist to YAML."""
        topic = self.find_topic(topic_identifier)
        if not topic:
            return None

        clean_keywords = [k.strip() for k in keywords if k and k.strip()]
        existing_queries_lower = {q.lower() for q in topic.search_queries}

        added = False
        for kw in clean_keywords:
            if kw.lower() not in existing_queries_lower:
                topic.search_queries.append(kw)
                existing_queries_lower.add(kw.lower())
                added = True

        if added:
            self.upsert_topic(topic)
        return topic

    def remove_keyword_from_topic(self, topic_identifier: str, keyword: str) -> bool:
        """Remove a keyword/query from a topic and persist to YAML."""
        topic = self.find_topic(topic_identifier)
        if not topic:
            return False

        clean_kw = keyword.strip().lower()
        initial_len = len(topic.search_queries)
        topic.search_queries = [q for q in topic.search_queries if q.strip().lower() != clean_kw]

        if len(topic.search_queries) < initial_len:
            self.upsert_topic(topic)
            return True
        return False

    def quick_feed_keyword(self, keyword: str, topic_identifier: Optional[str] = None) -> tuple[TopicConfig, bool]:
        """Feed a keyword to an existing topic or auto-assign/create a topic, saving to YAML.
        Returns (TopicConfig, is_newly_created)."""
        clean_kw = keyword.strip()
        if not clean_kw:
            raise ValueError("Keyword cannot be empty")

        # If a target topic was specified, find or create it
        if topic_identifier:
            topic = self.find_topic(topic_identifier)
            if topic:
                self.add_keywords_to_topic(topic.id, [clean_kw])
                return topic, False

        # Try to find a matching topic automatically
        for t in self.config.topics:
            if any(clean_kw.lower() in q.lower() or q.lower() in clean_kw.lower() for q in t.search_queries):
                self.add_keywords_to_topic(t.id, [clean_kw])
                return t, False

        # If no matching topic, check if topic_identifier was given as a new title
        topic_title = topic_identifier if topic_identifier else f"Topic: {clean_kw.title()}"
        slug_id = re.sub(r"[^a-z0-9_]", "_", topic_title.lower()).strip("_")
        if not slug_id:
            slug_id = f"kw_{int(len(self.config.topics) + 1)}"

        # Create new topic
        new_topic = TopicConfig(
            id=slug_id,
            title=topic_title,
            icon="🎯",
            enabled=True,
            strategy_prompt=f"Focus on the latest strategic developments, breakthroughs, and analysis for {clean_kw}.",
            search_queries=[clean_kw]
        )
        self.upsert_topic(new_topic)
        return new_topic, True

    def update_llm_settings(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None
    ) -> None:
        if provider:
            self.config.llm.provider = provider
        if model:
            self.config.llm.model = model
        if api_key is not None:
            self.config.llm.api_key = api_key
        if api_base:
            if self.config.llm.provider == "local":
                self.config.llm.local_api_base = api_base
            else:
                self.config.llm.api_base = api_base
        self.save()
