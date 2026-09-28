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
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
    force_refresh: bool = Query(False, description="Force live news refresh bypassing local SQLite cache")
):
    """Stream news intelligence aggregation in real-time as each topic completes."""
    async def event_generator():
        async for event in agent.stream_aggregate_all_topics(start_date, end_date, force_refresh=force_refresh):
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
    digest = await agent.aggregate_all_topics(req.start_date, req.end_date, force_refresh=req.force_refresh)
    return digest


@router.post("/topic")
async def get_topic_news(req: TopicNewsRequest):
    """Fetch and synthesize news for a specific topic."""
    topic = config_mgr.get_topic(req.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    result = await agent.analyze_topic(topic, req.start_date, req.end_date, force_refresh=req.force_refresh)
    return result


@router.get("/latest")
async def get_latest_digest(
    start_date: Optional[str] = Query(None, description="Optional start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Optional end date YYYY-MM-DD")
):
    """Get the cached latest digest from SQLite persistent cache or memory."""
    if start_date and end_date:
        cached = agent.cache.get_digest(start_date, end_date)
        if cached:
            agent.latest_digest = cached
            return cached

    if agent.latest_digest:
        return agent.latest_digest

    cached_latest = agent.cache.get_latest_digest()
    if cached_latest:
        agent.latest_digest = cached_latest
        return cached_latest

    raise HTTPException(status_code=404, detail="No cached news digest available yet")
