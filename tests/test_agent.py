"""Integration test for NewsAnalystAgent and AgentDialogueManager."""

import pytest
import asyncio
from news_agent_core.agent.analyst import NewsAnalystAgent
from news_agent_core.agent.chat_agent import AgentDialogueManager
from news_agent_core.config import ConfigManager, TopicConfig


@pytest.mark.asyncio
async def test_agent_topic_analysis():
    config_mgr = ConfigManager()
    agent = NewsAnalystAgent(config_manager=config_mgr)

    test_topic = TopicConfig(
        id="test_ai",
        title="AI Technology",
        strategy_prompt="Focus on foundational model improvements and efficient inference.",
        search_queries=["artificial intelligence models release"]
    )

    result = await agent.analyze_topic(test_topic, start_date="2026-09-01", end_date="2026-09-27")
    assert result.topic_id == "test_ai"
    assert result.topic_title == "AI Technology"


@pytest.mark.asyncio
async def test_dialogue_manager_command():
    config_mgr = ConfigManager()
    agent = NewsAnalystAgent(config_manager=config_mgr)
    dialogue = AgentDialogueManager(analyst=agent)

    # Test conversational command
    resp = await dialogue.handle_user_message(
        user_input="Add a topic called Robotics with strategy focus on humanoid robots and actuators",
        current_start_date="2026-09-01",
        current_end_date="2026-09-27"
    )

    assert resp is not None
    assert len(resp.reply) > 0
    assert resp.spoken_reply is not None


@pytest.mark.asyncio
async def test_dialogue_add_keyword(tmp_path):
    config_file = tmp_path / "test_chat_kw_config.yaml"
    config_mgr = ConfigManager(config_path=config_file)
    
    # Initialize with AI topic
    ai_topic = TopicConfig(
        id="artificial_intelligence",
        title="Artificial Intelligence",
        strategy_prompt="Focus on AI breakthroughs",
        search_queries=["OpenAI", "Google Gemini"]
    )
    config_mgr.upsert_topic(ai_topic)

    agent = NewsAnalystAgent(config_manager=config_mgr)
    dialogue = AgentDialogueManager(analyst=agent)

    # Test conversational keyword feeding
    resp = await dialogue.handle_user_message(
        user_input="Add keywords DeepSeek V3, Qwen 2.5 to Artificial Intelligence",
        current_start_date="2026-09-01",
        current_end_date="2026-09-27"
    )

    assert resp is not None
    assert resp.config_mutated is True
    assert "DeepSeek V3" in resp.reply or "DeepSeek V3" in str(resp.action_performed)

    # Verify topic in config has the new keywords
    updated_ai = config_mgr.get_topic("artificial_intelligence")
    assert any("DeepSeek" in q for q in updated_ai.search_queries)


