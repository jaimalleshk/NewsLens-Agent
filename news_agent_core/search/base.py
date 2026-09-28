"""Base data structures and abstract search interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class RawArticle(BaseModel):
    """Represents an ingested raw news article before summarization."""
    id: str = Field(..., description="Unique article hash")
    title: str = Field(..., description="Article headline")
    url: str = Field(..., description="Original publication URL")
    snippet: str = Field("", description="Short snippet or search excerpt")
    content: str = Field("", description="Extracted clean full text body")
    published_date: Optional[str] = Field(None, description="ISO date YYYY-MM-DD")
    source: str = Field("Web", description="Publisher or domain name")
    topic_id: Optional[str] = Field(None, description="Associated topic ID")
    score: float = Field(1.0, description="Relevance score")


class NewsSummary5Lines(BaseModel):
    """Strict 5-line executive impact breakdown."""
    line1_what: str = Field(..., description="Line 1: Core event, breakthrough, or announcement")
    line2_context: str = Field(..., description="Line 2: Context, underlying drivers, or background")
    line3_impact: str = Field(..., description="Line 3: Strategic, industry, or economic implications")
    line4_data: str = Field(..., description="Line 4: Key facts, metrics, figures, or notable quotes")
    line5_outlook: str = Field(..., description="Line 5: Next steps, forward milestone, or what to watch")

    def to_bullets(self) -> List[str]:
        return [
            f"• What: {self.line1_what}",
            f"• Context: {self.line2_context}",
            f"• Impact: {self.line3_impact}",
            f"• Key Data: {self.line4_data}",
            f"• Outlook: {self.line5_outlook}",
        ]


class NewsItem(BaseModel):
    """Synthesized, deduplicated news story with 5-line summary and natural speech script."""
    id: str = Field(..., description="Unique news event ID")
    title: str = Field(..., description="Clear, non-clickbait executive headline")
    url: str = Field(..., description="Direct primary source URL")
    additional_sources: List[Dict[str, str]] = Field(default_factory=list, description="Other outlet URLs covering this event")
    publisher: str = Field("News", description="Primary source name")
    published_date: str = Field(..., description="Date of occurrence/publication")
    topic_id: str = Field(..., description="Topic identifier")
    summary: NewsSummary5Lines = Field(..., description="Strict 5-line executive summary")
    natural_speech: Optional[str] = Field(None, description="Natural broadcast narrative script for executive voice readout")
    relevance_score: float = Field(1.0)


class TopicNewsResult(BaseModel):
    """Aggregated news collection for a specific dynamic tab/topic."""
    topic_id: str
    topic_title: str
    topic_icon: str
    strategy_applied: str
    start_date: str
    end_date: str
    items: List[NewsItem] = Field(default_factory=list)
    executive_audio_script: Optional[str] = Field(None, description="Cohesive audio broadcast script summarizing the entire topic")


class AggregatedNewsDigest(BaseModel):
    """Full news collection across all dynamic tabs with cross-topic executive summary."""
    generated_at: str
    start_date: str
    end_date: str
    executive_overview: str = Field(..., description="Cross-topic executive intelligence synthesis")
    executive_audio_script: str = Field(..., description="Complete conversational audio briefing script")
    topic_results: List[TopicNewsResult] = Field(default_factory=list)
    total_articles_indexed: int = 0


class BaseSearchEngine(ABC):
    """Abstract search provider interface."""

    @abstractmethod
    async def search(
        self,
        query: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_results: int = 5,
        topic_id: Optional[str] = None
    ) -> List[RawArticle]:
        pass
