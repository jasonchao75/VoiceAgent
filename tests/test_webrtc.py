"""Provider-free tests for session-bound Small WebRTC signaling."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aiortc import RTCPeerConnection, RTCSessionDescription
from loguru import logger as pipecat_logger
from pipecat.transports.smallwebrtc.request_handler import (
    IceCandidate,
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
)

from src.config import LLMProviderCatalog, RuntimeConfig, VoiceCatalog
from src.session import SessionRequest, SessionStore, SessionTokenError
from src.webrtc import SessionBoundSmallWebRTCHandler


class _FakeConnection:
    """Minimal connection exposing the lifecycle used by the adapter."""

    def __init__(self, pc_id: str = "peer-1") -> None:
        self.pc_id = pc_id
        self.disconnected = False

    async def disconnect(self) -> None:
        """Record deterministic cleanup."""
        self.disconnected = True


class _FakeRequestHandler:
    """Invoke callbacks without creating network sockets or provider traffic."""

    def __init__(self, *, invoke_callback: bool = True) -> None:
        self.connection = _FakeConnection()
        self.invoke_callback = invoke_callback
        self.patches: list[SmallWebRTCPatchRequest] = []
        self.closed = False
        self.requests: list[SmallWebRTCRequest] = []

    async def handle_web_request(self, request: Any, callback: Any) -> dict[str, str]:
        """Return a deterministic answer and optionally register the connection."""
        self.requests.append(request)
        if self.invoke_callback and not request.pc_id:
            await callback(self.connection)
        return {"sdp": "safe-answer", "type": "answer", "pc_id": self.connection.pc_id}

    async def handle_patch_request(self, request: SmallWebRTCPatchRequest) -> None:
        """Capture authorized candidate patches."""
        self.patches.append(request)

    async def close(self) -> None:
        """Record handler shutdown."""
        self.closed = True


class _HangingRequestHandler(_FakeRequestHandler):
    """Upstream stand-in that never finishes offer negotiation."""

    async def handle_web_request(self, request: Any, callback: Any) -> dict[str, str]:
        """Block until the adapter-enforced timeout cancels the request."""
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


async def _pending_mobile_lease(
    *,
    request: SessionRequest,
    runtime: RuntimeConfig,
    voices: VoiceCatalog,
    llms: LLMProviderCatalog,
) -> tuple[SessionStore, str]:
    """Create one provider-free pending mobile session for signaling tests."""
    store = SessionStore(token_ttl_seconds=120, max_sessions=3)
    lease = await store.create(
        request=request.model_copy(update={"session_type": "mobile_web_call"}),
        runtime=runtime,
        voice_catalog=voices,
        llm_catalog=llms,
    )
    return store, lease.token


@pytest.mark.asyncio
async def test_offer_claims_once_and_patch_requires_matching_peer(
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> None:
    """Bind offer and PATCH to one capability without touching a paid service."""
    store, token = await _pending_mobile_lease(
        request=session_request,
        runtime=runtime_config,
        voices=voice_catalog,
        llms=llm_catalog,
    )
    upstream = _FakeRequestHandler()
    adapter = SessionBoundSmallWebRTCHandler(session_store=store, handler=upstream)
    hold = asyncio.Event()

    async def run_connection(_lease: Any, _connection: Any) -> None:
        await hold.wait()

    answer = await adapter.offer(
        capability=token,
        request=SmallWebRTCRequest(sdp="sentinel-private-sdp", type="offer"),
        run_connection=run_connection,
    )
    assert answer == {"sdp": "safe-answer", "type": "answer", "pc_id": "peer-1"}
    assert await store.counts() == (0, 1)

    patch = SmallWebRTCPatchRequest(
        pc_id="peer-1",
        candidates=[IceCandidate(candidate="", sdp_mid="0", sdp_mline_index=0)],
    )
    await adapter.patch(capability=token, request=patch)
    assert upstream.patches == [patch]

    with pytest.raises(PermissionError, match="authorization"):
        await adapter.patch(
            capability=token,
            request=SmallWebRTCPatchRequest(pc_id="other-peer", candidates=[]),
        )
    with pytest.raises(SessionTokenError):
        await adapter.offer(
            capability=token,
            request=SmallWebRTCRequest(sdp="second-offer", type="offer"),
            run_connection=run_connection,
        )

    await adapter.close()
    assert upstream.closed is True
    assert upstream.connection.disconnected is True
    assert await store.counts() == (0, 0)


@pytest.mark.asyncio
async def test_restart_offer_reuses_binding_without_reclaiming_or_starting_pipeline(
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> None:
    """Authorize Pipecat ICE restart against the existing capability and peer."""
    store, token = await _pending_mobile_lease(
        request=session_request,
        runtime=runtime_config,
        voices=voice_catalog,
        llms=llm_catalog,
    )
    upstream = _FakeRequestHandler()
    adapter = SessionBoundSmallWebRTCHandler(session_store=store, handler=upstream)
    hold = asyncio.Event()
    runner_count = 0

    async def run_connection(_lease: Any, _connection: Any) -> None:
        nonlocal runner_count
        runner_count += 1
        await hold.wait()

    await adapter.offer(
        capability=token,
        request=SmallWebRTCRequest(sdp="first", type="offer"),
        run_connection=run_connection,
    )
    answer = await adapter.offer(
        capability=token,
        request=SmallWebRTCRequest(
            sdp="restart",
            type="offer",
            pc_id="peer-1",
            restart_pc=True,
        ),
        run_connection=run_connection,
    )
    await asyncio.sleep(0)
    assert answer["pc_id"] == "peer-1"
    assert runner_count == 1
    assert await store.counts() == (0, 1)
    assert len(upstream.requests) == 2

    await adapter.offer(
        capability=token,
        request=SmallWebRTCRequest(
            sdp="renegotiate",
            type="offer",
            pc_id="peer-1",
            restart_pc=False,
        ),
        run_connection=run_connection,
    )
    assert runner_count == 1
    assert len(upstream.requests) == 3

    with pytest.raises(SessionTokenError, match="authorization"):
        await adapter.offer(
            capability=token,
            request=SmallWebRTCRequest(
                sdp="wrong-peer",
                type="offer",
                pc_id="peer-2",
                restart_pc=True,
            ),
            run_connection=run_connection,
        )
    assert len(upstream.requests) == 3
    await adapter.close()


@pytest.mark.asyncio
async def test_answer_without_pipeline_registration_is_rejected_and_released(
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> None:
    """Reject the upstream failure mode that returns an answer without a Bot task."""
    store, token = await _pending_mobile_lease(
        request=session_request,
        runtime=runtime_config,
        voices=voice_catalog,
        llms=llm_catalog,
    )
    upstream = _FakeRequestHandler(invoke_callback=False)
    adapter = SessionBoundSmallWebRTCHandler(session_store=store, handler=upstream)

    async def run_connection(_lease: Any, _connection: Any) -> None:
        raise AssertionError("The upstream callback should not run")

    with pytest.raises(RuntimeError, match="registration"):
        await adapter.offer(
            capability=token,
            request=SmallWebRTCRequest(sdp="sentinel-private-sdp", type="offer"),
            run_connection=run_connection,
        )

    assert await store.counts() == (0, 0)
    await adapter.close()


@pytest.mark.asyncio
async def test_offer_timeout_releases_pending_session(
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> None:
    """Bound a stalled upstream negotiation and clear the claimed credential lease."""
    store, token = await _pending_mobile_lease(
        request=session_request,
        runtime=runtime_config,
        voices=voice_catalog,
        llms=llm_catalog,
    )
    adapter = SessionBoundSmallWebRTCHandler(
        session_store=store,
        handler=_HangingRequestHandler(),
        offer_timeout_seconds=0.01,
    )

    async def run_connection(_lease: Any, _connection: Any) -> None:
        raise AssertionError("A stalled offer must not start the pipeline")

    with pytest.raises(TimeoutError):
        await adapter.offer(
            capability=token,
            request=SmallWebRTCRequest(sdp="sentinel-private-sdp", type="offer"),
            run_connection=run_connection,
        )
    assert await store.counts() == (0, 0)
    await adapter.close()


@pytest.mark.asyncio
async def test_connection_failure_disconnects_peer_and_releases_capacity(
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> None:
    """Release the peer and active lease when ICE/media startup fails."""
    store, token = await _pending_mobile_lease(
        request=session_request,
        runtime=runtime_config,
        voices=voice_catalog,
        llms=llm_catalog,
    )
    upstream = _FakeRequestHandler()
    adapter = SessionBoundSmallWebRTCHandler(session_store=store, handler=upstream)

    async def run_connection(_lease: Any, _connection: Any) -> None:
        raise ConnectionError("simulated ICE/media failure")

    await adapter.offer(
        capability=token,
        request=SmallWebRTCRequest(sdp="sentinel-private-sdp", type="offer"),
        run_connection=run_connection,
    )
    for _ in range(20):
        if await store.counts() == (0, 0):
            break
        await asyncio.sleep(0)
    assert await store.counts() == (0, 0)
    assert upstream.connection.disconnected is True
    await adapter.close()


@pytest.mark.asyncio
async def test_real_local_offer_patch_and_sensitive_logs_are_suppressed(
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> None:
    """Exercise the pinned aiortc/Pipecat handshake without provider traffic."""
    store, token = await _pending_mobile_lease(
        request=session_request,
        runtime=runtime_config,
        voices=voice_catalog,
        llms=llm_catalog,
    )
    adapter = SessionBoundSmallWebRTCHandler(session_store=store)
    client = RTCPeerConnection()
    restart_client: RTCPeerConnection | None = None
    client.createDataChannel("rtvi-ai")
    client.addTransceiver("audio", direction="sendrecv")
    offer = await client.createOffer()
    await client.setLocalDescription(offer)
    messages: list[str] = []
    sink_id = pipecat_logger.add(messages.append, level="DEBUG")
    hold = asyncio.Event()

    async def run_connection(_lease: Any, _connection: Any) -> None:
        await hold.wait()

    try:
        answer = await asyncio.wait_for(
            adapter.offer(
                capability=token,
                request=SmallWebRTCRequest(
                    sdp=client.localDescription.sdp,
                    type=client.localDescription.type,
                ),
                run_connection=run_connection,
            ),
            timeout=10,
        )
        await client.setRemoteDescription(
            RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
        )
        await adapter.patch(
            capability=token,
            request=SmallWebRTCPatchRequest(
                pc_id=answer["pc_id"],
                candidates=[IceCandidate(candidate="", sdp_mid="0", sdp_mline_index=0)],
            ),
        )
        restart_client = RTCPeerConnection()
        restart_client.createDataChannel("rtvi-ai")
        restart_client.addTransceiver("audio", direction="sendrecv")
        restart_offer = await restart_client.createOffer()
        await restart_client.setLocalDescription(restart_offer)
        restart_answer = await adapter.offer(
            capability=token,
            request=SmallWebRTCRequest(
                sdp=restart_client.localDescription.sdp,
                type=restart_client.localDescription.type,
                pc_id=answer["pc_id"],
                restart_pc=True,
            ),
            run_connection=run_connection,
        )
        assert restart_answer["pc_id"] != answer["pc_id"]
        await restart_client.setRemoteDescription(
            RTCSessionDescription(sdp=restart_answer["sdp"], type=restart_answer["type"])
        )
        await adapter.patch(
            capability=token,
            request=SmallWebRTCPatchRequest(pc_id=restart_answer["pc_id"], candidates=[]),
        )
        with pytest.raises(PermissionError, match="authorization"):
            await adapter.patch(
                capability=token,
                request=SmallWebRTCPatchRequest(pc_id=answer["pc_id"], candidates=[]),
            )
        malformed_store, malformed_token = await _pending_mobile_lease(
            request=session_request,
            runtime=runtime_config,
            voices=voice_catalog,
            llms=llm_catalog,
        )
        malformed_adapter = SessionBoundSmallWebRTCHandler(session_store=malformed_store)
        sentinel = "sentinel-private-type"
        with pytest.raises(ValueError, match="type"):
            await malformed_adapter.offer(
                capability=malformed_token,
                request=SmallWebRTCRequest(sdp="private-sdp", type=sentinel),
                run_connection=run_connection,
            )
        await malformed_adapter.close()
        assert sentinel not in "".join(messages)
        assert "candidate:" not in "".join(messages)
    finally:
        pipecat_logger.remove(sink_id)
        if restart_client is not None:
            await restart_client.close()
        await client.close()
        await adapter.close()
