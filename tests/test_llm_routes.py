"""Tests for LLM configuration, model catalogue endpoints, and natural voice narrative synthesis."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.server import app
from news_agent_core.config import LLMConfig
from news_agent_core.llm.client import UnifiedLLMClient


@pytest.mark.asyncio
async def test_get_deepseek_models():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/config/llm/models?provider=deepseek")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "deepseek"
        model_ids = [m["id"] for m in data["models"]]
        assert "deepseek-chat" in model_ids
        assert "deepseek-reasoner" in model_ids
        chat_model = next(m for m in data["models"] if m["id"] == "deepseek-chat")
        assert chat_model["recommended"] is True


@pytest.mark.asyncio
async def test_get_local_models():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/config/llm/models?provider=local")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "local"
        assert len(data["models"]) >= 5
        model_ids = [m["id"] for m in data["models"]]
        assert "deepseek-r1:8b" in model_ids


@pytest.mark.asyncio
async def test_test_connection_missing_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/config/llm/test-connection",
            json={"provider": "deepseek", "model": "deepseek-chat", "api_key": ""}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "API key is missing" in data["message"]


@pytest.mark.asyncio
async def test_llm_client_broadcast_fallback_narration():
    config = LLMConfig(provider="local", model="deepseek-r1:8b", api_key="")
    client = UnifiedLLMClient(config)

    prompt = """You are a top-tier Executive News Broadcast Anchor.
Deliver a complete, comprehensive, and engaging spoken news broadcast covering the "Artificial Intelligence" section for dates 2026-09-20 to 2026-09-27.

NEWS STORIES TO NARRATE:
- Story 1: OpenAI Announces Breakthrough GPT-5 Architecture
  What: OpenAI released new model weights with advanced reasoning.
  Context: Enterprise adoption has surged across Fortune 500.
  Strategic Impact: Accelerates autonomous agent deployment.
  Data: 40% reduction in inference latency.
  Outlook: Commercial API rollout scheduled for next month.

- Story 2: Google Gemini Enterprise Update
  What: Google DeepMind unveils ultra-long context multimodal processing.
  Context: Cloud customers migrating large analytical workloads.
  Strategic Impact: Pressures existing proprietary models.
  Data: 2 million token context window.
  Outlook: General availability within two quarters.

REQUIREMENTS:
- Speak directly to the executive listener.
- Output only natural spoken narrative script.
"""

    result = await client.generate_completion(prompt=prompt)
    assert result is not None
    assert "Intelligence synthesis completed across" not in result
    assert "OpenAI" in result
    assert "Gemini" in result
    assert "Artificial Intelligence" in result
