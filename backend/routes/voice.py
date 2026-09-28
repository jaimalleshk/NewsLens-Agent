"""Voice TTS and Speech API routes."""

from fastapi import APIRouter, Response, HTTPException
from news_agent_core.voice.tts import NaturalVoiceBriefer
from news_agent_core.config import ConfigManager
from ..schemas import TTSRequest

router = APIRouter(prefix="/api/voice", tags=["Voice & Speech"])

config_mgr = ConfigManager()
briefer = NaturalVoiceBriefer(config=config_mgr.config.voice)


@router.post("/tts")
async def generate_speech_audio(req: TTSRequest):
    """Synthesize text into natural broadcast MP3 audio stream."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    audio_bytes = await briefer.generate_speech_audio(
        text=req.text,
        voice=req.voice
    )

    if not audio_bytes:
        raise HTTPException(status_code=500, detail="Failed to synthesize speech audio")

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=speech.mp3"}
    )
