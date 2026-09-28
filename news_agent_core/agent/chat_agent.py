"""Interactive conversational agent and voice command router for news intelligence."""

from __future__ import annotations
import json
import logging
import re
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from ..config import ConfigManager, TopicConfig, DateRange
from ..rag.vector_store import NewsVectorStore
from ..llm.client import UnifiedLLMClient
from ..llm.prompts import AGENT_INTENT_PARSER_PROMPT
from ..search.base import RawArticle
from .analyst import NewsAnalystAgent

logger = logging.getLogger(__name__)


class AgentChatResponse(BaseModel):
    """Result of conversational interaction with the News Agent."""
    reply: str
    spoken_reply: str
    intent_detected: str
    action_performed: Optional[str] = None
    config_mutated: bool = False
    rag_sources: List[Dict[str, str]] = Field(default_factory=list)
    suggested_followups: List[str] = Field(default_factory=list)


class AgentDialogueManager:
    """Manages chat and voice commands, dynamic configuration updates, and conversational RAG."""

    def __init__(self, analyst: NewsAnalystAgent):
        self.analyst = analyst
        self.config_manager = analyst.config_manager
        self.llm = analyst.llm
        self.vector_store = analyst.vector_store

    async def handle_user_message(
        self,
        user_input: str,
        current_start_date: str = "2026-09-01",
        current_end_date: str = "2026-09-27"
    ) -> AgentChatResponse:
        """Process user text or voice command, mutate configuration if requested, or answer questions via RAG."""
        user_input = user_input.strip()
        if not user_input:
            return AgentChatResponse(
                reply="How can I assist your news intelligence analysis today?",
                spoken_reply="How can I assist your news intelligence analysis today?",
                intent_detected="empty"
            )

        # 1. Parse intent using LLM
        current_topics_str = ", ".join([f"{t.title} (ID: {t.id})" for t in self.config_manager.config.topics])
        prompt = AGENT_INTENT_PARSER_PROMPT.format(
            user_input=user_input,
            current_topics=current_topics_str,
            current_start_date=current_start_date,
            current_end_date=current_end_date,
            current_llm_provider=self.config_manager.config.llm.provider,
            current_llm_model=self.config_manager.config.llm.model
        )

        resp = await self.llm.generate_completion(
            prompt=prompt,
            system_prompt="You are the News Intelligence Orchestrator. Output JSON.",
            json_mode=True
        )

        try:
            json_str = resp
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            parsed = json.loads(json_str)
        except Exception:
            parsed = {
                "intent": "ask_question",
                "action_details": {},
                "query": user_input,
                "conversational_reply": ""
            }

        intent = parsed.get("intent", "ask_question")
        action_details = parsed.get("action_details", {}) or {}
        operation = action_details.get("operation")
        conversational_reply = parsed.get("conversational_reply", "")

        # 2. Execute Configuration Mutation if requested
        config_mutated = False
        action_performed = None

        # 2. Execute Configuration Mutation if requested
        config_mutated = False
        action_performed = None

        # Check for direct keyword addition phrases as well
        lower_input = user_input.lower()
        is_add_keyword_phrase = any(p in lower_input for p in ["add keyword", "add keywords", "feed keyword", "track keyword", "save keyword", "add query"])
        
        if intent == "modify_config" or operation or is_add_keyword_phrase:
            if operation in ("add_keywords", "add_keyword", "save_keyword", "append_keywords") or is_add_keyword_phrase:
                target_topic_id = action_details.get("topic_id") or action_details.get("topic_title")
                raw_kws = action_details.get("keywords") or action_details.get("search_queries") or []
                
                # If LLM didn't extract keywords directly, parse from user_input
                if not raw_kws:
                    # e.g., "Add keyword DeepSeek V3 to Artificial Intelligence" or "Add keywords X, Y"
                    kw_match = re.search(
                        r"(?:add|track|feed|save)\s+(?:keywords?|query|queries)\s+[\"']?(.*?)(?:[\"']?\s+(?:to|in|under)\s+[\"']?([^\"']+)[\"']?)?$",
                        user_input,
                        re.IGNORECASE
                    )
                    if kw_match:
                        extracted_kw_str = kw_match.group(1).strip()
                        raw_kws = [k.strip().strip("\"'") for k in re.split(r"[,;]|\band\b", extracted_kw_str) if k.strip()]
                        if not target_topic_id and kw_match.group(2):
                            target_topic_id = kw_match.group(2).strip().strip("\"'")

                if not raw_kws and parsed.get("query"):
                    raw_kws = [parsed.get("query")]

                if not raw_kws:
                    raw_kws = [re.sub(r"^(?:add|feed|track|save)\s+(?:keywords?|queries|query)?", "", user_input, flags=re.IGNORECASE).strip()]
                
                raw_kws = [k for k in raw_kws if k]

                # Find or assign topic
                if target_topic_id:
                    updated_topic = self.config_manager.add_keywords_to_topic(target_topic_id, raw_kws)
                    if not updated_topic:
                        # Create topic with these keywords
                        updated_topic, _ = self.config_manager.quick_feed_keyword(raw_kws[0], topic_identifier=target_topic_id)
                        if len(raw_kws) > 1:
                            self.config_manager.add_keywords_to_topic(updated_topic.id, raw_kws[1:])
                else:
                    # Auto-assign or create
                    updated_topic, _ = self.config_manager.quick_feed_keyword(raw_kws[0])
                    if len(raw_kws) > 1:
                        self.config_manager.add_keywords_to_topic(updated_topic.id, raw_kws[1:])

                self.analyst.reload_config()
                config_mutated = True
                kw_list_str = ", ".join([f"`{k}`" for k in raw_kws])
                action_performed = f"Saved keywords {kw_list_str} to '{updated_topic.title}' in YAML"
                reply = f"✓ Saved keywords {kw_list_str} to **{updated_topic.title}** directly in `config.user.yaml`. Future ingests will monitor these terms."
                spoken = f"I have saved the new keywords {', '.join(raw_kws)} to topic {updated_topic.title} in your configuration."

            elif operation == "remove_keyword":
                target_topic_id = action_details.get("topic_id") or action_details.get("topic_title")
                kw_to_remove = (action_details.get("keywords") or [action_details.get("query") or ""])[0]
                if target_topic_id and kw_to_remove:
                    removed = self.config_manager.remove_keyword_from_topic(target_topic_id, kw_to_remove)
                    if removed:
                        self.analyst.reload_config()
                        config_mutated = True
                        action_performed = f"Removed keyword '{kw_to_remove}' from '{target_topic_id}' in YAML"
                        reply = f"Removed keyword `{kw_to_remove}` from topic in `config.user.yaml`."
                        spoken = f"Removed keyword {kw_to_remove} from your configuration."
                    else:
                        reply = f"Keyword `{kw_to_remove}` was not found in specified topic."
                        spoken = reply
                else:
                    reply = "Could not identify which keyword or topic to modify."
                    spoken = reply

            elif operation == "add_topic" or "add topic" in user_input.lower():
                title = action_details.get("topic_title") or "New Strategic Topic"
                t_id = action_details.get("topic_id") or re.sub(r"[^a-z0-9_]", "_", title.lower()).strip("_")
                strategy = action_details.get("strategy_prompt") or f"Focus on latest breakthroughs and strategic trends in {title}."
                queries = action_details.get("search_queries") or [title]

                new_topic = TopicConfig(
                    id=t_id,
                    title=title,
                    icon="🎯",
                    enabled=True,
                    strategy_prompt=strategy,
                    search_queries=queries
                )
                self.config_manager.upsert_topic(new_topic)
                self.analyst.reload_config()
                config_mutated = True
                action_performed = f"Added dynamic topic '{title}' (ID: {t_id}) to YAML"
                reply = f"I have added the new topic **{title}** with your custom strategy and saved it to `config.user.yaml`. Tabs and feeds are updated."
                spoken = f"I have added the new topic {title} to your intelligence feeds."

            elif operation == "update_topic":
                t_id = action_details.get("topic_id")
                topic = self.config_manager.find_topic(t_id) if t_id else None
                if topic:
                    if action_details.get("strategy_prompt"):
                        topic.strategy_prompt = action_details["strategy_prompt"]
                    if action_details.get("topic_title"):
                        topic.title = action_details["topic_title"]
                    if action_details.get("search_queries"):
                        topic.search_queries = action_details["search_queries"]
                    self.config_manager.upsert_topic(topic)
                    self.analyst.reload_config()
                    config_mutated = True
                    action_performed = f"Updated strategy for topic '{topic.title}' in YAML"
                    reply = f"Updated strategy for **{topic.title}** to: *{topic.strategy_prompt}* in `config.user.yaml`."
                    spoken = f"Updated strategic focus for {topic.title}."
                else:
                    reply = conversational_reply or "Topic not found to update."
                    spoken = reply

            elif operation == "delete_topic":
                t_id = action_details.get("topic_id")
                target = self.config_manager.find_topic(t_id) if t_id else None
                actual_id = target.id if target else t_id
                if actual_id and self.config_manager.delete_topic(actual_id):
                    self.analyst.reload_config()
                    config_mutated = True
                    action_performed = f"Deleted topic ID '{actual_id}' from YAML"
                    reply = f"Removed topic '{actual_id}' from `config.user.yaml`."
                    spoken = f"Removed topic from configuration."
                else:
                    reply = conversational_reply or "Could not find topic to remove."
                    spoken = reply

            elif operation == "set_llm":
                provider = action_details.get("llm_provider")
                model = action_details.get("llm_model")
                self.config_manager.update_llm_settings(provider=provider, model=model)
                self.analyst.reload_config()
                config_mutated = True
                action_performed = f"Switched LLM to {provider} ({model}) in YAML"
                reply = f"Switched LLM inference to **{provider.upper() if provider else ''}** ({model or 'default'}) in `config.user.yaml`."
                spoken = f"Switched model inference to {provider}."

            else:
                reply = conversational_reply or "Configuration updated in YAML."
                spoken = conversational_reply or "Configuration updated in YAML."

            return AgentChatResponse(
                reply=reply,
                spoken_reply=spoken,
                intent_detected="modify_config",
                action_performed=action_performed,
                config_mutated=config_mutated
            )

        # 3. Handle Question Answering / Ad-Hoc Live Search via RAG
        search_query = parsed.get("query") or user_input
        relevant_chunks = self.vector_store.search(
            query=search_query,
            start_date=current_start_date,
            end_date=current_end_date,
            top_k=4
        )

        # If no articles indexed yet for this query, perform an ad-hoc live search
        if not relevant_chunks:
            live_arts = await self.analyst.rss_search.search(
                query=search_query,
                start_date=current_start_date,
                end_date=current_end_date,
                max_results=4
            )
            if live_arts:
                self.vector_store.add_articles(live_arts)
                relevant_chunks = self.vector_store.search(
                    query=search_query,
                    start_date=current_start_date,
                    end_date=current_end_date,
                    top_k=4
                )

        rag_context = "\n\n".join([
            f"Source [{c.source}] ({c.published_date}):\nTitle: {c.title}\n{c.text}"
            for c in relevant_chunks
        ])

        qa_prompt = f"""You are the Executive Intelligence News Agent.
The user asked: "{user_input}"

RETRIEVED NEWS CONTEXT:
{rag_context if rag_context else "No prior articles indexed for this exact match. Provide concise domain intelligence."}

YOUR TASK:
Provide a precise, authoritative answer grounded in current news.
Structure:
- Direct, concise executive takeaway.
- Key details, supporting metrics, and cited facts.
- Conclude with a clear 1-2 sentence spoken summary suitable for executive voice briefing.
"""

        answer = await self.llm.generate_completion(
            prompt=qa_prompt,
            system_prompt="You are a senior news intelligence agent."
        )

        sources = [
            {"title": c.title, "url": c.url, "source": c.source}
            for c in relevant_chunks
        ]

        # Natural spoken version
        speech_script = conversational_reply or re.split(r"\n\n", answer)[0]
        speech_script = re.sub(r"[\*\#\-\_`]", "", speech_script).strip()
        if len(speech_script) < 30 and len(answer) > 30:
            speech_script = re.sub(r"[\*\#\-\_`]", "", answer[:250]).strip()

        return AgentChatResponse(
            reply=answer,
            spoken_reply=speech_script,
            intent_detected="ask_question",
            rag_sources=sources,
            suggested_followups=[
                "Summarize top risks in this sector",
                "Show primary source articles",
                "Add a custom strategy tab for this"
            ]
        )
