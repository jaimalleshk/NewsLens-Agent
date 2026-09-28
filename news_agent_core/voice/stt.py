"""Speech-To-Text helper module for voice commands and audio transcription."""

from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SpeechToTextHandler:
    """Handles audio speech-to-text transcription."""

    def __init__(self):
        pass

    async def transcribe_audio_bytes(self, audio_bytes: bytes, format_hint: str = "wav") -> str:
        """Transcribe audio bytes using local/cloud STT service if available."""
        # The Web Frontend handles native Web Speech API recognition directly in the browser.
        # This backend stub provides an extension point for local Whisper or audio file uploads.
        if not audio_bytes:
            return ""
        logger.info(f"Received {len(audio_bytes)} bytes of audio for transcription.")
        return ""
