# NewsLens REST & Streaming API Reference

The NewsLens backend is built on FastAPI and exposes high-performance REST and Server-Sent Events (SSE) streaming endpoints.

---

## 1. News Intelligence Endpoints

### GET /api/news/stream
Streams live topic-by-topic news ingestion results as Server-Sent Events (SSE).

**Query Parameters:**
- start_date (string, required): Format YYYY-MM-DD
- end_date (string, required): Format YYYY-MM-DD

**Event Sequence:**
1. event: start — Total topics and metadata.
2. event: topic_result — Emitted as each topic completes, delivering curated news items in real time.
3. event: complete — Final aggregated digest including the full Executive Overview and complete spoken audio script.

---

### POST /api/news/aggregate
Synchronous fallback endpoint that aggregates news across all active topics and returns the complete digest payload.

**Request Body:**
\\\json
{
  "start_date": "2026-09-20",
  "end_date": "2026-09-27"
}
\\\

---

### GET /api/news/topic/{topic_id}
Fetches and synthesizes news for a single specific topic tab.

**Query Parameters:**
- start_date (string)
- end_date (string)

---

## 2. LLM & Model Configuration Endpoints

### GET /api/config/llm/models
Discovers and lists available models for a given provider.

**Query Parameters:**
- provider: "deepseek" or "local"

**Example Response (DeepSeek):**
\\\json
{
  "provider": "deepseek",
  "models": [
    { "id": "deepseek-chat", "name": "DeepSeek-V3 (deepseek-chat)", "recommended": true },
    { "id": "deepseek-reasoner", "name": "DeepSeek-R1 (deepseek-reasoner)", "recommended": false },
    { "id": "deepseek-coder", "name": "DeepSeek Coder (deepseek-coder)", "recommended": false }
  ]
}
\\\

---

### POST /api/config/llm/test-connection
Validates LLM credentials or local server connectivity and returns live round-trip latency.

**Request Body:**
\\\json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "api_key": "sk-...",
  "api_base": "https://api.deepseek.com/v1"
}
\\\

**Response:**
\\\json
{
  "status": "ok",
  "latency_ms": 284,
  "message": "Successfully connected to deepseek (model: deepseek-chat)"
}
\\\

---

## 3. Configuration & YAML Persistence Endpoints

### GET /api/config/
Returns the current application configuration.

### POST /api/config/update
Atomically updates llm, 	opics, and ui preferences in memory and writes them directly to config.user.yaml.

### GET /api/config/yaml & POST /api/config/yaml
Direct read and save endpoints for raw YAML editing in the dashboard modal.

### POST /api/config/keywords/quick-add
Fast persistence endpoint for adding a keyword from the top feed bar directly into the selected topic's YAML config.

---

## 4. Voice Intelligence Endpoints

### POST /api/voice/synthesize
Generates natural Neural TTS audio bytes using Edge-TTS.

**Request Body:**
\\\json
{
  "text": "News broadcast text...",
  "voice": "en-US-AndrewMultilingualNeural",
  "rate": "+0%",
  "pitch": "+0Hz"
}
\\\
**Response:** Binary MP3 audio stream (udio/mpeg).

---

## 5. Agent Chat & Command Endpoints

### POST /api/agent/chat
Conversational dialogue manager supporting both general queries and dynamic agent actions (e.g. adding topics, changing date windows, updating LLMs via voice/text).
