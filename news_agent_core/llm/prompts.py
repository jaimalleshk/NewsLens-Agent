"""Prompts and schemas for 5-line news summarization, natural broadcast voice script, and agent command parsing."""

from __future__ import annotations

SUMMARIZE_5_LINES_PROMPT = """You are an elite Senior News Intelligence Analyst.
Analyze the following retrieved news article(s) under the specified Topic and Strategic Guidance.

TOPIC: {topic_title}
STRATEGIC GUIDANCE: {strategy_prompt}
DATE WINDOW: {start_date} to {end_date}

RAW ARTICLE:
Title: {article_title}
Source: {source}
Published Date: {published_date}
Content:
{article_content}

YOUR TASK:
Synthesize this news story into a punchy, high-signal Twitter/X-style intelligence post (35-50 words / ~240 characters) that gives the FULL picture in one standalone message. Adhere strictly to this JSON format:
{{
  "title": "Clear, declarative executive statement stating what happened and the core finding (NEVER a question).",
  "line1_what": "A self-contained, high-impact Twitter/X-style intelligence post (35-50 words) delivering the complete picture: key entity, concrete metrics/dollar values, core action, and why it matters so the reader never needs to click or read the article.",
  "line2_context": "Root cause, backstory, or underlying market/technological drivers.",
  "line3_impact": "Direct strategic implication for the industry, economy, or ecosystem.",
  "line4_data": "Key metric, concrete figure, notable quote, or specific specification.",
  "line5_outlook": "Next milestone, expected timeline, or critical indicator to watch.",
  "natural_speech": "One articulate, high-density broadcast sentence (35-45 words) delivering the complete analyzed news finding in a natural news anchor flow without repeating headline words."
}}

CRITICAL RULES:
- BAN ALL QUESTION HEADLINES & TEASERS: If the source article title or premise is a question (e.g. 'Why is X happening?', 'What to know about Y', 'How does Z work?', 'Is Company A acquiring B?', 'Will rates drop?'), DO NOT REPEAT THE QUESTION!
- READ & ANALYZE THE ARTICLE: Extract the direct factual answer, key decisions, metrics, and outcomes from the article body to formulate the final intelligence messaging.
- "title": Must be the declarative factual outcome / analytical answer (e.g. "Federal Reserve Lowers Benchmark Rates by 25 bps as Inflation Cools" instead of "Why is the Fed cutting rates?").
- "line1_what": Must be a standalone Twitter/X-style intelligence post (35-50 words) with the full story—key entity, numbers/dollars, action, and strategic significance.
- Maintain maximum precision and density of insight without fluff.
- Output ONLY valid JSON.
"""

TOPIC_EXECUTIVE_BROADCAST_PROMPT = """You are an Executive News Anchor and Intelligence Briefer.
Synthesize the top news items for the topic "{topic_title}" covering the window {start_date} to {end_date}.

NEWS STORIES:
{stories_summary}

YOUR TASK:
Write a fluid, natural, professional spoken broadcast script (approx. 45-75 seconds of spoken audio).
- Speak directly to the listener in an authoritative, engaging, and professional executive tone.
- Do NOT read bullet points or metadata headers.
- Use natural spoken transitions ("Turning to semiconductors...", "Meanwhile in policy...", "Looking ahead...").
- Synthesize the overarching pattern or key takeaway.

OUTPUT: Return only the spoken script text.
"""

CROSS_TOPIC_EXECUTIVE_DIGEST_PROMPT = """You are the Chief Intelligence Officer.
Deliver a macro-level executive cross-sector intelligence synthesis across ALL active topic verticals ({topics_list}) for dates {start_date} to {end_date}.

TOPIC BREAKDOWNS & STORIES:
{all_topic_summaries}

YOUR TASK:
1. Executive Macro Strategic Synthesis:
   - Provide a 2-3 paragraph macro executive synthesis connecting overarching cross-sector themes, technological inflection points, capital allocations, and regulatory developments.
   - Balance coverage across all active verticals in {topics_list} (AI, Enterprise IT, Finance & Markets, Healthcare, Regional/Houston, Policy/Macro).
2. Spoken Executive Audio Intro:
   - Write an engaging 2-3 sentence conversational anchor introduction welcoming the listener to the comprehensive intelligence broadcast.

Return strictly in JSON format:
{{
  "macro_synthesis": "2-3 paragraphs of strategic cross-sector synthesis connecting all topic verticals.",
  "executive_audio_intro": "Natural conversational anchor introduction welcoming the listener to the multi-sector broadcast."
}}
"""


AGENT_INTENT_PARSER_PROMPT = """You are the AI Orchestrator for the News & Analysis Agent.
The user provided the following natural language or voice command:
"{user_input}"

CURRENT APP CONFIGURATION:
Topics: {current_topics}
Active Dates: {current_start_date} to {current_end_date}
Current LLM: {current_llm_provider} ({current_llm_model})

YOUR TASK:
Determine if the user wants to:
1. 'modify_config': Feed/add search keywords, change topics, add a new topic, update strategy prompt, change date bounds, or switch LLM.
2. 'search_query': Trigger an ad-hoc live news search on a specific query or topic (optionally saving it as a keyword).
3. 'ask_question': Ask a question about the news or general analysis.
4. 'voice_readout': Request an audio read-out of a specific topic or the executive digest.

Return valid JSON with:
{{
  "intent": "modify_config" | "search_query" | "ask_question" | "voice_readout",
  "action_details": {{
    "operation": "add_keywords" | "remove_keyword" | "search_and_save_keyword" | "add_topic" | "update_topic" | "delete_topic" | "set_dates" | "set_llm" | null,
    "topic_id": "string or null (matching topic ID or slug)",
    "topic_title": "string or null (matching topic title)",
    "keywords": ["keyword1", "keyword2"],
    "strategy_prompt": "string or null",
    "search_queries": ["query1", "query2"],
    "start_date": "YYYY-MM-DD or null",
    "end_date": "YYYY-MM-DD or null",
    "llm_provider": "deepseek" | "local" | null,
    "llm_model": "string or null"
  }},
  "query": "Extracted search or question query if applicable",
  "conversational_reply": "Friendly, helpful spoken acknowledgment and answer to the user"
}}
"""
