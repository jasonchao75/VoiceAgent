"""Runtime PCM preparation uses frozen resource identity and collection fences."""

import asyncio
from importlib import import_module, util

import pytest

from src.config import TTSConfig
from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
from src.tts.echo_cache import EchoAudioCache


def renderer(cache, state, config, synthesize, events, manifest=None):
    """Require the production runtime adapter without invoking a provider."""
    assert util.find_spec("src.pipeline.echo_audio") is not None, "Runtime cache adapter absent"
    return import_module("src.pipeline.echo_audio").EchoAudio(
        cache=cache,
        bot_id="bot",
        collection=state,
        config=config,
        sample_rate=24000,
        gap_ms=50,
        manifest=manifest or {},
        synthesize=synthesize,
        record=lambda event, **data: events.append((event, data)),
    )


async def test_runtime_cached_repeated_units_stream_pcm_without_synthesis(tmp_path):
    cache = EchoAudioCache(tmp_path)
    state = IdentifierCollection(IdentifierVocabulary({"1": ["one"]}), target_length=None)
    config = TTSConfig(voice="fixture-voice")
    events, calls = [], []

    async def synthesize(unit, config, rate, *, timeout):
        calls.append((unit, config.speed))
        return b"\x01\x00" * 240

    await cache.prepare("bot", ["1"], config, 24000, synthesize, timeout=2)
    manifest = await cache.manifest("bot", ["1"], config, 24000)
    audio = renderer(cache, state, config, synthesize, events, manifest)
    calls.clear()
    chunks = [chunk async for chunk in audio.chunks("one one", generation=0)]
    assert b"".join(chunks) == b"\x01\x00" * 240 + b"\x00\x00" * 1200 + b"\x01\x00" * 240
    assert calls == []
    assert all(len(chunk) <= 960 for chunk in chunks)
    assert not any("playback" in event for event, _ in events)


async def test_clear_during_missing_asset_repair_never_reinserts_audio(tmp_path):
    cache = EchoAudioCache(tmp_path)
    state = IdentifierCollection(IdentifierVocabulary({"1": ["one"]}), target_length=None)
    config = TTSConfig(voice="fixture-voice", speed=0.9)
    events, calls = [], []
    started, release = asyncio.Event(), asyncio.Event()

    async def synthesize(unit, settings, rate, *, timeout):
        calls.append(settings.speed)
        started.set()
        await release.wait()
        return b"\x01\x00" * 240

    audio = renderer(cache, state, config, synthesize, events)
    config.speed = 1.2

    async def collect():
        return [chunk async for chunk in audio.chunks("one", generation=0)]

    task = asyncio.create_task(collect())
    await started.wait()
    state.clear_tool(state.bind_source(0, "clear", 1, "clear"))
    release.set()
    assert await task == []
    assert calls == [0.9]
    assert any(event == "identifier_echo_stale" for event, _ in events)
    assert any(event == "identifier_echo_synthesis_started" for event, _ in events)
    assert not any("playback" in event for event, _ in events)
    with pytest.raises(ValueError, match="vocabulary"):
        _ = [chunk async for chunk in audio.chunks("please", generation=state.generation)]
