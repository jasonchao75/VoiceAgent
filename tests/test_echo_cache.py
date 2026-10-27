"""CACHE-01/02/03: durable versioned assets, exact fingerprints and PCM composition."""

from importlib import import_module, util

import pytest

from src.config import TTSConfig


def cache(path):
    """Require the production asynchronous resource store."""
    assert util.find_spec("src.tts.echo_cache") is not None, "Permanent echo cache absent"
    return import_module("src.tts.echo_cache").EchoAudioCache(path)


def tts():
    """Explicit test-only voice settings; no credential or provider request."""
    return TTSConfig(voice="fixture-voice")


async def test_durable_units_deduplicate_generation_but_not_playback(tmp_path):
    store = cache(tmp_path)
    calls = []

    async def synthesize(unit, config, sample_rate, *, timeout):
        calls.append(unit)
        return b"\x01\x00" * 240

    rows = await store.prepare("bot", ["1", "1", "2"], tts(), 24000, synthesize, timeout=2)
    assert calls == ["1", "2"] and all(row.status == "ready" for row in rows)
    restarted = cache(tmp_path)
    manifest = await restarted.manifest("bot", ["1", "2"], tts(), 24000)
    pcm = await restarted.compose(manifest, ["1", "1", "2"], sample_rate=24000, gap_ms=50)
    assert (
        pcm
        == b"\x01\x00" * 240
        + b"\x00\x00" * 1200
        + b"\x01\x00" * 240
        + b"\x00\x00" * 1200
        + b"\x01\x00" * 240
    )
    await restarted.prepare("bot", ["1", "2"], tts(), 24000, synthesize, timeout=2)
    assert calls == ["1", "2"]


async def test_config_fingerprint_and_published_manifest_never_borrow_new_voice(tmp_path):
    store = cache(tmp_path)

    async def synthesize(unit, config, sample_rate, *, timeout):
        return (b"\x01\x00" if config.voice == "fixture-voice" else b"\x02\x00") * 100

    await store.prepare("bot", ["1"], tts(), 24000, synthesize, timeout=2)
    frozen = await store.manifest("bot", ["1"], tts(), 24000)
    changed = tts().model_copy(update={"voice": "different"})
    with pytest.raises(ValueError, match="missing"):
        await store.manifest("bot", ["1"], changed, 24000)
    await store.prepare("bot", ["1"], changed, 24000, synthesize, timeout=2)
    assert await store.compose(frozen, ["1"], sample_rate=24000, gap_ms=0) == b"\x01\x00" * 100
    ordinary_speed = tts().model_copy(update={"dynamic_speed_enabled": True, "speed_step": 0.2})
    assert await store.manifest("bot", ["1"], ordinary_speed, 24000) == frozen


async def test_failed_unit_retry_does_not_regenerate_successes_and_corruption_blocks_publish(
    tmp_path,
):
    store = cache(tmp_path)
    failing = True
    calls = []

    async def synthesize(unit, config, sample_rate, *, timeout):
        calls.append(unit)
        if unit == "2" and failing:
            raise TimeoutError("fixture")
        return b"\x01\x00" * 10

    rows = await store.prepare("bot", ["1", "2"], tts(), 24000, synthesize, timeout=2)
    assert [row.status for row in rows] == ["ready", "failed"]
    with pytest.raises(ValueError, match="missing"):
        await store.manifest("bot", ["1", "2"], tts(), 24000)
    failing = False
    rows = await store.prepare("bot", ["1", "2"], tts(), 24000, synthesize, timeout=2)
    assert calls == ["1", "2", "2"]
    asset = rows[0]
    asset.path.write_bytes(b"\x02\x00")
    with pytest.raises(ValueError, match="missing"):
        await store.manifest("bot", ["1", "2"], tts(), 24000)


async def test_runtime_repair_is_bounded_deduplicated_and_uses_frozen_settings(tmp_path):
    import asyncio

    store = cache(tmp_path)
    calls = []

    async def synthesize(unit, config, sample_rate, *, timeout):
        calls.append((unit, config.speed))
        await asyncio.sleep(0)
        return b"\x01\x00" * 10

    frozen = tts().model_copy(update={"speed": 0.9})
    outputs = await asyncio.gather(
        *[store.resolve("bot", "1", frozen, 24000, synthesize, timeout=2) for _ in range(3)]
    )
    assert calls == [("1", 0.9)]
    assert all(pcm == b"\x01\x00" * 10 and repaired for pcm, repaired in outputs)
    assert await store.resolve("bot", "1", frozen, 24000, synthesize, timeout=2) == (
        b"\x01\x00" * 10,
        False,
    )


async def test_async_preparation_captures_settings_before_first_io(tmp_path):
    """A draft edit cannot retarget an already requested batch's voice/speed fingerprint."""
    import asyncio

    store = cache(tmp_path)
    requested = tts()
    frozen = requested.model_copy(deep=True)

    async def synthesize(unit, config, sample_rate, *, timeout):
        return b"\x01\x00" * 10

    job = asyncio.create_task(store.prepare("bot", ["1"], requested, 24000, synthesize, timeout=2))
    await asyncio.sleep(0)
    requested.speed = 1.2
    await job
    assert await store.manifest("bot", ["1"], frozen, 24000)


async def test_cancelled_waiter_does_not_repeat_an_already_sent_synthesis(tmp_path):
    """Once requested, bounded synthesis settles and can serve another session waiting on it."""
    import asyncio

    store = cache(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def synthesize(unit, config, sample_rate, *, timeout):
        calls.append(unit)
        entered.set()
        await release.wait()
        return b"\x01\x00" * 10

    request = asyncio.create_task(store.resolve("bot", "1", tts(), 24000, synthesize, timeout=2))
    await entered.wait()
    request.cancel()
    await asyncio.gather(request, return_exceptions=True)
    following = asyncio.create_task(store.resolve("bot", "1", tts(), 24000, synthesize, timeout=2))
    release.set()
    await following
    await store.close()
    assert calls == ["1"]
    assert await store.manifest("bot", ["1"], tts(), 24000)


async def test_asset_write_failure_is_a_failed_unit_not_a_fake_ready_row(tmp_path, monkeypatch):
    """A synthesis response alone is insufficient if its permanent file could not be stored."""
    store = cache(tmp_path)

    async def synthesize(unit, config, sample_rate, *, timeout):
        return b"\x01\x00" * 10

    def fail_replace(*args):
        raise OSError("fixture-write-failure")

    monkeypatch.setattr(import_module("src.tts.echo_cache").os, "replace", fail_replace)
    rows = await store.prepare("bot", ["1"], tts(), 24000, synthesize, timeout=2)
    assert rows[0].status == "failed" and rows[0].error == "OSError"
    assert rows[0].public()["url"] is None
