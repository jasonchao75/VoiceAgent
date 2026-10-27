"""ASR-02: connection provenance survives old receiver tasks and SDK retries."""

import asyncio
from contextlib import asynccontextmanager

from pipecat.frames.frames import InterimTranscriptionFrame

from src.asr.source_frames import ASRStreamEpochFrame, SourceOwnedASRMixin


class Native:
    """Replace the socket only; retain task creation and source frame dispatch."""

    def __init__(self, **kwargs):
        self.frames = []
        self.receivers = []
        self.gates = []

    async def _connect(self):
        gate = asyncio.Event()
        index = len(self.gates)
        self.gates.append(gate)

        async def receive():
            await gate.wait()
            text = f"source-{index}"
            await self.push_frame(
                InterimTranscriptionFrame(
                    text,
                    "",
                    "",
                    result={
                        "event": "Update",
                        "turn_index": 0,
                        "transcript": text,
                        "audio_window_start": 0.0,
                        "audio_window_end": 1.0,
                    },
                )
            )

        self.receivers.append(asyncio.create_task(receive()))

    async def _websocket_connect(self, *args, **kwargs):
        return object()

    async def push_frame(self, frame, direction=None):
        self.frames.append(frame)


class Source(SourceOwnedASRMixin, Native):
    """Use the production mixin, with custom TD explicitly selected."""

    _td_source_mode = True


async def test_old_receiver_keeps_original_epoch_after_new_connection():
    source = Source()
    await source._connect()
    await source._connect()
    for gate in source.gates:
        gate.set()
    await asyncio.gather(*source.receivers)
    texts = [f for f in source.frames if isinstance(f, InterimTranscriptionFrame)]
    assert [f.metadata["asr_stream_epoch"] for f in texts] == [0, 1]

    from tests.test_td_runtime import coordinator

    td = coordinator()
    for frame in source.frames:
        await td.filter_provider_frame(frame)
    assert td.ledger.epoch == 1
    assert td.ledger.view().text == "source-1"


async def test_native_mode_keeps_original_sdk_frames_and_connection_flow():
    source = Source()
    source._td_source_mode = False
    await source._connect()
    source.gates[0].set()
    await asyncio.gather(*source.receivers)
    assert len(source.frames) == 1
    assert "asr_stream_epoch" not in source.frames[0].metadata
    assert "td_source_only" not in source.frames[0].metadata


async def test_socket_retry_without_connect_advances_epoch_and_fences_old_task():
    source = Source()
    await source._websocket_connect("fixture://first")
    gate = asyncio.Event()

    async def late():
        await gate.wait()
        await source.push_frame(InterimTranscriptionFrame("old", "", ""))

    old = asyncio.create_task(late())
    await source._websocket_connect("fixture://retry")
    await source.push_frame(InterimTranscriptionFrame("new", "", ""))
    gate.set()
    await old
    texts = [f for f in source.frames if isinstance(f, InterimTranscriptionFrame)]
    assert [(f.text, f.metadata["asr_stream_epoch"]) for f in texts] == [("new", 1), ("old", 0)]
    assert [f.epoch for f in source.frames if isinstance(f, ASRStreamEpochFrame)] == [0, 1]


async def test_lazy_sdk_context_retries_bind_each_actual_entry():
    source = Source()

    @asynccontextmanager
    async def connect():
        yield object()

    factory = source._source_context_connector(connect)
    for expected in [0, 1]:
        async with factory():
            await source.push_frame(InterimTranscriptionFrame("sdk", "", ""))
            assert source.frames[-1].metadata["asr_stream_epoch"] == expected


async def test_unbound_callback_never_borrows_the_current_connection_epoch():
    """A callback without inherited provenance cannot be relabelled as the active socket."""
    from contextvars import Context

    source = Source()
    await source._websocket_connect("fixture://current")

    async def unbound():
        await source.push_frame(
            InterimTranscriptionFrame(
                "unbound callback",
                "",
                "",
                result={
                    "event": "Update",
                    "turn_index": 0,
                    "transcript": "unbound callback",
                    "audio_window_start": 0.0,
                    "audio_window_end": 1.0,
                },
            )
        )

    await asyncio.create_task(unbound(), context=Context())
    frame = source.frames[-1]
    assert frame.metadata["asr_stream_epoch"] is None
    assert frame.metadata["td_source_only"] is True


async def test_unknown_connection_keeps_raw_text_and_fails_at_existing_deadline():
    """D-061: explicit unknown ownership is a retained gap, never a current or stale guess."""
    from tests.test_td_runtime import coordinator

    events = []
    td = coordinator(evidence_sink=events.append)
    errors = []

    async def error(message, **kwargs):
        errors.append(message)

    td.push_error = error
    await td.speech_started()
    frame = InterimTranscriptionFrame(
        "unbound original",
        "",
        "",
        result={
            "event": "Update",
            "turn_index": 0,
            "transcript": "unbound original",
            "audio_window_start": 0.0,
            "audio_window_end": 1.0,
        },
    )
    frame.metadata.update(td_source_only=True, asr_stream_epoch=None)
    assert await td.filter_provider_frame(frame) is True
    assert td.unranged_text == "unbound original"
    assert td.ledger.view().text == ""
    assert td._current_view().missing_reason == "unresolved_source_audio_range"
    raw = next(event for event in events if event["event"] == "unranged_transcript")
    assert raw["stream_epoch"] is None
    assert raw["reason"] == "source_connection_unavailable"
    assert raw["turn_id"] is None
    await td.filter_provider_frame(ASRStreamEpochFrame(epoch=1))
    valid = InterimTranscriptionFrame(
        "new proven source",
        "",
        "",
        result={
            "event": "Update",
            "turn_index": 0,
            "transcript": "new proven source",
            "audio_window_start": 0.0,
            "audio_window_end": 1.0,
        },
    )
    valid.metadata.update(td_source_only=True, asr_stream_epoch=1)
    await td.filter_provider_frame(valid)
    assert td._current_view().missing_reason == "unresolved_source_audio_range"
    await td.speech_stopped(1000)
    await td.advance(3500)
    assert errors == ["asr_source_evidence_unavailable"]
    assert td.responses.user_submission_count == 0


def test_source_diagnostics_are_bounded_and_do_not_break_stream():
    """A broken evidence sink cannot change ASR behavior or grow without bound."""
    source = Source()
    events = []
    source._td_diagnostic_sink = lambda kind, **fields: events.append((kind, fields))
    for _ in range(700):
        source.record_source_diagnostic("asr_audio_ingress", total_bytes=32000)
    assert len(events) == 601
    assert events[-1] == ("asr_diagnostic_limit", {"limit": 600})
    source._td_diagnostic_count = 0

    def broken(kind, **fields):
        raise RuntimeError("test storage unavailable")

    source._td_diagnostic_sink = broken
    source.record_source_diagnostic("asr_audio_ingress", total_bytes=32000)
    source._td_source_mode = False
    source._td_diagnostic_sink = lambda kind, **fields: events.append((kind, fields))
    source.record_source_diagnostic("asr_audio_ingress", total_bytes=32000)
    assert len(events) == 601
