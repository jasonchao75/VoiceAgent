"""Provider-free pipeline assembly and opening behavior smoke tests."""

from __future__ import annotations

from typing import Any

import pytest
from pipecat.frames.frames import TTSSpeakFrame

from src.asr.factory import ASRService
from src.config import LLMProviderCatalog, RuntimeConfig, VoiceCatalog
from src.observability import SessionEventBuffer
from src.pipeline import voice_agent
from src.session import SessionRequest, SessionStore


class _Handlers:
    """Minimal Pipecat-compatible event decorator for the smoke test."""

    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}

    def event_handler(self, name: str):  # type: ignore[no-untyped-def]
        """Capture one decorated async event handler."""

        def decorator(handler):  # type: ignore[no-untyped-def]
            self.handlers[name] = handler
            return handler

        return decorator


class _FakeTransport(_Handlers):
    """Inert input/output transport used without browser audio."""

    def __init__(self) -> None:
        super().__init__()
        self.input_processor = object()
        self.output_processor = object()

    def input(self) -> object:
        """Return the input stage marker."""
        return self.input_processor

    def output(self) -> object:
        """Return the output stage marker."""
        return self.output_processor


class _FakeContext:
    """Capture context messages without an LLM."""

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def add_message(self, message: dict[str, str]) -> None:
        """Append one role/content message."""
        self.messages.append(message)


class _FakeWorker:
    """Capture queued frames and RTVI handlers."""

    def __init__(self) -> None:
        self.rtvi = _Handlers()
        self.queued: list[Any] = []
        self.cancelled = False

    async def queue_frames(self, frames: list[Any]) -> None:
        """Capture opening frames."""
        self.queued.extend(frames)

    async def cancel(self) -> None:
        """Mark the worker cancelled."""
        self.cancelled = True


class _FakeRunner:
    """Trigger client-ready and finish immediately."""

    def __init__(self, **_kwargs: Any) -> None:
        self.worker: _FakeWorker | None = None

    async def add_workers(self, worker: _FakeWorker) -> None:
        """Capture the only worker."""
        self.worker = worker

    async def run(self) -> None:
        """Simulate RTVI readiness without provider connections."""
        assert self.worker is not None
        await self.worker.rtvi.handlers["on_client_ready"](self.worker.rtvi)


class _FakeRegistry:
    """Return an inert TTS stage marker."""

    def __init__(self, marker: object) -> None:
        self.marker = marker
        self.calls = 0

    def create(self, **_kwargs: Any) -> object:
        """Return the marker without a paid provider call."""
        self.calls += 1
        return self.marker


