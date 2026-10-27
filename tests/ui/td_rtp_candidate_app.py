"""D-064 finite loopback RTP candidate fixture; no providers, keys or product route."""

import asyncio
import json
import math
import struct

from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from aiortc.rtp import RtpPacket, is_rtcp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from td_rtp_serial_fixture import SerialRTCFixture

from src.pipeline.rtp_mapping import MappedOpusEncoder, MappedRawAudioTrack, RTPTaskLedger

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5177"],
    allow_methods=["POST"],
    allow_headers=["content-type"],
)
peers: set[RTCPeerConnection] = set()
serial_session: SerialRTCFixture | None = None


@app.post("/serial-offer/{scenario}")
async def serial_offer(scenario: str, data: dict) -> dict:
    """Create one explicitly selected finite serial-actor candidate."""
    global serial_session
    if serial_session:
        await serial_session.close()
    serial_session = SerialRTCFixture(scenario)
    return await serial_session.answer(data)


@app.post("/serial-result")
async def serial_result() -> dict:
    """Return actual actor and renderer evidence before fixture cleanup."""
    return serial_session.result() if serial_session else {}


@app.post("/offer")
async def offer(data: dict, timeout: float = 8.0, candidate_diagnostic: bool = False) -> dict:
    """Answer only the local candidate's offer, sending synthetic PCM through RTP.

    Args:
        data: Loopback offer from the finite browser test.
        timeout: Bound for local SDP setup; no remote provider is used.

    Returns:
        Local SDP and immutable source descriptions for the test assertions.
    """
    peer = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    peers.add(peer)
    ledger = RTPTaskLedger()

    class LimitedTrack(MappedRawAudioTrack):
        """D-066 caps source samples independently of browser wall-clock cleanup."""

        async def recv(self):
            """Stop before emitting more than one second of native source media."""
            if self._timestamp >= 24000:
                raise MediaStreamError
            return await super().recv()

    track_type = LimitedTrack if candidate_diagnostic else MappedRawAudioTrack
    track = track_type(24000, ledger)
    # This deliberately creates a mixed codec packet at the 30ms task boundary.
    for task, frequency in (("partial-A", 1000), ("final-B", 3000)):
        pcm = b"".join(
            struct.pack("<h", round(10000 * math.sin(n * 2 * math.pi * frequency / 24000)))
            for n in range(720)
        )
        track.add_task_audio(pcm, task)
    sender = peer.addTrack(track)
    sender._RTCRtpSender__encoder = MappedOpusEncoder(ledger)
    records: list[dict] = []
    channels = []
    original_send = sender.transport._send_rtp

    async def send_rtp(payload: bytes) -> None:
        """Observe the native serialized wire packet, with control records only."""
        if not is_rtcp(payload):
            mapping = ledger.bind_rtp(RtpPacket.parse(payload))
            records.append(mapping)
            for channel in channels:
                if channel.readyState == "open":
                    channel.send(json.dumps({"event": "mapping", "mapping": mapping}))
        await original_send(payload)

    sender.transport._send_rtp = send_rtp

    @peer.on("datachannel")
    def on_channel(channel):
        """Control sidecar carries hashes/ranges only; all audio remains RTP."""

        @channel.on("message")
        def message(value):
            """Browser requests the already recorded sidecar after channel readiness."""
            if value == "ready" and channel not in channels:
                channels.append(channel)
                for mapping in records:
                    channel.send(json.dumps({"event": "mapping", "mapping": mapping}))

    async with asyncio.timeout(timeout):
        await peer.setRemoteDescription(RTCSessionDescription(**data))
        await peer.setLocalDescription(await peer.createAnswer())
    return {"sdp": peer.localDescription.sdp, "type": peer.localDescription.type}


@app.post("/close")
async def close() -> dict:
    """Release all peers owned by this isolated fixture."""
    await asyncio.gather(*(peer.close() for peer in list(peers)))
    peers.clear()
    global serial_session
    if serial_session:
        await serial_session.close()
        serial_session = None
    return {"closed": True}
