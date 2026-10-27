"""D-064 isolated task writer for RTP, with control-only sample extent manifests."""

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

from src.pipeline.audio_identity import TaskAudioFrame
from src.pipeline.rtp_mapping import MappedRawAudioTrack
from src.pipeline.webrtc_cancel import clear_pending_rtp_audio

logger = logging.getLogger(__name__)


class RTPCandidateWriter:
    """Preserve source identity without claiming that queueing or EOS is playback."""

    def __init__(self, track: MappedRawAudioTrack, control: Callable[[dict], None]) -> None:
        """Bind one native track and a non-audio control sink for this candidate."""
        self.track = track
        self._control = control
        self._totals: dict[str, int] = {}
        self._closed: set[str] = set()
        self._ended: set[str] = set()

    def audio(self, frame: TaskAudioFrame) -> Any:
        """Queue only explicitly bound mono PCM at the track's own rate.

        Raises:
            ValueError: If the exact source format cannot be proven.
        """
        if (
            not isinstance(frame, TaskAudioFrame)
            or frame.sample_rate != self.track._sample_rate
            or frame.num_channels != 1
            or len(frame.audio) % 2
        ):
            raise ValueError("Candidate RTP source format or identity is unproven")
        identity = str(frame.task_identity["playback_id"])
        if identity in self._closed or identity in self._ended:
            return
        waiter = self.track.add_task_audio(frame.audio, identity)
        self._totals[identity] = self._totals.get(identity, 0) + (
            len(frame.audio) // 2 * (48000 // frame.sample_rate)
        )

        return waiter

    def control(self, message: dict[str, Any]) -> None:
        """Emit source extent or a stop request, never a renderer acknowledgement."""
        identity = message.get("playback_id")
        if not isinstance(identity, str) or not identity or len(identity) > 128:
            raise ValueError("Invalid candidate control identity")
        if message.get("event") == "task_end":
            if identity in self._ended or identity in self._closed:
                return
            self._ended.add(identity)
            self._control({**message, "expected_samples": self._totals.get(identity, 0)})
        elif message.get("event") == "stop_task":
            self._closed.add(identity)
            clear_pending_rtp_audio(self.track)
            self._control(dict(message))


def bind_candidate_output(
    output: Any,
    track: MappedRawAudioTrack,
    control: Callable[[dict], None],
) -> RTPCandidateWriter:
    """Bind a development output instance without replacing its native input.

    Args:
        output: Existing SmallWebRTC output transport instance.
        track: Its mapped native RTP source, installed before output starts.
        control: Connection-local metadata sender; never carries audio bytes.

    Returns:
        Writer that owns exact task extents for this output instance.

    Raises:
        ValueError: If source audio format or task identity cannot be proven.
    """
    writer = RTPCandidateWriter(track, control)
    original_message = output.send_message

    async def write(frame: Any) -> bool:
        """Preserve the original task subclass across the SDK byte-only boundary."""
        waiter = writer.audio(frame)
        if inspect.isawaitable(waiter):
            return bool(await waiter)
        return True

    async def message(frame: Any) -> None:
        """Keep unrelated SDK messages on their original native path."""
        data = frame.message
        if isinstance(data, dict) and data.get("label") == "voice-agent-playback":
            writer.control(data)
        else:
            await original_message(frame)

    output.write_audio_frame = write
    output.send_message = message
    return writer


def install_candidate_transport(transport: Any, connection: Any) -> None:
    """Install the RTP sidecar before native connection readiness in development.

    Args:
        transport: Existing native SmallWebRTC transport, not yet started.
        connection: Its negotiated connection and original RTP sender.

    Raises:
        RuntimeError: If pinned SDK sender ownership cannot be proven.
    """
    from aiortc.rtp import RtpPacket, is_rtcp

    from src.pipeline.rtp_mapping import MappedOpusEncoder, RTPTaskLedger

    original_replace = connection.replace_audio_track
    ledger = RTPTaskLedger()
    control_ready = asyncio.Event()
    close_task: asyncio.Task[None] | None = None

    def control_timeout() -> None:
        """Close outside the sender task, since peer.close waits for that sender to stop."""
        nonlocal close_task
        logger.error(
            "playback_control_timeout connection_id=%s", getattr(connection, "_pc_id", "unknown")
        )

        async def close_connection() -> None:
            """Own and consume disconnect errors rather than leaving an orphan task."""
            try:
                await connection.disconnect()
            except Exception:
                logger.exception("playback_control_timeout_cleanup_failed")

        if close_task is None:
            close_task = asyncio.create_task(close_connection())

    def observe_channel(channel: Any) -> None:
        """Do not produce RTP before the reliable ownership channel can carry its evidence."""
        if channel.readyState == "open":
            control_ready.set()
        else:
            channel.on("open", control_ready.set)

    connection._pc.on("datachannel", observe_channel)
    if getattr(connection, "_data_channel", None) is not None:
        observe_channel(connection._data_channel)

    def control(message: dict) -> None:
        """Use the existing app-message channel for metadata only."""
        connection.send_app_message({"label": "voice-agent-playback", **message})

    def replace(track: Any) -> None:
        """Attach provenance before the native sender can consume the new track."""
        transceivers = connection._pc.getTransceivers()
        audio = [item.sender for item in transceivers if item.kind == "audio"]
        if len(audio) != 1:
            raise RuntimeError("Candidate RTP audio sender ownership is unproven")
        sender = audio[0]
        mapped = MappedRawAudioTrack(
            track._sample_rate, ledger, ready=control_ready, on_ready_timeout=control_timeout
        )
        sender._RTCRtpSender__encoder = MappedOpusEncoder(ledger)
        original_send = sender.transport._send_rtp

        async def send(payload: bytes) -> None:
            """Bind the exact serialized native packet before forwarding unchanged."""
            if not is_rtcp(payload):
                control({"event": "mapping", "mapping": ledger.bind_rtp(RtpPacket.parse(payload))})
            await original_send(payload)

        sender.transport._send_rtp = send
        transport._client._audio_output_track = mapped
        bind_candidate_output(transport.output(), mapped, control)
        original_replace(mapped)
        track.stop()

    connection.replace_audio_track = replace
