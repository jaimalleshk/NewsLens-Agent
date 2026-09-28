# NewsLens Configuration Guide (`config.default.yaml` & `config.user.yaml`)

NewsLens uses a clean, human-readable YAML configuration structure. All user modifications are automatically persisted to `config.user.yaml`, keeping default presets safe in `config.default.yaml`.

---

## 1. LLM Settings (`llm`)

```yaml
llm:
  # Provider: "deepseek" (DeepSeek Online API) or "local" (Ollama / Local OpenAI-compatible)
  provider: "deepseek"
  
  # Model identifier
  # DeepSeek Online: "deepseek-chat" (DeepSeek-V3) or "deepseek-reasoner" (DeepSeek-R1)
  # Local Ollama: "deepseek-r1:8b", "llama3.3", "mistral", etc.
  model: "deepseek-chat"
  
  # API Key (Required for DeepSeek Online, leave empty for Local Ollama)
  api_key: ""
  
  # API Base URLs
  api_base: "https://api.deepseek.com/v1"
  local_api_base: "http://localhost:11434/v1"
  
  # Inference parameters
  temperature: 0.3
  max_tokens: 2000
```

---

## 2. Search & Ingestion Settings (`search`)

```yaml
search:
  # Maximum news stories synthesized per topic
  max_results_per_topic: 20
  
  # Search backend: "hybrid" (Google News RSS + DuckDuckGo News)
  backend: "hybrid"
  
  # Timeout per external request in seconds
  timeout_seconds: 15
  
  # User agent for web extraction
  user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

---

## 3. Voice & Speech Synthesis Settings (`voice`)

```yaml
voice:
  # Edge-TTS Neural Voice Model (e.g. en-US-AndrewMultilingualNeural, en-US-BrianMultilingualNeural, en-US-AvaMultilingualNeural)
  tts_voice: "en-US-AndrewMultilingualNeural"
  
  # Speech speed adjustments ("+0%", "+15%", "-10%")
  tts_rate: "+0%"
  
  # Voice pitch adjustment
  tts_pitch: "+0Hz"
  
  # Enable broadcast-style news transitions
  broadcast_style: true
  
  # Play speech locally when using CLI
  enable_local_playback: true
```

---

## 4. Topic Configurations (`topics`)

Each topic represents a dynamic tab with custom search queries and strategic guidance prompts:

```yaml
topics:
  - id: "artificial_intelligence"
    title: "Artificial Intelligence"
    icon: "🤖"
    enabled: true
    max_articles: 20
    strategy_prompt: >
      Focus on foundational frontier model releases, open-weights innovations, efficient inference architectures (MoE, quantizations), 
      AI agent frameworks, and enterprise production deployments. Filter out repetitive promotional fluff.
    search_queries:
      - "frontier AI models LLM architecture release"
      - "open source AI weights benchmark"
      - "enterprise AI agent production deployment"

  - id: "cloud_infrastructure"
    title: "Cloud & Distributed Systems"
    icon: "☁️"
    enabled: true
    max_articles: 15
    strategy_prompt: >
      Monitor cloud hyper-scaler developments (AWS, Azure, GCP), Kubernetes orchestration, serverless platforms, 
      and high-performance distributed database infrastructure.
    search_queries:
      - "cloud computing infrastructure architecture AWS Azure GCP"
      - "Kubernetes distributed database release"
```