@pytest.mark.asyncio
async def test_full_coverage_executive_digest_and_spoken_broadcast():
    from news_agent_core.search.base import NewsItem, NewsSummary5Lines, TopicNewsResult

    config_mgr = ConfigManager()
    agent = NewsAnalystAgent(config_manager=config_mgr)

    # Mock topic results across 2 verticals with multiple articles
    item1 = NewsItem(
        id="a1",
        title="NVIDIA Unveils Next-Gen Blackwell Ultra Chips",
        url="https://example.com/a1",
        publisher="Reuters",
        published_date="2026-09-27",
        topic_id="ai_tech",
        summary=NewsSummary5Lines(
            line1_what="NVIDIA announced its updated Blackwell Ultra AI accelerator lineup with double memory capacity.",
            line2_context="High demand from cloud hyper-scalers continues.",
            line3_impact="Accelerates foundation model inference speeds.",
            line4_data="288GB HBM3e memory per package.",
            line5_outlook="Sampling begins next quarter."
        ),
        natural_speech="NVIDIA has announced its updated Blackwell Ultra lineup featuring doubled memory capacity for cloud hyper-scalers."
    )
    item2 = NewsItem(
        id="a2",
        title="OpenAI Releases Open Source Model Distillations",
        url="https://example.com/a2",
        publisher="TechCrunch",
        published_date="2026-09-27",
        topic_id="ai_tech",
        summary=NewsSummary5Lines(
            line1_what="OpenAI released open-weights distillations of frontier reasoning models.",
            line2_context="Developer ecosystem demand for low-latency edge deployment.",
            line3_impact="Broadens enterprise on-premise AI deployments.",
            line4_data="Models range from 1.5B to 14B parameters.",
            line5_outlook="Community fine-tunes expected within days."
        ),
        natural_speech="In developer news, OpenAI has released open weights distillations of its reasoning models."
    )

    item3 = NewsItem(
        id="f1",
        title="Federal Reserve Signals Measured Easing Path",
        url="https://example.com/f1",
        publisher="Bloomberg",
        published_date="2026-09-27",
        topic_id="finance",
        summary=NewsSummary5Lines(
            line1_what="Central bank officials projected steady rate cuts following stable inflation prints.",
            line2_context="Labor market indicators show balanced normalization.",
            line3_impact="Lowers debt financing costs for corporate borrowing.",
            line4_data="Target benchmark reduced by 25 basis points.",
            line5_outlook="Next policy meeting scheduled for November."
        ),
        natural_speech="The Federal Reserve has indicated a steady pace of interest rate reductions as inflation numbers stabilize."
    )

    topic1 = TopicConfig(id="ai_tech", title="AI Technology", icon="🤖", strategy_prompt="Focus on AI innovation")
    topic2 = TopicConfig(id="finance", title="Finance & Markets", icon="📈", strategy_prompt="Focus on macro finance")

    # Test topic broadcast generation covering 100% of items
    script_ai = agent._build_topic_spoken_broadcast(topic1, [item1, item2], "2026-09-20", "2026-09-27")
    assert "NVIDIA" in script_ai
    assert "OpenAI" in script_ai
    assert "Here is your news briefing for AI Technology" in script_ai
    assert "That completes all updates for AI Technology" in script_ai

    # Test master executive digest synthesis
    res1 = TopicNewsResult(
        topic_id=topic1.id,
        topic_title=topic1.title,
        topic_icon=topic1.icon,
        strategy_applied="AI focus",
        start_date="2026-09-20",
        end_date="2026-09-27",
        items=[item1, item2],
        executive_audio_script=script_ai
    )
    script_fin = agent._build_topic_spoken_broadcast(topic2, [item3], "2026-09-20", "2026-09-27")
    res2 = TopicNewsResult(
        topic_id=topic2.id,
        topic_title=topic2.title,
        topic_icon=topic2.icon,
        strategy_applied="Finance focus",
        start_date="2026-09-20",
        end_date="2026-09-27",
        items=[item3],
        executive_audio_script=script_fin
    )

    overview_md, master_audio = await agent._synthesize_executive_digest([res1, res2], "2026-09-20", "2026-09-27")

    # Verify 100% topic and article coverage in Executive Overview markdown
    assert "## 🌐 Executive Cross-Topic Intelligence Briefing" in overview_md
    assert "### 📊 Macro Strategic Cross-Sector Synthesis" in overview_md
    assert "#### 🤖 AI Technology (2 Developments)" in overview_md
    assert "NVIDIA Unveils Next-Gen Blackwell Ultra Chips" in overview_md
    assert "Reuters" in overview_md
    assert "OpenAI Releases Open Source Model Distillations" in overview_md
    assert "TechCrunch" in overview_md
    assert "#### 📈 Finance & Markets (1 Developments)" in overview_md
    assert "Federal Reserve Signals Measured Easing Path" in overview_md
    assert "Bloomberg" in overview_md

    # Verify Master Spoken Broadcast covers both topics and all stories
    assert "AI Technology" in master_audio
    assert "NVIDIA" in master_audio
    assert "OpenAI" in master_audio
    assert "Finance & Markets" in master_audio
    assert "Federal Reserve" in master_audio


