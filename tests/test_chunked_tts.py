"""Test chunked TTS synthesis for long scripts."""

import pytest
from news_agent_core.voice.tts import NaturalVoiceBriefer


def test_chunk_text():
    briefer = NaturalVoiceBriefer()
    sentences = [
        f"Story number {i} provides detailed reporting on strategic technological investments and economic policy developments."
        for i in range(40)
    ]
    long_text = " ".join(sentences)
    assert len(long_text) > 4000

    chunks = briefer._split_text_into_chunks(long_text, max_chunk_chars=1500)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1800
        assert chunk.strip().endswith((".", "!", "?", '."'))


@pytest.mark.asyncio
async def test_generate_speech_audio_long_text():
    briefer = NaturalVoiceBriefer()
    sentences = [
        f"Development {i} showcases breakthrough advancements in artificial intelligence models and high performance compute."
        for i in range(15)
    ]
    long_text = " ".join(sentences)
    audio_bytes = await briefer.generate_speech_audio(long_text)
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 5000
