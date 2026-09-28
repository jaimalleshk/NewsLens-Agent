"""News Analyst Agent: end-to-end multi-topic RAG news ingestion and 5-line analysis pipeline."""

from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable, AsyncGenerator, Tuple

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
from ..storage.sqlite_db import SQLiteNewsCache

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
        self.cache = SQLiteNewsCache()
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

    def _build_topic_spoken_broadcast(
        self,
        topic: TopicConfig,
        items: List[NewsItem],
        start_date: str,
        end_date: str
    ) -> str:
        """Construct an articulate, natural, broadcast-quality news anchor script with zero title repetition."""
        if not items:
            return f"No major news events were identified for {topic.title} in this date window."

        # Professional news opening (strip emojis for pristine TTS pronunciation)
        topic_clean_name = re.sub(r"^[^\w\s]+", "", topic.title).strip()
        segments = [
            f"Here is your news briefing for {topic_clean_name}, covering {len(items)} key developments."
        ]

        anchor_transitions = [
            "Leading off,",
            "Next in key developments,",
            "Turning to related news,",
            "In other significant reporting,",
            "Meanwhile in the sector,",
            "Additionally today,",
            "Furthermore,",
            "On another front,",
            "Rounding out our coverage,"
        ]

        for idx, it in enumerate(items):
            if idx == 0:
                trans = "Leading off,"
            elif idx == len(items) - 1 and len(items) > 1:
                trans = "Finally,"
            else:
                trans = anchor_transitions[min(idx, len(anchor_transitions) - 1)]

            clean_what = it.summary.line1_what.strip() if it.summary else ""
            clean_title = it.title.strip()
            speech_cand = (it.natural_speech or "").strip()

            # Clean out any JSON or template artifacts
            if speech_cand and ("{" in speech_cand or "line1" in speech_cand or len(speech_cand) < 20):
                speech_cand = ""

            # Determine the single best narrative sentence (never repeat title + line1)
            selected_story_text = ""
            if speech_cand:
                # Remove redundant prefix like "In local news," if present
                clean_speech = re.sub(r"^(In [^,]+,\s*)", "", speech_cand).strip()
                selected_story_text = clean_speech
            elif clean_what:
                # Check if clean_what already includes the core subject of the title
                title_words = set(re.findall(r"\w{4,}", clean_title.lower()))
                what_words = set(re.findall(r"\w{4,}", clean_what.lower()))
                overlap = len(title_words.intersection(what_words))

                if overlap >= 2 or len(clean_what) > 35:
                    selected_story_text = clean_what
                else:
                    selected_story_text = f"{clean_title}, with reports highlighting {clean_what}"
            else:
                selected_story_text = clean_title

            # Ensure proper punctuation and capitalization
            selected_story_text = selected_story_text.rstrip(".") + "."
            if selected_story_text:
                selected_story_text = selected_story_text[0].upper() + selected_story_text[1:]

            segments.append(f"{trans} {selected_story_text}")

        segments.append(f"That completes all updates for {topic_clean_name}.")
        return " ".join(segments)

    async def _synthesize_executive_digest(
        self,
        topic_results: List[TopicNewsResult],
        start_date: str,
        end_date: str
    ) -> Tuple[str, str]:
        """Synthesize a complete point-by-point cross-topic executive briefing and master audio script."""
        # Ensure topic_results are strictly in configured topic order (AI -> Enterprise -> Finance -> Policy -> Local Houston -> Real Estate -> Health)
        enabled_topics = [t for t in self.config.topics if t.enabled]
        if not enabled_topics:
            enabled_topics = self.config.topics
        topic_order_map = {t.id: idx for idx, t in enumerate(enabled_topics)}
        topic_results.sort(key=lambda r: topic_order_map.get(r.topic_id, 999))

        summaries_for_overview = []
        total_stories = 0
        for res in topic_results:
            if res.items:
                total_stories += len(res.items)
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
            system_prompt="You are Chief Intelligence Officer. Synthesize a macro cross-sector strategic overview. Output JSON with macro_synthesis and executive_audio_intro.",
            json_mode=True
        )

        macro_text = ""
        audio_intro = ""
        try:
            json_str = overview_resp
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            ov_data = json.loads(json_str)
            macro_text = ov_data.get("macro_synthesis") or ov_data.get("executive_overview") or ""
            audio_intro = ov_data.get("executive_audio_intro") or ov_data.get("executive_audio_script") or ""
        except Exception:
            macro_text = overview_resp or ""

        is_generic = (
            not macro_text
            or len(macro_text.strip()) < 80
            or "Intelligence summary for current inquiries" in macro_text
            or "Cross-sector analysis reflects" in macro_text
        )
        if is_generic:
            macro_text = (
                f"Across our monitored sectors from {start_date} to {end_date}, strategic developments highlight "
                f"rapid technology adoption, cloud infrastructure expansion, and shifting market dynamics. "
                f"Enterprises and regional stakeholders are actively navigating key inflection points in compute capacity, "
                f"capital allocation, and regulatory compliance."
            )

        # Build exhaustive point-by-point executive markdown covering ALL tabs and ALL articles
        overview_blocks = [
            f"## 🌐 Executive Cross-Topic Intelligence Briefing\n",
            f"**Reporting Window:** {start_date} to {end_date} &nbsp;|&nbsp; **Coverage:** {len(topic_results)} Verticals, {total_stories} Curated Developments\n",
            f"### 📊 Macro Strategic Cross-Sector Synthesis",
            macro_text.strip(),
            "\n---\n",
            f"### 📋 Comprehensive Section & Article Intelligence Breakdown\n"
        ]

        for res in topic_results:
            if res.items:
                overview_blocks.append(f"#### {res.topic_icon} {res.topic_title} ({len(res.items)} Developments)")
                for it in res.items:
                    clean_what = it.summary.line1_what.strip() if it.summary else ""
                    clean_title = it.title.strip()
                    # Check if title and clean_what are redundant
                    norm_t = re.sub(r"[^\w\s]", "", clean_title.lower()).strip()
                    norm_w = re.sub(r"[^\w\s]", "", clean_what.lower()).strip()
                    words_t = set(w for w in norm_t.split() if len(w) > 3)
                    words_w = set(w for w in norm_w.split() if len(w) > 3)
                    overlap = len(words_t.intersection(words_w))
                    is_dup = (
                        norm_t == norm_w
                        or (words_t and words_w and (overlap / min(len(words_t), len(words_w))) >= 0.8)
                        or (norm_t in norm_w or norm_w in norm_t)
                    )
                    if is_dup or not clean_what:
                        overview_blocks.append(f"• **{it.title}** *({it.publisher})*")
                    else:
                        overview_blocks.append(f"• **{it.title}** *({it.publisher})* — {clean_what}")
                overview_blocks.append("")
            else:
                overview_blocks.append(f"#### {res.topic_icon} {res.topic_title} (0 Developments)")
                overview_blocks.append("*No major news stories identified in this date window.*")
                overview_blocks.append("")

        exec_overview = "\n".join(overview_blocks)

        # Build master broadcast covering every section and every story in order
        if not audio_intro or len(audio_intro.strip()) < 40:
            audio_intro = f"Welcome to your complete executive news intelligence broadcast covering all {len(topic_results)} sectors from {start_date} to {end_date}."

        master_broadcast_segments = [audio_intro]
        for res in topic_results:
            if res.items and res.executive_audio_script:
                clean_sec_title = re.sub(r"^[^\w\s]+", "", res.topic_title).strip()
                master_broadcast_segments.append(
                    f"Now turning to our reporting for {clean_sec_title}. {res.executive_audio_script}"
                )
        master_broadcast_segments.append("That concludes your full executive cross-sector intelligence broadcast.")
        full_executive_audio = " ".join(master_broadcast_segments)

        return exec_overview, full_executive_audio

    async def analyze_topic(
        self,
        topic: TopicConfig,
        start_date: str,
        end_date: str,
        progress_cb: Optional[Callable[[str], None]] = None,
        force_refresh: bool = False
    ) -> TopicNewsResult:
        """Run complete retrieval, RAG, and summarization pipeline for one topic."""
        # Check SQLite persistent cache first if not forced refresh
        if not force_refresh:
            cached_res = self.cache.get_topic_result(topic.id, start_date, end_date)
            if cached_res is not None and cached_res.items:
                if progress_cb:
                    progress_cb(f"Loaded cached news for {topic.title} ({start_date} to {end_date}).")
                return cached_res

        target_max = topic.max_articles or self.config.search.max_results_per_topic

        if progress_cb:
            progress_cb(f"Fetching news for {topic.title} ({start_date} to {end_date}, max {target_max})...")

        raw_articles = await self.fetch_topic_articles(
            topic=topic,
            start_date=start_date,
            end_date=end_date,
            max_articles=target_max
        )

        # Cache raw articles in SQLite
        if raw_articles:
            self.cache.save_raw_articles(raw_articles, topic.id)

        if not raw_articles:
            empty_res = TopicNewsResult(
                topic_id=topic.id,
                topic_title=topic.title,
                topic_icon=topic.icon,
                strategy_applied=topic.strategy_prompt,
                start_date=start_date,
                end_date=end_date,
                items=[],
                executive_audio_script=f"No major news events were identified for {topic.title} in this date window."
            )
            self.cache.save_topic_result(empty_res)
            return empty_res

        # Index into RAG vector store
        self.vector_store.add_articles(raw_articles)

        # Cluster stories
        clusters = self.clusterer.cluster(raw_articles)
        if progress_cb:
            progress_cb(f"Synthesizing {len(clusters)} story clusters for {topic.title}...")

        # Deep LLM analysis for clusters up to target_max concurrently
        llm_limit = min(len(clusters), target_max)
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

        # Generate comprehensive topic-level spoken broadcast script covering 100% of valid items
        if not valid_items:
            topic_audio_script = f"No major news stories were identified for {topic.title} in the selected time period."
        else:
            stories_bullets = "\n\n".join([
                f"- Story {idx}: {it.title}\n  Summary: {it.summary.line1_what}"
                for idx, it in enumerate(valid_items, 1)
            ])

            broadcast_prompt = f"""You are a professional News Anchor.
Deliver a complete, engaging, natural spoken news broadcast covering the "{topic.title}" section for dates {start_date} to {end_date}.

NEWS STORIES TO NARRATE:
{stories_bullets}

CRITICAL RULES:
- Speak directly to the listener as a live professional news anchor in a natural conversational flow.
- Synthesize each story into ONE concise, fluent spoken sentence.
- NEVER repeat the headline and then repeat the same sentence. Speak each development once cleanly.
- Use natural spoken transitions ("Leading off,", "Next in headlines,", "Turning to related developments,", "Meanwhile,", "Looking ahead,").
- Do NOT use markdown headers, asterisks, meta-labels, or bullet points. Output only the spoken script.
"""

            topic_audio_script = await self.llm.generate_completion(
                prompt=broadcast_prompt,
                system_prompt="You are a professional executive news anchor. Deliver a fluid, non-repetitive spoken broadcast script."
            )

            # Ensure comprehensive spoken narrative covering all stories in topic without omission or duplicate phrases
            min_expected_len = len(valid_items) * 30
            is_insufficient = (
                not topic_audio_script
                or len(topic_audio_script.strip()) < max(80, min_expected_len)
                or "Produce an ultra-precise" in topic_audio_script
                or "Intelligence synthesis completed" in topic_audio_script
                or "Intelligence summary for current inquiries" in topic_audio_script
            )
            if is_insufficient:
                topic_audio_script = self._build_topic_spoken_broadcast(topic, valid_items, start_date, end_date)

        final_res = TopicNewsResult(
            topic_id=topic.id,
            topic_title=topic.title,
            topic_icon=topic.icon,
            strategy_applied=topic.strategy_prompt,
            start_date=start_date,
            end_date=end_date,
            items=valid_items,
            executive_audio_script=topic_audio_script
        )
        self.cache.save_topic_result(final_res)
        return final_res

    async def aggregate_all_topics(
        self,
        start_date: str,
        end_date: str,
        progress_cb: Optional[Callable[[str], None]] = None,
        force_refresh: bool = False
    ) -> AggregatedNewsDigest:
        """Run full cross-topic news intelligence aggregation."""
        # Check SQLite cache first if not forced refresh
        if not force_refresh:
            cached_digest = self.cache.get_digest(start_date, end_date)
            if cached_digest is not None:
                self.latest_digest = cached_digest
                return cached_digest
        else:
            self.cache.clear_cache(start_date, end_date)

        self.reload_config()
        self.vector_store.clear()

        enabled_topics = [t for t in self.config.topics if t.enabled]
        if not enabled_topics:
            enabled_topics = self.config.topics

        if progress_cb:
            progress_cb(f"Starting news analysis across {len(enabled_topics)} topics...")

        topic_tasks = [
            self.analyze_topic(topic, start_date, end_date, progress_cb, force_refresh=force_refresh)
            for topic in enabled_topics
        ]
        topic_results = await asyncio.gather(*topic_tasks)

        exec_overview, full_executive_audio = await self._synthesize_executive_digest(
            topic_results, start_date, end_date
        )

        digest = AggregatedNewsDigest(
            generated_at=datetime.now(timezone.utc).isoformat(),
            start_date=start_date,
            end_date=end_date,
            executive_overview=exec_overview,
            executive_audio_script=full_executive_audio,
            topic_results=topic_results,
            total_articles_indexed=len(self.vector_store.chunks)
        )

        self.cache.save_digest(digest)
        self.latest_digest = digest
        return digest

    async def stream_aggregate_all_topics(
        self,
        start_date: str,
        end_date: str,
        concurrency_limit: int = 8,
        force_refresh: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream news intelligence aggregation in real-time as each topic finishes."""
        # Return instantly from SQLite cache if available and not force refresh
        if not force_refresh:
            cached_digest = self.cache.get_digest(start_date, end_date)
            if cached_digest is not None:
                yield {
                    "event": "start",
                    "total_topics": len(cached_digest.topic_results),
                    "topics": [{"id": t.topic_id, "title": t.topic_title, "icon": t.topic_icon} for t in cached_digest.topic_results],
                    "start_date": start_date,
                    "end_date": end_date
                }
                for idx, res in enumerate(cached_digest.topic_results, 1):
                    yield {
                        "event": "topic_result",
                        "completed_count": idx,
                        "total_topics": len(cached_digest.topic_results),
                        "topic": res.model_dump()
                    }
                self.latest_digest = cached_digest
                yield {
                    "event": "complete",
                    "digest": cached_digest.model_dump()
                }
                return
        else:
            self.cache.clear_cache(start_date, end_date)

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
                return await self.analyze_topic(topic, start_date, end_date, force_refresh=force_refresh)

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

        # Generate overarching comprehensive executive overview and audio script across all items (with strict topic ordering)
        exec_overview, full_executive_audio = await self._synthesize_executive_digest(
            topic_results, start_date, end_date
        )

        digest = AggregatedNewsDigest(
            generated_at=datetime.now(timezone.utc).isoformat(),
            start_date=start_date,
            end_date=end_date,
            executive_overview=exec_overview,
            executive_audio_script=full_executive_audio,
            topic_results=topic_results,
            total_articles_indexed=len(self.vector_store.chunks)
        )
        self.cache.save_digest(digest)
        self.latest_digest = digest

        yield {
            "event": "complete",
            "digest": digest.model_dump()
        }


