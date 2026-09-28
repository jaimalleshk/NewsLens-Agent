# NewsLens System Architecture & Technical Design

NewsLens is designed as an autonomous, high-throughput intelligence platform that continuously harvests news feeds across configurable topic verticals, eliminates cross-outlet duplication, performs RAG indexing with temporal boundaries, synthesizes precise executive summaries, and renders natural spoken audio briefings.

---

## High-Level Architecture

\\\
┌────────────────────────────────────────────────────────────────────────┐
│                          User Interfaces                               │
│   ┌───────────────────────────┐      ┌───────────────────────────────┐ │
│   │   Modern Web Dashboard    │      │    Interactive Terminal CLI   │ │
│   │ (HTML5 / Vanilla JS / CSS)│      │    (Rich / Typer / Speech)    │ │
│   └─────────────┬─────────────┘      └──────────────┬────────────────┘ │
└─────────────────┼───────────────────────────────────┼──────────────────┘
                  │ HTTP / SSE                        │ In-Process SDK
┌─────────────────▼───────────────────────────────────▼──────────────────┐
│                   FastAPI Backend Application Layer                    │
│   • /api/news (Stream & Aggregate)   • /api/config (YAML & LLM Test)   │
│   • /api/agent (Chat & Voice)        • /api/voice (Edge-TTS Audio)     │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼──────────────────────────────────────┐
│                   news_agent_core Python SDK Layer                     │
│                                                                        │
│   ┌─────────────────────┐  ┌─────────────────────┐  ┌────────────────┐ │
│   │ NewsAnalystAgent    │  │ ConfigManager       │  │ Vector Store   │ │
│   │ (Orchestrator)      │  │ (YAML / JSON Sync)  │  │ (Temporal RAG) │ │
│   └──────────┬──────────┘  └─────────────────────┘  └────────────────┘ │
│              │                                                         │
│   ┌──────────┴──────────┐  ┌─────────────────────┐  ┌────────────────┐ │
│   │ Search & Extraction │  │ Story Clusterer     │  │ Voice Briefer  │ │
│   │ (DDG + Google RSS)  │  │ (Cosine & Jaccard)  │  │ (Edge-TTS)     │ │
│   └──────────┬──────────┘  └─────────────────────┘  └────────────────┘ │
│              │                                                         │
│   ┌──────────▼───────────────────────────────────────────────────────┐ │
│   │ UnifiedLLMClient (DeepSeek Online API / Local Ollama Engine)     │ │
│   └──────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
\\\

---

## Ingestion Pipeline Phases

### 1. Multi-Backend Search & Scraping
- **Parallel Query Execution**: Queries Google News RSS feeds and DuckDuckGo News in non-blocking worker threads.
- **Smart Extraction**: Extracts article metadata (headline, publication date, outlet name, URL) with lightweight HTML body extraction on demand.

### 2. Story Clustering & Deduplication
- **Vector & N-gram Clustering**: Groups related articles reporting on the same underlying news event across multiple news outlets into distinct story clusters.
- **Cluster Aggregation**: Selects the primary source while preserving secondary sources as cross-references.

### 3. Synthesis & Summarization
- **Hybrid Synthesis**: Runs high-precision LLM summarization on top core clusters and instant extractive synthesis on secondary clusters to achieve ~10-15s total processing time across all topics.
- **Natural Language Output**: Formats clear, high-signal news stories without artificial meta-tag clutter.

### 4. Cross-Topic Executive Overview
- **100% Coverage Aggregation**: Compiles 100% of all aggregated news stories across every active topic into a comprehensive cross-sector executive intelligence overview.
- **Multi-Topic Spoken Audio Broadcast**: Generates a continuous, radio-style narrative script that flows through every topic section seamlessly.

### 5. Persistent YAML Configuration Engine
- **Bidirectional Sync**: Configuration changes made via the UI, Agent Chat, or Voice Commands are atomically written back to config.user.yaml.
- **Dynamic Topics & Keywords**: Dynamic addition and removal of search keywords and topic strategies without restarting the server.