def test_small_webrtc_transport_uses_shared_audio_contract(
    monkeypatch: pytest.MonkeyPatch,
    runtime_config: RuntimeConfig,
) -> None:
    """Build Small WebRTC with the exact PCM rates consumed by the shared pipeline."""
    captured: dict[str, object] = {}

    def fake_transport_factory(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(voice_agent, "SmallWebRTCTransport", fake_transport_factory)
    connection = object()
    transport = voice_agent.create_small_webrtc_transport(
        connection=connection,  # type: ignore[arg-type]
        runtime=runtime_config,
    )

    assert transport is not None
    assert captured["webrtc_connection"] is connection
    params = captured["params"]
    assert params.audio_in_enabled is True
    assert params.audio_out_enabled is True
    assert params.audio_in_sample_rate == runtime_config.audio.input_sample_rate
    assert params.audio_out_sample_rate == runtime_config.audio.output_sample_rate
    assert params.audio_in_channels == runtime_config.audio.channels
    assert params.audio_out_channels == runtime_config.audio.channels


@pytest.mark.asyncio
@pytest.mark.parametrize("opening_script, expected_frames", [("Hello there.", 1), ("", 0)])
@pytest.mark.parametrize(
    "session_type, expected_audio_input, expected_stt_calls",
    [("web_call", True, 1), ("chat_test", False, 0)],
)
async def test_pipeline_order_and_opening_behavior_without_paid_apis(
    monkeypatch: pytest.MonkeyPatch,
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
    opening_script: str,
    expected_frames: int,
    session_type: str,
    expected_audio_input: bool,
    expected_stt_calls: int,
) -> None:
    """Build the mode-specific cascade and verify opening behavior without providers."""
    request = session_request.model_copy(update={"session_type": session_type})
    store = SessionStore(token_ttl_seconds=120, max_sessions=1)
    pending = await store.create(
        request=request,
        runtime=runtime_config,
        voice_catalog=voice_catalog,
        llm_catalog=llm_catalog,
    )
    lease = await store.claim(pending.token)
    lease.config = lease.config.model_copy(update={"opening_script": opening_script})

    fake_transport = _FakeTransport()
    fake_context = _FakeContext()
    fake_worker = _FakeWorker()
    stt, user_aggregator, llm, tts, assistant_aggregator = (object() for _ in range(5))
    captured_pipeline: list[object] = []
    captured_transport_params: list[Any] = []

    def fake_transport_factory(**kwargs: Any) -> _FakeTransport:
        captured_transport_params.append(kwargs["params"])
        return fake_transport

    monkeypatch.setattr(voice_agent, "FastAPIWebsocketTransport", fake_transport_factory)
    monkeypatch.setattr(voice_agent, "create_llm_service", lambda **_kwargs: llm)
    monkeypatch.setattr(voice_agent, "LLMContext", lambda: fake_context)
    monkeypatch.setattr(
        voice_agent,
        "LLMContextAggregatorPair",
        lambda _context: (user_aggregator, assistant_aggregator),
    )
    monkeypatch.setattr(
        voice_agent,
        "Pipeline",
        lambda processors: captured_pipeline.extend(processors),
    )
    monkeypatch.setattr(voice_agent, "PipelineWorker", lambda *_args, **_kwargs: fake_worker)
    monkeypatch.setattr(voice_agent, "WorkerRunner", _FakeRunner)

    asr_registry = _FakeRegistry(ASRService(processor=stt))
    await voice_agent.run_voice_agent_session(
        websocket=object(),
        lease=lease,
        runtime=runtime_config,
        asr_registry=asr_registry,
        tts_registry=_FakeRegistry(tts),
        allowed_origins=["http://localhost:8000"],
        event_buffer=SessionEventBuffer(),
    )

    expected_pipeline = [
        fake_transport.input_processor,
        user_aggregator,
        llm,
        tts,
        fake_transport.output_processor,
        assistant_aggregator,
    ]
    if session_type == "web_call":
        expected_pipeline.insert(1, stt)
    assert captured_pipeline == expected_pipeline
    assert captured_transport_params[0].audio_in_enabled is expected_audio_input
    assert asr_registry.calls == expected_stt_calls
    assert len(fake_worker.queued) == expected_frames
    if opening_script:
        assert isinstance(fake_worker.queued[0], TTSSpeakFrame)
        assert fake_context.messages == [{"role": "assistant", "content": opening_script}]
    else:
        assert fake_context.messages == []

    await store.close(lease.session_id)


@pytest.mark.parametrize("with_identifier", [False, True])
@pytest.mark.parametrize("playback_protocol", [None, "websocket"])
async def test_custom_td_uses_local_audio_before_asr_and_owned_aggregator(
    playback_protocol,
    tmp_path,
    with_identifier,
    monkeypatch,
    session_request,
    runtime_config,
    voice_catalog,
    llm_catalog,
):
    """The production pipeline must use the new stages, not merely expose a catalog choice."""
    from tests.test_td_config import td_settings
    from tests.test_td_rule_settings import priority_settings

    settings = td_settings()
    if with_identifier:
        settings["priority_rule"] = priority_settings()
    request = SessionRequest.model_validate(
        {
            **session_request.model_dump(),
            "turn_detection_source": "self_developed",
            "td_config": settings,
            "jev_api_key": "fixture-jev-inert-key",
        }
    )
    store = SessionStore(token_ttl_seconds=120, max_sessions=1)
    pending = await store.create(
        request=request,
        runtime=runtime_config,
        voice_catalog=voice_catalog,
        llm_catalog=llm_catalog,
    )
    lease = await store.claim(pending.token)
    transport = _FakeTransport()
    context, worker = _FakeContext(), _FakeWorker()
    stt, local_audio, user, llm, tts, assistant = [object() for _ in range(6)]
    captured = []

    class Coordinator:
        """Inert coordinator used only for production assembly verification."""

        authority = object()
        source_evidence_error = None

        def assistant_context(self, text):
            self.opening = text

    coordinator = Coordinator()

    class HTTP:
        """Record client cleanup without creating a socket."""

        closed = False

        async def aclose(self):
            self.closed = True

    http = HTTP()

    async def prepare(**kwargs):
        assert kwargs["api_key"] == "fixture-jev-inert-key"
        assert kwargs["settings"].maximum_ms == 2500
        assert (kwargs.get("bind_input") is not None) == with_identifier
        assert (kwargs.get("identifier_output") is not None) == (
            with_identifier and playback_protocol == "websocket"
        )
        return local_audio, coordinator, http

    def aggregators(actual_context, authority):
        assert actual_context is context and authority is coordinator.authority
        return user, assistant

    monkeypatch.setattr(voice_agent, "prepare_custom_td", prepare)
    monkeypatch.setattr(voice_agent, "create_custom_aggregators", aggregators)
    captured_tools = []

    def context_factory(**kwargs):
        captured_tools.extend(kwargs.get("tools", []))
        return context

    monkeypatch.setattr(voice_agent, "LLMContext", context_factory)
    monkeypatch.setattr(voice_agent, "create_llm_service", lambda **kwargs: llm)
    monkeypatch.setattr(voice_agent, "Pipeline", lambda processors: captured.extend(processors))
    monkeypatch.setattr(voice_agent, "PipelineWorker", lambda *args, **kwargs: worker)
    monkeypatch.setattr(voice_agent, "WorkerRunner", _FakeRunner)
    from src.tts.echo_cache import EchoAudioCache

    cache = EchoAudioCache(tmp_path / "echo")
    await voice_agent.run_voice_agent_pipeline(
        playback_protocol=playback_protocol,
        echo_cache=cache,
        transport=transport,
        lease=lease,
        runtime=runtime_config,
        asr_registry=_FakeRegistry(ASRService(processor=stt)),
        tts_registry=_FakeRegistry(tts),
        event_buffer=SessionEventBuffer(),
    )
    assert captured[:6] == [transport.input_processor, local_audio, stt, coordinator, user, llm]
    from src.pipeline.audio_identity import AudioTaskTagger
    from src.pipeline.serial_output import SerialAudioOutput

    if playback_protocol == "websocket":
        assert isinstance(captured[-3], SerialAudioOutput)
        assert isinstance(captured[-4], AudioTaskTagger)
        assert captured[-5] is tts
    else:
        assert captured[-4] is tts
        assert isinstance(captured[-3], AudioTaskTagger)
    await cache.close()
    assert captured[-2:] == [transport.output_processor, assistant]
    assert http.closed
    assert coordinator.opening == request.opening_script
    assert {tool.name for tool in captured_tools} == (
        {"submit_identifier", "clear_identifier"} if with_identifier else set()
    )
    await store.close(lease.session_id)
