"""Provider-free pipeline assembly and opening behavior smoke tests."""

from __future__ import annotations

from typing import Any

import pytest
from pipecat.frames.frames import TTSSpeakFrame

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

    def create(self, **_kwargs: Any) -> object:
        """Return the marker without a paid provider call."""
        return self.marker


@pytest.mark.asyncio
@pytest.mark.parametrize("opening_script, expected_frames", [("Hello there.", 1), ("", 0)])
async def test_pipeline_order_and_opening_behavior_without_paid_apis(
    monkeypatch: pytest.MonkeyPatch,
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
    opening_script: str,
    expected_frames: int,
) -> None:
    """Build the seven-stage cascade and verify assistant-first/user-first behavior."""
    store = SessionStore(token_ttl_seconds=120, max_sessions=1)
    pending = await store.create(
        request=session_request,
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

    monkeypatch.setattr(voice_agent, "FastAPIWebsocketTransport", lambda **_kwargs: fake_transport)
    monkeypatch.setattr(voice_agent, "create_flux_stt", lambda **_kwargs: stt)
    monkeypatch.setattr(voice_agent, "create_openai_compatible_llm", lambda **_kwargs: llm)
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

    await voice_agent.run_voice_agent_session(
        websocket=object(),
        lease=lease,
        runtime=runtime_config,
        tts_registry=_FakeRegistry(tts),  # type: ignore[arg-type]
        allowed_origins=["http://localhost:8000"],
        event_buffer=SessionEventBuffer(),
    )

    assert captured_pipeline == [
        fake_transport.input_processor,
        stt,
        user_aggregator,
        llm,
        tts,
        fake_transport.output_processor,
        assistant_aggregator,
    ]
    assert len(fake_worker.queued) == expected_frames
    if opening_script:
        assert isinstance(fake_worker.queued[0], TTSSpeakFrame)
        assert fake_context.messages == [{"role": "assistant", "content": opening_script}]
    else:
        assert fake_context.messages == []

    await store.close(lease.session_id)
