"""Actual local Pipecat unit-rendering lifecycle without a paid TTS connection."""

from importlib import import_module, util

import pytest
from pipecat.frames.frames import TTSAudioRawFrame, TTSSpeakFrame, TTSStoppedFrame
from pipecat.processors.frame_processor import FrameProcessor

from src.config import TTSConfig


async def test_unit_renderer_reports_upstream_provider_error_without_waiting_for_timeout():
    """SDK push_error goes upstream; a downstream-only sink cannot observe it."""
    from src.tts.unit_synthesis import synthesize_unit

    class FailingSynth(FrameProcessor):
        """Use the actual SDK upstream error path, without any vendor connection."""

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, TTSSpeakFrame):
                await self.push_error(error_msg="sensitive-provider-detail-must-not-leak")
            else:
                await self.push_frame(frame, direction)

    class Registry:
        def create(self, **kwargs):
            return FailingSynth()

    with pytest.raises(ValueError, match="TTS synthesis failed"):
        await synthesize_unit(
            Registry(),
            "inert-key",
            "one",
            TTSConfig(voice="fixture"),
            24000,
            timeout=0.3,
        )


async def test_unit_renderer_bounds_sdk_setup_and_releases_partial_resources():
    """The real worker must close a partially connected processor when setup times out."""
    import asyncio
    import time

    from src.tts.unit_synthesis import synthesize_unit

    resources = {"open": False}

    class SlowSetup(FrameProcessor):
        """Model a socket opened before a provider's ready signal, without any network."""

        async def setup(self, setup):
            await super().setup(setup)
            resources["open"] = True
            await asyncio.Event().wait()

        async def cleanup(self):
            resources["open"] = False
            await super().cleanup()

    class Registry:
        def create(self, **kwargs):
            return SlowSetup()

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await synthesize_unit(
            Registry(),
            "inert-key",
            "one",
            TTSConfig(voice="fixture"),
            24000,
            timeout=0.1,
        )
    assert resources["open"] is False
    assert time.monotonic() - started < 1


@pytest.mark.parametrize("sample_rate,fail", [(24000, False), (16000, True)])
async def test_unit_renderer_uses_fixed_settings_and_validates_actual_pcm(sample_rate, fail):
    assert util.find_spec("src.tts.unit_synthesis") is not None, "Fixed-unit renderer absent"
    module = import_module("src.tts.unit_synthesis")
    observed = []

    class Synth(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, TTSSpeakFrame):
                await self.push_frame(TTSAudioRawFrame(b"\x01\x00" * 100, sample_rate, 1))
                await self.push_frame(TTSStoppedFrame())
            else:
                await self.push_frame(frame, direction)

    class Registry:
        def create(self, **kwargs):
            observed.append(kwargs["config"])
            return Synth()

    config = TTSConfig(voice="fixture", speed=0.9, dynamic_speed_enabled=True)
    if fail:
        with pytest.raises(ValueError, match="format"):
            await module.synthesize_unit(Registry(), "inert-key", "1", config, 24000, timeout=2)
    else:
        pcm = await module.synthesize_unit(Registry(), "inert-key", "1", config, 24000, timeout=2)
        assert pcm == b"\x01\x00" * 100
    assert observed[0].speed == 0.9 and not observed[0].dynamic_speed_enabled
