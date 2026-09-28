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

    def __init__(self, config: Optional[VoiceConfig] = None, cache_dir: Optional[str | Path] = None):
        self.config = config or VoiceConfig()
        import hashlib
        self._hashlib = hashlib
        self.cache_dir = Path(cache_dir or (Path(__file__).resolve().parent.parent.parent / "data" / "audio_cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, bytes] = {}

    def _get_cache_key(self, clean_text: str, voice: str, rate: str, pitch: str) -> str:
        """Generate SHA-256 cache key for given voice parameters."""
        raw_key = f"{clean_text}__{voice}__{rate}__{pitch}"
        return self._hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

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

    def _split_text_into_chunks(self, text: str, max_chunk_chars: int = 1800) -> list[str]:
        """Split text into clean, sentence-bounded chunks suitable for Edge TTS synthesis."""
        if not text:
            return []
        if len(text) <= max_chunk_chars:
            return [text]

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            if current_len + sentence_len > max_chunk_chars and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_len = sentence_len
            else:
                current_chunk.append(sentence)
                current_len += sentence_len + 1

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    async def generate_speech_audio(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None
    ) -> bytes:
        """Synthesize natural speech audio and return MP3 bytes with caching & parallel chunk streaming."""
        clean_text = self.clean_text_for_speech(text)
        if not clean_text:
            return b""

        selected_voice = voice or self.config.tts_voice
        selected_rate = rate or self.config.tts_rate
        selected_pitch = pitch or self.config.tts_pitch

        # Check in-memory cache first (<1ms)
        cache_key = self._get_cache_key(clean_text, selected_voice, selected_rate, selected_pitch)
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]

        # Check persistent disk cache (<5ms)
        cache_file = self.cache_dir / f"{cache_key}.mp3"
        if cache_file.exists():
            try:
                cached_bytes = cache_file.read_bytes()
                if cached_bytes:
                    if len(self._memory_cache) > 200:
                        self._memory_cache.clear()
                    self._memory_cache[cache_key] = cached_bytes
                    return cached_bytes
            except Exception as e:
                logger.debug(f"Error reading audio cache file: {e}")

        # Chunk text and synthesize in parallel
        chunks = self._split_text_into_chunks(clean_text, max_chunk_chars=1200)

        async def synthesize_chunk(chunk_text: str) -> bytes:
            try:
                communicate = edge_tts.Communicate(
                    text=chunk_text,
                    voice=selected_voice,
                    rate=selected_rate,
                    pitch=selected_pitch
                )
                audio_pieces = []
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_pieces.append(chunk["data"])
                return b"".join(audio_pieces)
            except Exception as ex:
                logger.warning(f"Error synthesizing TTS chunk: {ex}")
                return b""

        if len(chunks) == 1:
            full_audio = await synthesize_chunk(chunks[0])
        else:
            # Parallel synthesis of all chunks concurrently
            chunk_results = await asyncio.gather(*[synthesize_chunk(c) for c in chunks])
            full_audio = b"".join(chunk_results)

        if full_audio:
            # Store to disk and memory cache
            try:
                cache_file.write_bytes(full_audio)
            except Exception as e:
                logger.debug(f"Error writing audio cache file: {e}")

            if len(self._memory_cache) > 200:
                self._memory_cache.clear()
            self._memory_cache[cache_key] = full_audio

        return full_audio

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
