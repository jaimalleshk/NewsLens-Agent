import time
import httpx
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from news_agent_core.config import ConfigManager, TopicConfig, AppConfig, LLMConfig
from ..schemas import (
    ConfigUpdateRequest,
    RawYamlRequest,
    RawYamlResponse,
    AddKeywordsRequest,
    RemoveKeywordRequest,
    QuickAddKeywordRequest,
    LLMModelItem,
    LLMModelsResponse,
    LLMTestConnectionRequest,
    LLMTestConnectionResponse,
)

router = APIRouter(prefix="/api/config", tags=["Configuration"])
config_mgr = ConfigManager()


@router.get("", response_model=AppConfig)
async def get_configuration():
    return config_mgr.load()


@router.get("/raw")
async def get_raw_configuration(format: str = Query("yaml", pattern="^(yaml|json)$")):
    """Retrieve raw configuration text in YAML or JSON format."""
    try:
        content, path = config_mgr.get_formatted_config(format)
        return {"content": content, "format": format, "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read configuration: {e}")


@router.get("/yaml", response_model=RawYamlResponse)
async def get_raw_yaml_configuration():
    """Retrieve raw YAML configuration file text and path."""
    try:
        yaml_content, path = config_mgr.get_raw_yaml()
        return RawYamlResponse(yaml=yaml_content, path=path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read YAML file: {e}")


@router.post("/yaml")
async def save_raw_yaml_configuration(req: RawYamlRequest):
    """Validate and save raw YAML text directly into configuration file."""
    try:
        validated_config = config_mgr.save_raw_yaml(req.yaml)
        return {
            "status": "success",
            "message": "Configuration saved successfully",
            "config": validated_config,
            "path": str(config_mgr.config_path)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {e}")


@router.post("/update")
async def update_configuration(req: ConfigUpdateRequest):
    if req.llm:
        config_mgr.config.llm = req.llm
    if req.voice:
        config_mgr.config.voice = req.voice
    if req.search:
        config_mgr.config.search = req.search
    if req.ui:
        config_mgr.config.ui = req.ui
    if req.topics is not None:
        config_mgr.config.topics = req.topics
    config_mgr.save()
    return {"status": "success", "config": config_mgr.config}


@router.get("/topics", response_model=List[TopicConfig])
async def list_topics():
    return config_mgr.config.topics


@router.post("/topics")
async def add_or_update_topic(topic: TopicConfig):
    config_mgr.upsert_topic(topic)
    return {"status": "success", "topic": topic}


@router.delete("/topics/{topic_id}")
async def delete_topic(topic_id: str):
    success = config_mgr.delete_topic(topic_id)
    if not success:
        raise HTTPException(status_code=404, detail="Topic ID not found")
    return {"status": "success", "deleted_topic_id": topic_id}


@router.post("/topics/{topic_id}/keywords")
async def add_topic_keywords(topic_id: str, req: AddKeywordsRequest):
    """Add search keywords/queries to a specific topic and persist to YAML."""
    topic = config_mgr.add_keywords_to_topic(topic_id, req.keywords)
    if not topic:
        raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")
    return {
        "status": "success",
        "message": f"Added {len(req.keywords)} keywords to {topic.title} and saved to YAML",
        "topic": topic,
        "path": str(config_mgr.config_path)
    }


@router.delete("/topics/{topic_id}/keywords")
async def delete_topic_keyword(topic_id: str, req: RemoveKeywordRequest):
    """Remove a search keyword/query from a topic and persist to YAML."""
    success = config_mgr.remove_keyword_from_topic(topic_id, req.keyword)
    if not success:
        raise HTTPException(status_code=404, detail=f"Keyword '{req.keyword}' not found in topic '{topic_id}'")
    topic = config_mgr.find_topic(topic_id)
    return {
        "status": "success",
        "message": f"Removed keyword '{req.keyword}' and saved to YAML",
        "topic": topic
    }


@router.post("/keywords/quick-add")
async def quick_add_keyword(req: QuickAddKeywordRequest):
    """Feed a new keyword/query to an existing or dynamic topic, saving to YAML."""
    try:
        topic, is_new = config_mgr.quick_feed_keyword(req.keyword, req.topic_id)
        return {
            "status": "success",
            "is_new_topic": is_new,
            "message": f"Keyword '{req.keyword}' saved to '{topic.title}' in YAML",
            "topic": topic,
            "path": str(config_mgr.config_path)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/llm/models", response_model=LLMModelsResponse)
async def get_available_llm_models(provider: str = Query("deepseek", pattern="^(deepseek|local)$")):
    """Return comprehensive model options for the specified provider (DeepSeek Online or Local Ollama)."""
    if provider == "deepseek":
        deepseek_models = [
            LLMModelItem(
                id="deepseek-chat",
                name="deepseek-chat (DeepSeek-V3)",
                description="Ultra-fast flagship model (64K context). Recommended for rapid news ingestion, 1-line takeaways & 5-line analysis.",
                recommended=True,
                context_length="64k"
            ),
            LLMModelItem(
                id="deepseek-reasoner",
                name="deepseek-reasoner (DeepSeek-R1)",
                description="Deep Chain-of-Thought reasoning model. Best for deep geopolitical, macro-economic, and strategic intelligence synthesis.",
                recommended=False,
                context_length="64k"
            ),
            LLMModelItem(
                id="deepseek-coder",
                name="deepseek-coder (DeepSeek Coder)",
                description="Specialized in technical news, algorithmic updates, and developer-centric intelligence.",
                recommended=False,
                context_length="16k"
            )
        ]
        return LLMModelsResponse(provider="deepseek", models=deepseek_models, detected_live=False)

    # Local Ollama Provider - attempt to detect installed models via Ollama API
    local_base = config_mgr.config.llm.local_api_base or "http://localhost:11434/v1"
    host_base = local_base.replace("/v1", "").rstrip("/")
    detected_models: List[LLMModelItem] = []
    detected_live = False

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{host_base}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    m_name = m.get("name", "")
                    size_gb = round(m.get("size", 0) / (1024**3), 1)
                    detected_models.append(
                        LLMModelItem(
                            id=m_name,
                            name=f"{m_name} (Installed - {size_gb}GB)",
                            description="Locally installed Ollama model detected on system.",
                            recommended=(m_name.startswith("deepseek-r1") or "llama3" in m_name)
                        )
                    )
                if detected_models:
                    detected_live = True
    except Exception:
        pass

    # Standard fallback local models catalogue
    default_local_catalog = [
        LLMModelItem(id="deepseek-r1:8b", name="deepseek-r1:8b", description="DeepSeek-R1 8B quantized (Recommended for 8GB+ RAM/VRAM)", recommended=True),
        LLMModelItem(id="deepseek-r1:14b", name="deepseek-r1:14b", description="DeepSeek-R1 14B quantized (Balanced reasoning)", recommended=False),
        LLMModelItem(id="deepseek-r1:32b", name="deepseek-r1:32b", description="DeepSeek-R1 32B high reasoning capacity", recommended=False),
        LLMModelItem(id="llama3.3:latest", name="llama3.3:latest", description="Meta Llama 3.3 70B flagship local model", recommended=False),
        LLMModelItem(id="llama3.2:latest", name="llama3.2:latest", description="Meta Llama 3.2 3B lightweight fast local model", recommended=False),
        LLMModelItem(id="llama3.1:8b", name="llama3.1:8b", description="Meta Llama 3.1 8B general purpose", recommended=False),
        LLMModelItem(id="qwen2.5:7b", name="qwen2.5:7b", description="Alibaba Qwen 2.5 7B high accuracy & speed", recommended=False),
        LLMModelItem(id="qwen2.5:14b", name="qwen2.5:14b", description="Alibaba Qwen 2.5 14B multilingual & analytical", recommended=False),
        LLMModelItem(id="mistral:latest", name="mistral:latest", description="Mistral 7B fast summarization", recommended=False),
        LLMModelItem(id="phi4:latest", name="phi4:latest", description="Microsoft Phi-4 14B synthetic reasoning", recommended=False),
        LLMModelItem(id="gemma2:9b", name="gemma2:9b", description="Google Gemma 2 9B instruction tuned", recommended=False),
    ]

    # Merge detected models with catalog (avoid duplicates)
    final_models = detected_models.copy()
    existing_ids = {m.id for m in final_models}
    for item in default_local_catalog:
        if item.id not in existing_ids:
            final_models.append(item)

    return LLMModelsResponse(provider="local", models=final_models, detected_live=detected_live)


@router.post("/llm/test-connection", response_model=LLMTestConnectionResponse)
async def test_llm_connection(req: LLMTestConnectionRequest):
    """Perform a live round-trip test against DeepSeek Online API or Local Ollama."""
    provider = req.provider.lower()
    
    if provider == "deepseek":
        api_key = req.api_key.strip() if req.api_key is not None else (config_mgr.config.llm.api_key or "").strip()
        if not api_key:
            return LLMTestConnectionResponse(
                status="error",
                message="DeepSeek API key is missing. Please enter your API key (starts with sk-...) from platform.deepseek.com."
            )

        base = (req.api_base or config_mgr.config.llm.api_base or "https://api.deepseek.com/v1").rstrip("/")
        url = f"{base}/chat/completions" if not base.endswith("/chat/completions") else base
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": req.model or "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a connectivity tester."},
                {"role": "user", "content": "Respond with the single word: Connected"}
            ],
            "max_tokens": 10,
            "temperature": 0.0
        }

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)

                if resp.status_code == 200:
                    data = resp.json()
                    sample = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    return LLMTestConnectionResponse(
                        status="success",
                        message=f"DeepSeek Online API connection successful! Model '{req.model}' is ready.",
                        latency_ms=elapsed_ms,
                        sample_response=sample
                    )
                elif resp.status_code == 401:
                    return LLMTestConnectionResponse(
                        status="error",
                        message="Authentication failed (401 Unauthorized). Please check that your DeepSeek API key is valid."
                    )
                elif resp.status_code == 402:
                    return LLMTestConnectionResponse(
                        status="error",
                        message="Payment/Quota required (402). Your DeepSeek account balance may be insufficient."
                    )
                else:
                    return LLMTestConnectionResponse(
                        status="error",
                        message=f"DeepSeek API returned HTTP {resp.status_code}: {resp.text[:200]}"
                    )
        except httpx.ConnectTimeout:
            return LLMTestConnectionResponse(
                status="error",
                message="Connection timed out connecting to DeepSeek API endpoint (https://api.deepseek.com)."
            )
        except Exception as e:
            return LLMTestConnectionResponse(
                status="error",
                message=f"Connection failed: {str(e)}"
            )

    # Test Local Ollama connection
    local_base = (req.local_api_base or config_mgr.config.llm.local_api_base or "http://localhost:11434/v1").rstrip("/")
    url = f"{local_base}/chat/completions" if not local_base.endswith("/chat/completions") else local_base
    payload = {
        "model": req.model or "deepseek-r1:8b",
        "messages": [
            {"role": "user", "content": "Respond with: Connected"}
        ],
        "max_tokens": 10
    }

    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.post(url, headers={"Content-Type": "application/json"}, json=payload)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
            if resp.status_code == 200:
                data = resp.json()
                sample = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                return LLMTestConnectionResponse(
                    status="success",
                    message=f"Local LLM connection successful! Model '{req.model}' responded.",
                    latency_ms=elapsed_ms,
                    sample_response=sample
                )
            else:
                return LLMTestConnectionResponse(
                    status="error",
                    message=f"Local endpoint returned HTTP {resp.status_code}: {resp.text[:200]}"
                )
    except Exception as e:
        return LLMTestConnectionResponse(
            status="error",
            message=f"Could not connect to local LLM at {local_base}. Ensure Ollama is running (`ollama serve`). Error: {e}"
        )


