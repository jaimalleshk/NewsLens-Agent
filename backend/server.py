"""FastAPI Server for News & Analysis Agent Platform."""

from __future__ import annotations
import os
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import config, news, chat, voice

app = FastAPI(
    title="News & Analysis Agent API",
    description="Backend API for Multi-Topic Ingestion, Live Temporal RAG, DeepSeek/Local LLM, and Natural Voice Intelligence",
    version="0.1.0"
)

# Enable CORS for cross-origin frontend apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(config.router)
app.include_router(news.router)
app.include_router(chat.router)
app.include_router(voice.router)

# Mount Frontend static files
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


def start(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Entrypoint to run the FastAPI server."""
    uvicorn.run("backend.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    start()
