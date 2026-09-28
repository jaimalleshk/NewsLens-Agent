"""High fidelity natural voice synthesis and executive news broadcast engine."""

from __future__ import annotations
import os
import re
import asyncio
import logging
from pathlib import Path
from typing import Optional
import edge_tts

from ..config import VoiceConfig

logger = logging.getLogger(__name__)


class NaturalVoiceBriefer:
    """Generates broadcast-quality natural spoken audio using Neural TTS."""

    # Curated expressive neural voices
    DEFAULT_VOICES = {
        "andrew_male": "en-US-AndrewMultilingualNeural",   # Warm, authoritative, executive male
        "brian_male": "en-US-BrianMultilingualNeural",     # Deep, clear broadcaster male
        "ava_female": "en-US-AvaMultilingualNeural",       # Expressive, natural executive female
        "jenny_female": "en-US-JennyNeural",               # Professional, clear female
        "ryan_british": "en-GB-RyanNeural",                # British executive male
    }

    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()

    def clean_text_for_speech(self, text: str) -> str:
        """Sanitize markdown, URLs, symbols, emojis, and formatting into fluid, natural spoken text."""
        if not text:
            return ""

        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)
        # Remove markdown headers and formatting
        text = re.sub(r"#{1,6}\s*", "", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

        # Strip emojis and special decorative glyphs
        text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
        text = re.sub(r"[🌐🤖💼📈🏛️📍🏡🩺⚡🎙️🔑★•▪●]", " ", text)

        # Remove bullet labels like What:, Context:, etc.
        text = re.sub(r"^[•\-\*]\s*(What|Context|Impact|Key Data|Outlook):\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[•\-\*]\s*", "", text, flags=re.MULTILINE)

        # Expand currency and financial abbreviations for natural spoken reading
        text = re.sub(r"\$(\d+(?:\.\d+)?)\s*[Bb](?:illion)?\b", r"\1 billion dollars", text)
        text = re.sub(r"\$(\d+(?:\.\d+)?)\s*[Mm](?:illion)?\b", r"\1 million dollars", text)
        text = re.sub(r"\$(\d+(?:\.\d+)?)\s*[Kk]\b", r"\1 thousand dollars", text)
        text = re.sub(r"\$(\d+(?:,\d+)*(?:\.\d+)?)", r"\1 dollars", text)

        # Acronyms for clear natural pronunciation
        acronyms = {
            r"\bAI\b": "A.I.",
            r"\bISD\b": "I.S.D.",
            r"\bCEO\b": "C.E.O.",
            r"\bCTO\b": "C.T.O.",
            r"\bGPU\b": "G.P.U.",
            r"\bGPUs\b": "G.P.U.s",
            r"\bLLM\b": "L.L.M.",
            r"\bLLMs\b": "L.L.M.s",
            r"\bAPI\b": "A.P.I.",
            r"\bAPIs\b": "A.P.I.s",
            r"\bTSMC\b": "T.S.M.C.",
        }
        for pat, rep in acronyms.items():
            text = re.sub(pat, rep, text)

        # Deduplicate back-to-back identical sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        deduped = []
        for s in sentences:
            if not deduped or s.lower() != deduped[-1].lower():
                deduped.append(s)
        text = " ".join(deduped)

        # Clean multiple spaces and linebreaks
        text = re.sub(r"\s+", " ", text).strip()
        return text

    async def generate_speech_audio(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None
    ) -> bytes:
        """Synthesize natural speech audio and return MP3 bytes."""
        clean_text = self.clean_text_for_speech(text)
        if not clean_text:
            return b""

        selected_voice = voice or self.config.tts_voice
        selected_rate = rate or self.config.tts_rate
        selected_pitch = pitch or self.config.tts_pitch

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=selected_voice,
            rate=selected_rate,
            pitch=selected_pitch
        )

        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        return b"".join(audio_chunks)

    async def save_speech_to_file(
        self,
        text: str,
        output_path: str | Path,
        voice: Optional[str] = None
    ) -> Path:
        """Synthesize and save audio directly to an MP3 file."""
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        audio_bytes = await self.generate_speech_audio(text, voice=voice)
        with open(dest, "wb") as f:
            f.write(audio_bytes)

        return dest

    async def speak_locally(self, text: str) -> None:
        """Play synthesized audio locally (useful in CLI)."""
        import tempfile
        import subprocess

        temp_file = Path(tempfile.gettempdir()) / f"news_speech_{os.getpid()}.mp3"
        await self.save_speech_to_file(text, temp_file)

        # Play in background using PowerShell or default media player on Windows
        try:
            ps_cmd = f'(New-Object Media.SoundPlayer "{temp_file}").PlaySync()'
            # For MP3 on Windows, use Windows Media Player COM object or ffplay / start
            vbs_cmd = f'powershell -c "$m = New-Object -ComObject WMPlayer.OCX; $m.URL = \'{temp_file}\'; $m.controls.play(); while ($m.playState -ne 1) {{ Start-Sleep -Milliseconds 100 }}"'
            subprocess.run(vbs_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.debug(f"Local audio playback error: {e}")
