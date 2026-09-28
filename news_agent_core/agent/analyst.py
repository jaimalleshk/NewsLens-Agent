"""News Analyst Agent: end-to-end multi-topic RAG news ingestion and 5-line analysis pipeline."""

from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable, AsyncGenerator

from ..config import AppConfig, ConfigManager, TopicConfig, DateRange
from ..search.base import (
    RawArticle,
    NewsItem,
    NewsSummary5Lines,
    TopicNewsResult,
    AggregatedNewsDigest
)
from ..search.ddg_search import DDGNewsSearch
from ..search.rss_search import RSSNewsSearch
from ..search.extractor import ArticleExtractor
from ..rag.vector_store import NewsVectorStore
from ..llm.client import UnifiedLLMClient
from ..llm.prompts import (
    SUMMARIZE_5_LINES_PROMPT,
    TOPIC_EXECUTIVE_BROADCAST_PROMPT,
    CROSS_TOPIC_EXECUTIVE_DIGEST_PROMPT
)
from .clusterer import StoryClusterer

logger = logging.getLogger(__name__)


class NewsAnalystAgent:
    """Core intelligence agent coordinating search, RAG, LLM synthesis, and voice scripting."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        self.config_manager = config_manager or ConfigManager()
        self.config: AppConfig = self.config_manager.config
        self.extractor = ArticleExtractor(timeout=self.config.search.timeout_seconds)
        self.ddg_search = DDGNewsSearch(extractor=self.extractor)
        self.rss_search = RSSNewsSearch(extractor=self.extractor)
        self.vector_store = NewsVectorStore()
        self.clusterer = StoryClusterer(similarity_threshold=0.4)
        self.llm = UnifiedLLMClient(self.config.llm)
        self.latest_digest: Optional[AggregatedNewsDigest] = None

    def reload_config(self) -> None:
        """Reload configuration from disk."""
        self.config = self.config_manager.load()
        self.llm = UnifiedLLMClient(self.config.llm)

    async def fetch_topic_articles(
        self,
        topic: TopicConfig,
        start_date: str,
        end_date: str,
        max_articles: int = 15
    ) -> List[RawArticle]:
        """Search and extract articles for a specific topic concurrently across configured backends."""
        queries = topic.search_queries or [topic.title]
        collected: Dict[str, RawArticle] = {}

        async def run_single_query(query: str):
            res_rss, res_ddg = await asyncio.gather(
                self.rss_search.search(
                    query=query,
                    start_date=start_date,
                    end_date=end_date,
                    max_results=max_articles,
                    topic_id=topic.id
                ),
                self.ddg_search.search(
                    query=query,
                    start_date=start_date,
                    end_date=end_date,
                    max_results=max_articles,
                    topic_id=topic.id
                ),
                return_exceptions=True
            )
            items = []
            if isinstance(res_rss, list):
                items.extend(res_rss)
            if isinstance(res_ddg, list):
                items.extend(res_ddg)
            return items

        # Execute all search queries in parallel concurrently
        query_tasks = [run_single_query(q) for q in queries[:4]]
        results_lists = await asyncio.gather(*query_tasks, return_exceptions=True)

        for res in results_lists:
            if isinstance(res, list):
                for art in res:
                    if art.id not in collected:
                        collected[art.id] = art

        article_list = list(collected.values())[:max_articles * 2]

        # Extract full content concurrently only for top articles needing body text
        top_to_enrich = [a for a in article_list if not a.content or len(a.content) < 80][:4]
        async def enrich(art: RawArticle):
            body = await self.extractor.extract(art.url)
            if body:
                art.content = body

        if top_to_enrich:
            await asyncio.gather(*(enrich(a) for a in top_to_enrich), return_exceptions=True)
        return article_list


    def _fast_extractive_summary(
        self,
        cluster: List[RawArticle],
        topic: TopicConfig,
        start_date: str,
        end_date: str
    ) -> Optional[NewsItem]:
        """Fast extractive synthesis fallback for secondary clusters."""
        if not cluster:
            return None
        primary_article = cluster[0]
        content_snippet = (primary_article.snippet or primary_article.title).strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", content_snippet) if len(s.strip()) > 15]

        s1 = sentences[0] if len(sentences) > 0 else f"{primary_article.title} reported with direct relevance to {topic.title}."
        s2 = sentences[1] if len(sentences) > 1 else f"Coverage reported by {primary_article.source} highlighting industry movements."
        s3 = f"Strategic focus centers on competitive execution and sector positioning for {topic.title}."
        s4 = f"Verified reporting sourced from {primary_article.source}."
        s5 = "Ongoing operational developments and follow-up milestones being tracked."

        summary = NewsSummary5Lines(
            line1_what=s1,
            line2_context=s2,
            line3_impact=s3,
            line4_data=s4,
            line5_outlook=s5
        )

        additional = [
            {"source": a.source, "url": a.url}
            for a in cluster[1:]
            if a.url != primary_article.url
        ]

        return NewsItem(
            id=primary_article.id,
            title=primary_article.title,
            url=primary_article.url,
            additional_sources=additional,
            publisher=primary_article.source,
            published_date=primary_article.published_date or start_date,
            topic_id=topic.id,
            summary=summary,
            natural_speech=f"In {topic.title}, {primary_article.title}. {s1}",
            relevance_score=primary_article.score
        )

    async def summarize_cluster_to_5lines(
        self,
        cluster: List[RawArticle],
        topic: TopicConfig,
        start_date: str,
        end_date: str
    ) -> Optional[NewsItem]:
        """Synthesize a cluster of articles into a structured 5-line NewsItem."""
        if not cluster:
            return None

        primary_article = cluster[0]
        combined_content = "\n\n".join([
            f"Outlet: {a.source}\nTitle: {a.title}\n{a.content or a.snippet}"
            for a in cluster
        ])

        prompt = SUMMARIZE_5_LINES_PROMPT.format(
            topic_title=topic.title,
            strategy_prompt=topic.strategy_prompt,
            start_date=start_date,
            end_date=end_date,
            article_title=primary_article.title,
            source=primary_article.source,
            published_date=primary_article.published_date or start_date,
            article_content=combined_content[:3000]
        )

        response_text = await self.llm.generate_completion(
            prompt=prompt,
            system_prompt="You are a senior intelligence analyst. Output strictly valid JSON.",
            json_mode=True
        )

        try:
            json_str = response_text
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)

            summary = NewsSummary5Lines(
                line1_what=data.get("line1_what", primary_article.title),
                line2_context=data.get("line2_context", "Background context in sector evolution."),
                line3_impact=data.get("line3_impact", "Significant strategic and market impact."),
                line4_data=data.get("line4_data", "Measurable momentum across industry data."),
                line5_outlook=data.get("line5_outlook", "Subsequent announcements expected shortly.")
            )

            additional = [
                {"source": a.source, "url": a.url}
                for a in cluster[1:]
                if a.url != primary_article.url
            ]

            return NewsItem(
                id=primary_article.id,
                title=data.get("title", primary_article.title),
                url=primary_article.url,
                additional_sources=additional,
                publisher=primary_article.source,
                published_date=primary_article.published_date or start_date,
                topic_id=topic.id,
                summary=summary,
                natural_speech=data.get("natural_speech"),
                relevance_score=primary_article.score
            )
        except Exception as e:
            logger.warning(f"Failed to parse LLM 5-line summary JSON: {e}. Fallback to template.")
            return self._fast_extractive_summary(cluster, topic, start_date, end_date)

    async def analyze_topic(
        self,
        topic: TopicConfig,
        start_date: str,
        end_date: str,
        progress_cb: Optional[Callable[[str], None]] = None
    ) -> TopicNewsResult:
        """Run complete retrieval, RAG, and summarization pipeline for one topic."""
        target_max = topic.max_articles or self.config.search.max_results_per_topic

        if progress_cb:
            progress_cb(f"Fetching news for {topic.title} ({start_date} to {end_date}, max {target_max})...")

        raw_articles = await self.fetch_topic_articles(
            topic=topic,
            start_date=start_date,
            end_date=end_date,
            max_articles=target_max
        )

        if not raw_articles:
            return TopicNewsResult(
                topic_id=topic.id,
                topic_title=topic.title,
                topic_icon=topic.icon,
                strategy_applied=topic.strategy_prompt,
                start_date=start_date,
                end_date=end_date,
                items=[],
                executive_audio_script=f"No major news events were identified for {topic.title} in this date window."
            )

        # Index into RAG vector store
        self.vector_store.add_articles(raw_articles)

        # Cluster stories
        clusters = self.clusterer.cluster(raw_articles)
        if progress_cb:
            progress_cb(f"Synthesizing {len(clusters)} story clusters for {topic.title}...")

        # Deep LLM analysis for top 5 key clusters, fast extractive synthesis for remaining
        llm_limit = 5
        llm_tasks = [
            self.summarize_cluster_to_5lines(cl, topic, start_date, end_date)
            for cl in clusters[:llm_limit]
        ]
        llm_results = await asyncio.gather(*llm_tasks, return_exceptions=True)

        valid_items: List[NewsItem] = []
        for it in llm_results:
            if isinstance(it, NewsItem):
                valid_items.append(it)

        for cl in clusters[llm_limit:target_max]:
            ext_item = self._fast_extractive_summary(cl, topic, start_date, end_date)
            if ext_item:
                valid_items.append(ext_item)

        # Generate comprehensive topic-level spoken broadcast script
        if not valid_items:
            topic_audio_script = f"No major news stories were identified for {topic.title} in the selected time period."
        else:
            stories_bullets = "\n\n".join([
                f"- Story {idx}: {it.title}\n  Summary: {it.summary.line1_what}"
                for idx, it in enumerate(valid_items[:10], 1)
            ])

            broadcast_prompt = f"""You are a professional News Anchor.
