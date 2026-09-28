"""API schemas for FastAPI backend."""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from news_agent_core.config import TopicConfig, LLMConfig, VoiceConfig, SearchConfig, UIConfig
from news_agent_core.search.base import AggregatedNewsDigest, TopicNewsResult, NewsItem


class AggregateRequest(BaseModel):
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    force_refresh: bool = False


class TopicNewsRequest(BaseModel):
    topic_id: str
    start_date: str
    end_date: str
    force_refresh: bool = False


class ChatRequest(BaseModel):
    message: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    spoken_reply: str
    intent_detected: str
    action_performed: Optional[str] = None
    config_mutated: bool = False
    rag_sources: List[Dict[str, str]] = []


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    llm: Optional[LLMConfig] = None
    voice: Optional[VoiceConfig] = None
    search: Optional[SearchConfig] = None
    ui: Optional[UIConfig] = None
    topics: Optional[List[TopicConfig]] = None


class RawYamlRequest(BaseModel):
    yaml: str


class RawYamlResponse(BaseModel):
    yaml: str
    path: str


class AddKeywordsRequest(BaseModel):
    keywords: List[str] = Field(..., description="List of search queries/keywords to append")


class RemoveKeywordRequest(BaseModel):
    keyword: str = Field(..., description="Keyword/query to remove")


class QuickAddKeywordRequest(BaseModel):
    keyword: str = Field(..., description="Keyword or search query")
    topic_id: Optional[str] = Field(None, description="Optional target topic ID or title")
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class LLMModelItem(BaseModel):
    id: str
    name: str
    description: str = ""
    recommended: bool = False
    context_length: Optional[str] = None


class LLMModelsResponse(BaseModel):
    provider: str
    models: List[LLMModelItem]
    detected_live: bool = False


class LLMTestConnectionRequest(BaseModel):
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    local_api_base: Optional[str] = None


class LLMTestConnectionResponse(BaseModel):
    status: str
    message: str
    latency_ms: Optional[float] = None
    sample_response: Optional[str] = None

