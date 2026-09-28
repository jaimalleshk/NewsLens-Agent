# NewsLens — Autonomous Multi-Topic News & Intelligence Agent Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20%7C%20Local%20Ollama-purple.svg)](https://www.deepseek.com/)
[![Edge-TTS](https://img.shields.io/badge/Voice-Neural%20TTS-green.svg)](https://github.com/rany2/edge-tts)
[![Tests](https://img.shields.io/badge/Tests-14%20Passing-brightgreen.svg)](tests/)

An autonomous, multi-interface News & Intelligence Agent platform that continuously ingests live news across dynamic, user-configured topics, deduplicates stories across outlets, indexes content in a temporal RAG pipeline, synthesizes high-signal executive intelligence using **DeepSeek AI** or **Local Ollama LLMs**, and broadcasts fluid, continuous spoken audio briefings.

---

## 🌟 Key Architecture & Features

- **📦 Modular Python Core SDK (`news_agent_core`)**:
  - Fully decoupled core library that can be embedded into any Python application or automated service.
  - Multi-backend parallel ingestion (Google News RSS feeds + DuckDuckGo News) with non-blocking thread workers.
  - Story clustering and cross-outlet deduplication.
  - Temporal RAG vector store with cosine embeddings and date window boundaries.
  - Dual LLM support: **DeepSeek Online API** (`deepseek-chat` / DeepSeek-V3, `deepseek-reasoner` / DeepSeek-R1) and **Local Ollama** models with live model discovery.

- **🎙️ Continuous Section-by-Section Spoken Broadcasts (TTS & STT)**:
  - Radio-style continuous news narration covering 100% of aggregated stories across all topics.
  - Neural voice synthesis powered by Edge-TTS (`en-US-AndrewMultilingualNeural`).
  - Interactive speech-to-text (STT) for voice search, topic customization, and natural agent commands.

- **⚡ High-Throughput Streaming Ingestion (~10-15s total)**:
  - Non-blocking Server-Sent Events (SSE) stream (`GET /api/news/stream`).
  - Cards render progressively in real time as each topic completes without blocking the UI.
  - 100% comprehensive Executive Overview synthesizing all stories across active topics.

- **⚙️ Dynamic YAML Persistence & Live Model Controls**:
  - Live model discovery (`GET /api/config/llm/models`) and instant latency ping (`⚡ Test Connection`).
  - Password-toggleable (👁️) API key input with atomic YAML saving.
  - Dynamic keyword feeding bar with instant YAML sync.

- **💻 Dual Interface**:
  - **Modern Web Dashboard**: Single-page application with dynamic topic tabs, date filter presets (Today, 3D, 7D), non-blocking progress banner, audio broadcast player, and agent drawer.
  - **Rich Terminal CLI**: Interactive console app with progress spinners, colored panels, topic flags, and local voice narration.

---

## 📖 Documentation Index

- [Architecture & Technical Design](docs/ARCHITECTURE.md)
- [REST & Streaming API Reference](docs/API.md)
- [Configuration Guide & YAML Spec](docs/CONFIGURATION.md)

---

## 🚀 Quickstart Guide

### 1. Installation

Clone the repository and install in editable mode:
```bash
git clone https://github.com/jaimalleshk/newslens-agent.git
cd newslens-agent
pip install -e .
```

Or install required dependencies directly:
```bash
pip install httpx beautifulsoup4 feedparser duckduckgo_search fastapi uvicorn pydantic pyyaml rich typer edge-tts numpy pytest pytest-asyncio
```

---

### 2. Launching the Web Application

Start the FastAPI application and UI:
```bash
python -m backend.server
```

Open your browser at:
👉 **`http://localhost:8000`**

- Click **⚡ Run Ingestion** to stream real-time news across all active topics.
- Click **▶ Play Executive Spoken Broadcast** to listen to the continuous radio-style news briefing.
- Click the top **⚡ DeepSeek / Local** pill to test connections or switch LLM models.
- Type any keyword in the top bar to immediately inject and persist it into your YAML configuration.

---

### 3. Running the Interactive Terminal CLI

```bash
# Fetch cross-topic executive news digest
python -m cli.main digest --start 2026-09-20 --end 2026-09-27

# Fetch digest with live spoken voice readout
python -m cli.main digest --speak

# Inspect a single topic tab (e.g. AI & Machine Learning)
python -m cli.main topic artificial_intelligence --speak

# Launch interactive conversational and voice agent console
python -m cli.main chat
```

---

### 4. Consuming as a Python SDK

```python
import asyncio
from news_agent_core import NewsAnalystAgent, ConfigManager, NaturalVoiceBriefer

async def main():
    config_mgr = ConfigManager()
    agent = NewsAnalystAgent(config_manager=config_mgr)

    # Ingest and synthesize news for a date window
    digest = await agent.aggregate_all_topics(
        start_date="2026-09-20",
        end_date="2026-09-27"
    )

    print(f"Executive Overview:\n{digest.executive_overview}\n")

    for topic_res in digest.topic_results:
        print(f"\n=== {topic_res.topic_icon} {topic_res.topic_title} ({len(topic_res.items)} stories) ===")
        for item in topic_res.items:
            print(f"- {item.title} ({item.publisher})")
            print(f"  Summary: {item.summary.line1_what}")

    # Generate natural spoken broadcast audio
    briefer = NaturalVoiceBriefer()
    audio_bytes = await briefer.generate_speech_audio(digest.executive_audio_script)
    with open("briefing.mp3", "wb") as f:
        f.write(audio_bytes)
    print("\nSaved broadcast audio to briefing.mp3")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🧪 Running Unit & Integration Tests

```bash
pytest -v
```

All 14 test suites validate:
- Dynamic configuration persistence to YAML.
- DeepSeek model discovery and connection pinging.
- Story clustering and RAG vector store retrieval.
- Multi-topic news analyst synthesis.
- Edge-TTS natural voice audio generation.

---

## 📄 License

MIT License. Designed and developed for autonomous news intelligence and multi-topic strategic analysis.