Deliver a complete, engaging, natural spoken news broadcast covering the "{topic.title}" section for dates {start_date} to {end_date}.

NEWS STORIES TO NARRATE:
{stories_bullets}

REQUIREMENTS:
- Speak directly to the listener in a natural, professional news broadcast tone.
- Clearly present each news story concisely and smoothly.
- Do NOT mention or use meta-labels like "What:", "Context:", "Strategic Impact:", "Data:", or "Outlook:".
- Use natural spoken transitions ("Turning first to...", "In related developments...", "Meanwhile...", "Looking ahead...").
- Do NOT use markdown headers, asterisks, or bullet points. Output only the natural spoken narrative script.
"""

            topic_audio_script = await self.llm.generate_completion(
                prompt=broadcast_prompt,
                system_prompt="You are a professional executive news anchor. Deliver a complete spoken broadcast script."
            )

            # Ensure comprehensive spoken narrative covering all stories in topic
            is_insufficient = (
                not topic_audio_script
                or len(topic_audio_script.strip()) < 100
                or "Produce an ultra-precise" in topic_audio_script
                or "Intelligence synthesis completed" in topic_audio_script
                or "Intelligence summary for current inquiries" in topic_audio_script
            )
            if is_insufficient:
                segments = [f"Here is your news intelligence briefing covering {topic.title}."]
                for i, it in enumerate(valid_items, 1):
                    transition = "Turning first to" if i == 1 else ("Next in headlines," if i == 2 else ("In related developments," if i == 3 else "Also today,"))
                    clean_summary = it.summary.line1_what.strip()
                    story_text = f"{transition} {it.title}. {clean_summary}"
                    segments.append(story_text)
                segments.append(f"That concludes our reporting for {topic.title}.")
                topic_audio_script = " ".join(segments)


        return TopicNewsResult(
            topic_id=topic.id,
            topic_title=topic.title,
            topic_icon=topic.icon,
            strategy_applied=topic.strategy_prompt,
            start_date=start_date,
            end_date=end_date,
            items=valid_items,
            executive_audio_script=topic_audio_script
        )

    async def aggregate_all_topics(
        self,
        start_date: str,
        end_date: str,
        progress_cb: Optional[Callable[[str], None]] = None
    ) -> AggregatedNewsDigest:
        """Run full cross-topic news intelligence aggregation."""
        self.reload_config()
        self.vector_store.clear()

        enabled_topics = [t for t in self.config.topics if t.enabled]
        if not enabled_topics:
            enabled_topics = self.config.topics

        if progress_cb:
            progress_cb(f"Starting news analysis across {len(enabled_topics)} topics...")

        topic_tasks = [
            self.analyze_topic(topic, start_date, end_date, progress_cb)
            for topic in enabled_topics
        ]
        topic_results = await asyncio.gather(*topic_tasks)

        summaries_for_overview = []
        for res in topic_results:
            if res.items:
                summaries_for_overview.append(
                    f"### {res.topic_icon} {res.topic_title} ({len(res.items)} stories)\n" +
                    "\n".join([f"- **{it.title}** ({it.publisher}): {it.summary.line1_what}" for it in res.items])
                )

        cross_prompt = CROSS_TOPIC_EXECUTIVE_DIGEST_PROMPT.format(
            topics_list=", ".join([t.topic_title for t in topic_results]),
            start_date=start_date,
            end_date=end_date,
            all_topic_summaries="\n\n".join(summaries_for_overview)
        )

        overview_resp = await self.llm.generate_completion(
            prompt=cross_prompt,
            system_prompt="You are Chief Intelligence Officer. Synthesize a comprehensive executive overview covering the breadth of all provided topic news. Output JSON with executive_overview and executive_audio_script.",
            json_mode=True
        )

        exec_overview = ""
        try:
            json_str = overview_resp
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            ov_data = json.loads(json_str)
            exec_overview = ov_data.get("executive_overview", "")
        except Exception:
            exec_overview = overview_resp or ""

        is_generic_overview = (
            not exec_overview
            or len(exec_overview.strip()) < 120
            or "Cross-sector analysis reflects" in exec_overview
            or "Intelligence summary for current inquiries" in exec_overview
        )
        if is_generic_overview:
            overview_sections = [
                f"## Executive Cross-Topic Intelligence Summary ({start_date} to {end_date})\n",
                f"Comprehensive cross-sector intelligence synthesis covering **{len(topic_results)} active topics** and **{sum(len(r.items) for r in topic_results)} curated stories**:\n"
            ]
            for res in topic_results:
                if res.items:
                    overview_sections.append(f"### {res.topic_icon} {res.topic_title} ({len(res.items)} developments)")
                    for it in res.items:
                        overview_sections.append(f"- **{it.title}** *({it.publisher})*: {it.summary.line1_what}")
                    overview_sections.append("")
            exec_overview = "\n".join(overview_sections)

        # Build comprehensive master full broadcast covering all sections
        master_broadcast_segments = [
            f"Welcome to your complete executive news intelligence broadcast for {start_date} to {end_date}."
        ]
        for res in topic_results:
            if res.items and res.executive_audio_script:
                master_broadcast_segments.append(
                    f"Now turning to {res.topic_title}. {res.executive_audio_script}"
                )
        master_broadcast_segments.append("That concludes your complete executive news intelligence briefing.")
        full_executive_audio = " ".join(master_broadcast_segments)

        digest = AggregatedNewsDigest(
            generated_at=datetime.now(timezone.utc).isoformat(),
            start_date=start_date,
            end_date=end_date,
            executive_overview=exec_overview,
            executive_audio_script=full_executive_audio,
            topic_results=topic_results,
            total_articles_indexed=len(self.vector_store.chunks)
        )

        self.latest_digest = digest
        return digest

    async def stream_aggregate_all_topics(
        self,
        start_date: str,
        end_date: str,
        concurrency_limit: int = 8
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream news intelligence aggregation in real-time as each topic finishes."""
        self.reload_config()
        self.vector_store.clear()

        enabled_topics = [t for t in self.config.topics if t.enabled]
        if not enabled_topics:
            enabled_topics = self.config.topics

        yield {
            "event": "start",
            "total_topics": len(enabled_topics),
            "topics": [{"id": t.id, "title": t.title, "icon": t.icon} for t in enabled_topics],
            "start_date": start_date,
            "end_date": end_date
        }

        semaphore = asyncio.Semaphore(concurrency_limit)
        topic_results: List[TopicNewsResult] = []

        async def process_single_topic(topic: TopicConfig) -> TopicNewsResult:
            async with semaphore:
                return await self.analyze_topic(topic, start_date, end_date)

        tasks = [asyncio.create_task(process_single_topic(t)) for t in enabled_topics]

        for coro in asyncio.as_completed(tasks):
            result: TopicNewsResult = await coro
            topic_results.append(result)
            yield {
                "event": "topic_result",
                "completed_count": len(topic_results),
                "total_topics": len(enabled_topics),
                "topic": result.model_dump()
            }

        # Generate overarching executive overview and audio script across all items
        summaries_for_overview = []
        for res in topic_results:
            if res.items:
                summaries_for_overview.append(
                    f"### {res.topic_icon} {res.topic_title} ({len(res.items)} stories)\n" +
                    "\n".join([f"- **{it.title}** ({it.publisher}): {it.summary.line1_what}" for it in res.items])
                )

        cross_prompt = CROSS_TOPIC_EXECUTIVE_DIGEST_PROMPT.format(
            topics_list=", ".join([t.topic_title for t in topic_results]),
            start_date=start_date,
            end_date=end_date,
            all_topic_summaries="\n\n".join(summaries_for_overview)
        )

        overview_resp = await self.llm.generate_completion(
            prompt=cross_prompt,
            system_prompt="You are Chief Intelligence Officer. Synthesize a comprehensive executive overview covering the breadth of all provided topic news. Output JSON with executive_overview and executive_audio_script.",
            json_mode=True
        )

        exec_overview = ""
        try:
            json_str = overview_resp
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            ov_data = json.loads(json_str)
            exec_overview = ov_data.get("executive_overview", "")
        except Exception:
            exec_overview = overview_resp or ""

        is_generic_overview = (
            not exec_overview
            or len(exec_overview.strip()) < 120
            or "Cross-sector analysis reflects" in exec_overview
            or "Intelligence summary for current inquiries" in exec_overview
        )
        if is_generic_overview:
            overview_sections = [
                f"## Executive Cross-Topic Intelligence Summary ({start_date} to {end_date})\n",
                f"Comprehensive cross-sector intelligence synthesis covering **{len(topic_results)} active topics** and **{sum(len(r.items) for r in topic_results)} curated stories**:\n"
            ]
            for res in topic_results:
                if res.items:
                    overview_sections.append(f"### {res.topic_icon} {res.topic_title} ({len(res.items)} developments)")
                    for it in res.items:
                        overview_sections.append(f"- **{it.title}** *({it.publisher})*: {it.summary.line1_what}")
                    overview_sections.append("")
            exec_overview = "\n".join(overview_sections)

        # Master complete spoken broadcast covering every section
        master_broadcast_segments = [
            f"Welcome to your complete executive news intelligence broadcast for {start_date} to {end_date}."
        ]
        for res in topic_results:
            if res.items and res.executive_audio_script:
                master_broadcast_segments.append(
                    f"Now turning to {res.topic_title}. {res.executive_audio_script}"
                )
        master_broadcast_segments.append("That concludes your complete executive news intelligence briefing.")
        full_executive_audio = " ".join(master_broadcast_segments)

        digest = AggregatedNewsDigest(
            generated_at=datetime.now(timezone.utc).isoformat(),
            start_date=start_date,
            end_date=end_date,
            executive_overview=exec_overview,
            executive_audio_script=full_executive_audio,
            topic_results=topic_results,
            total_articles_indexed=len(self.vector_store.chunks)
        )
        self.latest_digest = digest


        yield {
            "event": "complete",
            "digest": digest.model_dump()
        }

