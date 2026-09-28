"""Unit test for Natural Voice TTS synthesis."""

import pytest
from news_agent_core.voice.tts import NaturalVoiceBriefer


def test_clean_text_for_speech():
    briefer = NaturalVoiceBriefer()
    raw = "### Breaking Update\n- **What:** TSMC completed fab expansion [Source](https://example.com/tsmc).\n• Impact: 20% output increase."
    cleaned = briefer.clean_text_for_speech(raw)
    assert "https://" not in cleaned
    assert "###" not in cleaned
    assert "T.S.M.C. completed fab expansion" in cleaned
    assert "20 percent output increase" in cleaned or "20%" in cleaned


@pytest.mark.asyncio
async def test_generate_speech_audio():
    briefer = NaturalVoiceBriefer()
    audio_bytes = await briefer.generate_speech_audio("Good evening, here is your executive intelligence digest.")
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0
