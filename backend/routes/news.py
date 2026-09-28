import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from news_agent_core import NewsAnalystAgent, ConfigManager
from ..schemas import AggregateRequest, TopicNewsRequest

router = APIRouter(prefix="/api/news", tags=["News"])

config_mgr = ConfigManager()
agent = NewsAnalystAgent(config_manager=config_mgr)


@router.get("/stream")
@router.post("/stream")
async def stream_news(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD")
):
    """Stream news intelligence aggregation in real-time as each topic completes."""
    async def event_generator():
        async for event in agent.stream_aggregate_all_topics(start_date, end_date):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/aggregate")
async def aggregate_all(req: AggregateRequest):
    """Run full news aggregation for active topics within date range."""
    digest = await agent.aggregate_all_topics(req.start_date, req.end_date)
    return digest


@router.post("/topic")
async def get_topic_news(req: TopicNewsRequest):
    """Fetch and synthesize news for a specific topic."""
    topic = config_mgr.get_topic(req.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    result = await agent.analyze_topic(topic, req.start_date, req.end_date)
    return result


@router.get("/latest")
async def get_latest_digest():
    """Get the cached latest digest if available."""
    if not agent.latest_digest:
        raise HTTPException(status_code=404, detail="No digest generated yet")
    return agent.latest_digest
