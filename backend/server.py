"""FastAPI Server for News & Analysis Agent Platform."""

from __future__ import annotations
from contextlib import asynccontextmanager
import os
import threading
import webbrowser
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes import config, news, chat, voice


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager that optionally opens the browser once the server is ready."""
    if os.environ.get("NEWSLENS_OPEN_BROWSER") == "1":
        port = os.environ.get("NEWSLENS_PORT", "8000")
        url = f"http://localhost:{port}"
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    yield


app = FastAPI(
    title="News & Analysis Agent API",
    description="Backend API for Multi-Topic Ingestion, Live Temporal RAG, DeepSeek/Local LLM, and Natural Voice Intelligence",
    version="0.1.0",
    lifespan=lifespan,
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


def start(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Entrypoint to run the FastAPI server."""
    uvicorn.run("backend.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    start()

