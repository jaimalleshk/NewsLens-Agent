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

