# NewsLens: Functional Requirements & System Specification Document

**Project**: NewsLens — Autonomous Multi-Topic News & Intelligence Analyst Platform  
**Repository**: [https://github.com/jaimalleshk/NewsLens-Agent](https://github.com/jaimalleshk/NewsLens-Agent)  
**Version**: 1.0.0 (Production Stable)  
**Status**: Verified & Operational  
**Last Updated**: September 2026  

---

## 1. Executive Summary & Vision

NewsLens is an autonomous, real-time AI news intelligence and synthesis platform built for executives, strategists, and decision-makers. It autonomously discovers, indexes, dedupes, clusters, and analyzes multi-topic news from global sources and delivers **standalone, high-signal Twitter/X-style intelligence summaries (~35–50 words)** that provide the complete picture (entity, metrics, action, outcome, and ecosystem impact) without clickbait, question headlines, or shallow links.

NewsLens includes an **Executive Cross-Sector Macro Synthesis**, **Edge-TTS Spoken Audio Broadcasts**, **SQLite Persistent Caching**, and **Natural Language Voice Control**.

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                 NEWSLENS PLATFORM                                      │
├───────────────────────┬───────────────────────────────────┬───────────────────────────┤
│ Multi-Source Search   │ AI Synthesis & RAG               │ Voice & Delivery          │
│ • Google News RSS     │ • DeepSeek-Chat / Local LLM       │ • Edge-TTS Neural Voice   │
│ • DuckDuckGo News     │ • Twitter/X Standalone Posts      │ • Spoken Anchor Broadcast │
│ • Temporal Filtering  │ • Zero-Question Declarative Intel │ • Parallel Synthesis      │
│ • Source Clustering   │ • Macro Cross-Sector Digest       │ • SHA-256 Audio Cache     │
└───────────────────────┴───────────────────────────────────┴───────────────────────────┘
```

---

## 2. Target User Persona & Core Value Proposition

* **Executive User**: Requires rapid comprehension of macroeconomic, tech, policy, regional, and market developments across 13+ verticals in minutes.
* **Core Rule**: Every intelligence card must deliver the **full picture** in a self-contained 35–50 word post so the reader never needs to click an external link to understand what happened, why, and what it means.
* **Layout Rule**: Zero wasted vertical space. The card begins immediately with the high-signal tweet summary, followed by a compact bottom source tag (`🔗 Publisher @handle · Date ↗`) and an instantaneous `[🔊 Listen]` action.

---

## 3. Functional Requirements Specification

### 3.1 Multi-Topic Management & Dynamic Configuration
* **FR-1.1: 13 Monitored Verticals**: Supports customizable topic tabs out-of-the-box:
  1. *Artificial Intelligence*
  2. *Finance & Business (USA)*
  3. *USA IT & Enterprise Tech*
  4. *USA Politics & Immigration*
  5. *Local: Houston & Tomball, TX*
  6. *Narendra Modi (PM Updates)*
  7. *Sri Sri Ravi Shankar*
  8. *Republic TV Top News*
  9. *Finance & Business (India)*
  10. *India IT & Tech Industry*
  11. *India Politics & Governance*
  12. *AI Hardware & Chips*
  13. *Optical Computing & Silicon Photonics*
* **FR-1.2: Dynamic YAML Persistence**: All topics, search keywords, strategy prompts, and preferences are dynamically stored in `config.user.yaml` and reloaded automatically without server restarts.
* **FR-1.3: Keyword Management**: Users can add or remove search keywords per topic directly from the UI chip bar or via voice/chat commands.

---

### 3.2 Ingestion, Multi-Engine Search & Clustering
* **FR-2.1: Hybrid Ingestion Engine**: Pulls articles across Google News RSS and DuckDuckGo News with customizable date boundaries (`start_date`, `end_date`).
* **FR-2.2: RAG Vector Store**: Index article chunks into an in-memory vector store for contextual retrieval and semantic similarity matching.
* **FR-2.3: Semantic Story Clustering**: Automatically groups duplicate coverage and multi-outlet reporting into unified story clusters, identifying primary sources and secondary corroborating citations.

---

### 3.3 AI Tweet-Style Intelligence Synthesis
* **FR-3.1: Standalone Twitter/X Format (~35–50 Words)**:
  - Every card synthesizes the full story into one punchy, standalone post.
  - Structure: `[Primary Entity/Actor] + [Concrete Metric/Action] + [Root Driver/Context] + [Strategic Impact/Outcome]`.
* **FR-3.2: Strict Ban on Question Headlines & Clickbait Teasers**:
  - The AI model reads full article contents and formulates **declarative factual outcomes**.
  - Transforms questions (e.g. *"Why did the Fed cut rates?"* $\rightarrow$ *"Federal Reserve Lowers Benchmark Rates by 25 bps as Inflation Cools"*).
  - Regex guards protect acronyms (`A.I.`, `U.S.`, `U.K.`, `E.U.`) from mid-word tokenizer fragmentation.
* **FR-3.3: Elimination of Boilerplate Fillers**:
  - Completely bans boilerplate phrases like *"Verified reporting from X details key operational milestones..."* or *"Confirmed reporting from X reflects..."*.
  - Enriches brief summaries using substantive context, impact, and key data points.

---

### 3.4 Executive Overview & Cross-Sector Macro Digest
* **FR-4.1: Top Macro Synthesis Card**: Renders solely a high-level 2–3 paragraph strategic cross-sector synthesis connecting overarching trends, capital allocation, and regulatory shifts across all active verticals.
* **FR-4.2: Visual Card Grid**: Renders the complete, clean visual feed of all topic cards below the macro synthesis, eliminating legacy raw bullet link dumps.

---

### 3.5 Natural Spoken Audio Broadcast Engine (Edge-TTS)
* **FR-5.1: High-Fidelity Neural Voices**: Powered by Microsoft Edge-TTS (`en-US-AndrewMultilingualNeural`, `en-US-AvaMultilingualNeural`, `en-US-BrianMultilingualNeural`).
* **FR-5.2: Zero Audio Duplication**: Broadcast scripts narrate each development once using fluent newsroom transitions (*"Leading off..."*, *"Turning to related developments..."*, *"Meanwhile in the sector..."*), completely omitting repetitive headline reading.
* **FR-5.3: Parallel Synthesis & Performance Acceleration**:
  - Long broadcasts are split into sentence-bounded chunks and synthesized concurrently via `asyncio.gather`, cutting multi-chunk generation latency by 3x–5x.
* **FR-5.4: Persistent Disk & Memory Audio Caching**:
  - Audio files are cached in `data/audio_cache/<sha256>.mp3`.
  - Repeat listens and pre-cached cards return instantly in **<5 milliseconds**.

---

### 3.6 Persistence & SQLite Caching
* **FR-6.1: Full SQLite Cache**: All raw articles, topic results, 5-line analyses, audio scripts, and aggregated digests persist in `data/newslens.db`.
* **FR-6.2: Seamless Browser Refresh (F5)**: On page reload, the frontend immediately queries `/api/news/latest`, restoring all 13 topic tabs, card feeds, and story counts with zero data loss.

---

### 3.7 Space-Efficient, Message-First UI Layout
* **FR-7.1: Zero Top-Header Clutter**: Cards start directly with the intelligence tweet body text.
* **FR-7.2: Unified Source Tag**: Integrated bottom footer containing:
  - Clickable source link: `🔗 Publisher @handle · YYYY-MM-DD ↗`
  - Audio listen button: `[🔊 Listen]`
* **FR-7.3: Compact / Full View Mode Toggle**: Toggle between compact 1-line tweet cards and detailed 5-line analytical breakdown cards (`Context`, `Impact`, `Data`, `Outlook`).

---

## 4. System Architecture & Component Mapping

```
NewsLens-Agent/
├── backend/
│   ├── server.py              # FastAPI application, static mounting, CORS
│   ├── schemas.py             # Pydantic request/response schemas
│   └── routes/
│       ├── news.py            # /api/news (aggregate, stream, topic, latest)
│       ├── config.py          # /api/config (read, update, topic management)
│       ├── voice.py           # /api/voice (tts, stt, transcribe)
│       ├── dialogue.py        # /api/dialogue (natural language commands)
│       └── llm.py             # /api/llm (providers, models, test connection)
├── news_agent_core/
│   ├── config.py              # Configuration manager & YAML persistence
│   ├── agent/
│   │   ├── analyst.py         # Primary NewsAnalystAgent & orchestration
│   │   └── prompts.py         # Intelligence prompts & zero-question rules
│   ├── llm/
│   │   ├── client.py          # DeepSeek API & OpenAI-compatible LLM client
│   │   └── prompts.py         # 5-line summarization & intent parser prompts
│   ├── rag/
│   │   ├── vector_store.py    # Temporal cosine similarity RAG store
│   │   └── clusterer.py       # TF-IDF / semantic article clusterer
│   ├── search/
│   │   ├── ddg_search.py      # DuckDuckGo news provider
│   │   ├── rss_search.py      # Google News RSS provider
│   │   └── extractor.py       # HTML / snippet text extraction
│   ├── voice/
│   │   ├── tts.py             # Fast parallel & cached Edge-TTS briefer
│   │   └── stt.py             # Speech-to-text transcription engine
│   └── storage/
│       └── sqlite_db.py       # SQLite database & on-the-fly sanitization
├── frontend/
│   ├── index.html             # Single-page executive portal
│   ├── css/style.css          # Dark executive theme & space-efficient layout
│   └── js/
│       ├── app.js             # State management, SSE streaming, card UI
│       └── voice.js           # Audio playback, Web Speech STT, floating bar
├── data/
│   ├── newslens.db            # SQLite persistent store
│   └── audio_cache/           # SHA-256 cached MP3 audio files
└── tests/                     # 23 Automated pytest unit & integration tests
```

---

## 5. Performance & Audio Optimization Profile

| Metric | Target | Observed / Achieved | Status |
| :--- | :--- | :--- | :--- |
| **SQLite Refresh Latency (F5)** | < 100 ms | ~ 25 ms | ✅ Passed |
| **Single Card Read Aloud (Network)** | < 2.0 s | ~ 1.2 s | ✅ Passed |
| **Single Card Read Aloud (Cached)** | < 10 ms | < 4 ms | ✅ Passed |
| **Topic Spoken Broadcast (Parallel TTS)** | < 3.5 s | ~ 2.1 s | ✅ Passed |
| **Topic Spoken Broadcast (Cached)** | < 10 ms | < 5 ms | ✅ Passed |
| **Unit & Integration Test Suite** | 100% pass | 23 / 23 passed | ✅ Passed |

---

## 6. Verification & Acceptance Criteria

1. **Standalone Intelligence Post**: Every card across all 13 topics contains a standalone, high-signal intelligence summary (~35–50 words) providing complete factual context.
2. **Zero Question Headlines**: Headings and summaries are strictly declarative statements of fact/analysis.
3. **Zero Boilerplate**: No repetitive filler phrases (*"Verified reporting from..."*, *"Confirmed reporting from..."*).
4. **Maximized Vertical Space**: Card headers have been replaced with compact bottom source tags.
5. **Fast Audio Playback**: Card audio and topic broadcasts leverage parallel synthesis and SHA-256 disk caching for instant replay.
6. **Persistent SQLite Database**: Page refresh (F5) immediately restores all 13 topics and cached cards without data loss.
