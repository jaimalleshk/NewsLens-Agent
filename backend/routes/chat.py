"""Conversational Agent & Voice Command API routes."""

from fastapi import APIRouter
from news_agent_core import NewsAnalystAgent, AgentDialogueManager, ConfigManager
from ..schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["Agent Chat & Voice Command"])

config_mgr = ConfigManager()
agent = NewsAnalystAgent(config_manager=config_mgr)
dialogue = AgentDialogueManager(analyst=agent)


@router.post("", response_model=ChatResponse)
async def chat_with_agent(req: ChatRequest):
    """Process user conversational chat message or voice query."""
    start_d = req.start_date or "2026-09-01"
    end_d = req.end_date or "2026-09-27"

    resp = await dialogue.handle_user_message(
        user_input=req.message,
        current_start_date=start_d,
        current_end_date=end_d
    )

    return ChatResponse(
        reply=resp.reply,
        spoken_reply=resp.spoken_reply,
        intent_detected=resp.intent_detected,
        action_performed=resp.action_performed,
        config_mutated=resp.config_mutated,
        rag_sources=resp.rag_sources
    )
