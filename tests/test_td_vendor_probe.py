"""R2: a real-adapter probe must be bounded before any credential or socket use."""

from importlib import import_module

import pytest


def probe():
    """Load the no-side-effect probe module."""
    return import_module("scripts.evaluation.probe_td_compatibility")


def test_plan_has_exact_data_and_public_price_connection_bound():
    """A wall-clock billable envelope is stronger than a speech-duration estimate."""
    plan = probe().build_plan()
    assert len(plan["cases"]) == plan["max_calls"] == 9
    assert {row["model"] for row in plan["cases"]} == {
        "flux-general-en",
        "flux-general-multi",
        "nova-3",
    }
    assert plan["cost_ceiling_usd"] == "0.10"
    assert plan["maximum_public_price_usd"] == "0.03510"
    assert all(row["sha256"] and row["duration_seconds"] > 0 for row in plan["cases"])


def test_diagnostic_plan_has_separate_single_connection_authorization_scope():
    """A failed batch grant cannot be reused to diagnose or replay it."""
    original = probe().build_plan()
    diagnostic = probe().build_plan(diagnostic=True)
    assert diagnostic["batch_id"] != original["batch_id"]
    assert diagnostic["request_sha256"] != original["request_sha256"]
    assert diagnostic["max_calls"] == len(diagnostic["cases"]) == 1
    assert diagnostic["cases"] == original["cases"][:1]
    assert diagnostic["cost_ceiling_usd"] == "0.02"


async def test_socket_budget_blocks_the_second_attempt_before_connecting():
    """An SDK retry is a second paid connection, even inside one processor."""
    module = probe()
    calls = []

    async def connect(*args, **kwargs):
        calls.append(True)
        return object()

    budget = module.ConnectionBudget()
    guarded = budget.async_connector(connect)
    await guarded("wss://api.deepgram.com/v2/listen")
    with pytest.raises(RuntimeError, match="budget"):
        await guarded("wss://api.deepgram.com/v2/listen")
    assert calls == [True]


def test_sdk_context_connector_also_refuses_automatic_reconnection():
    """Reserve before the lazy context enters; constructing one does not open a socket."""
    module = probe()
    calls = []
    budget = module.ConnectionBudget()
    guarded = budget.context_connector(lambda **kwargs: calls.append(True))
    guarded(model="nova-3")
    with pytest.raises(RuntimeError, match="budget"):
        guarded(model="nova-3")
    assert calls == []
    assert budget.attempts == 1


@pytest.mark.parametrize("vendor", [None, "assemblyai", "speechmatics", "soniox"])
def test_probe_cli_cannot_load_a_key_without_an_exact_confirmed_batch(
    monkeypatch,
    tmp_path,
    vendor,
):
    """Dry-run and absent authorization cannot touch the local credential."""
    import hashlib
    import json
    import wave

    module = probe()
    media = tmp_path / "inert-local.wav"
    with wave.open(str(media), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(bytes(320))
    plan = module.build_plan(single_vendor=vendor)
    for row in plan["cases"]:
        row.update(
            path=str(media),
            sha256=hashlib.sha256(media.read_bytes()).hexdigest(),
            duration_seconds=0.01,
        )
    plan.pop("request_sha256")
    plan["request_sha256"] = hashlib.sha256(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    monkeypatch.setattr(module, "build_plan", lambda **kwargs: plan)
    touched = []
    monkeypatch.setattr(module, "local_key", lambda: touched.append(True))
    assert module.main([]) == 0
    assert module.main(["--execute", "--authorization-decision", "D-999"]) == 2
    plan["cases"][0]["path"] = str(tmp_path / "missing.wav")
    assert module.main([]) == 2
    assert touched == []


@pytest.mark.parametrize("missing_range", [False, True])
async def test_real_sdk_worker_collects_production_normalization_without_a_provider(
    monkeypatch,
    tmp_path,
    missing_range,
):
    """Exercise startup, paced input, normalization, cleanup and safe result fields together."""
    import wave
    from types import SimpleNamespace

    from pipecat.frames.frames import InputAudioRawFrame, InterimTranscriptionFrame, StartFrame
    from pipecat.processors.frame_processor import FrameProcessor

    from src.asr import factory
    from src.asr.turn_events import SourceNormalizer

    module = probe()
    connected = []
    input_frames = []

    class OfflineASR(FrameProcessor):
        """Replace only the provider, leaving native worker lifecycle intact."""

        async def _websocket_connect(self, *args, **kwargs):
            """Record a local connector call; no socket is created."""
            connected.append(True)

        async def process_frame(self, frame, direction):
            """Emit one source event after real input reaches the processor."""
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                await self._websocket_connect("fixture://local")
            if isinstance(frame, InputAudioRawFrame):
                input_frames.append(True)
            if isinstance(frame, InputAudioRawFrame) and not hasattr(self, "emitted"):
                self.emitted = True
                payload = {
                    "event": "Update",
                    "turn_index": 1,
                    "transcript": "test-fixture-private-key",
                    "audio_window_start": 0,
                    "audio_window_end": 0.01,
                    "request_id": "must-not-persist",
                }
                if missing_range:
                    payload.pop("audio_window_end")
                await self.push_frame(
                    InterimTranscriptionFrame(
                        "test-fixture-private-key",
                        "",
                        "",
                        result=payload,
                    )
                )
            await self.push_frame(frame, direction)

    service = factory.ASRService(
        OfflineASR(),
        source_normalizer=SourceNormalizer(
            "deepgram",
            "flux-general-en",
        ),
    )
    monkeypatch.setattr(
        factory,
        "create_default_asr_registry",
        lambda: SimpleNamespace(
            create=lambda **kwargs: service,
        ),
    )
    path = tmp_path / "tiny.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(bytes(320))
    result = await module.run_case(
        {"id": "tiny", "model": "flux-general-en", "options": {}, "path": str(path)},
        "test-fixture-private-key",
        timeout=10,
    )
    assert result["status"] == ("transcript_or_range_missing" if missing_range else "ok")
    assert connected == [True]
    assert result["connections"] == 1
    if missing_range:
        assert len(input_frames) == 1
    else:
        assert result["events"][0]["segments"][0]["start_ms"] == 0
    assert result["events"][0]["source_evidence"]["audio_window_start"] == 0
    assert "must-not-persist" not in __import__("json").dumps(result)
    assert "test-fixture-private-key" not in __import__("json").dumps(result)


async def test_nova_context_budget_preserves_entry_and_exit():
    """The handshake bound must not accidentally become a five-second session limit."""
    from contextlib import asynccontextmanager

    events = []

    @asynccontextmanager
    async def connection(**kwargs):
        events.append("enter")
        try:
            yield "local"
        finally:
            events.append("exit")

    wrapped = probe().ConnectionBudget().context_connector(connection)
    async with wrapped(model="nova-3") as value:
        assert value == "local"
    with pytest.raises(RuntimeError, match="budget"):
        wrapped(model="nova-3")
    assert events == ["enter", "exit"]


@pytest.mark.parametrize("model", ["flux-general-en", "flux-general-multi", "nova-3"])
def test_locked_production_factory_exposes_the_guarded_connection_boundary(model):
    """Validate all actual adapter entry points without starting a network lifecycle."""
    from src.asr.factory import create_default_asr_registry
    from src.config import AudioConfig

    service = create_default_asr_registry().create(
        provider="deepgram",
        model=model,
        turn_detection_source="self_developed",
        options={"language": "en"} if model == "nova-3" else {},
        api_key="test-fixture-private-key",
        audio=AudioConfig(),
    )
    assert service.processor._td_source_mode
    if model == "nova-3":
        assert callable(service.processor._client.listen.v1.connect)
    else:
        assert callable(service.processor._websocket_connect)


def test_consumed_grant_is_rejected_without_relying_on_a_local_log(monkeypatch, tmp_path):
    """A copied workspace without claim logs still cannot replay a completed grant."""
    import json

    module = probe()
    plan = module.build_plan()
    (tmp_path / "verification").mkdir()
    (tmp_path / "decisions").mkdir()
    grant = {
        key: plan[key] for key in ("batch_id", "request_sha256", "max_calls", "cost_ceiling_usd")
    }
    grant.update(authorization_decision_id="D-777", authorization_status="confirmed")
    (tmp_path / "decisions/decision-log.md").write_text(
        "### D-777: Offline fixture\n- Status: Confirmed\n"
        "- Confirmation quote: fixture scope accepted\n- Source thread/message: fixture only\n"
    )
    monkeypatch.setattr(module, "CHANGE", tmp_path)
    for consumed in ["completed", "stopped_on_first_failure", "running_exclusive_claim"]:
        grant["execution_status"] = consumed
        (tmp_path / "verification/delivery-status.json").write_text(
            json.dumps({"external_calls": [grant]})
        )
        with pytest.raises(ValueError, match="consumed|started"):
            module.verify_authorization(plan, "D-777")
    grant["execution_status"] = "authorized_not_started"
    (tmp_path / "verification/delivery-status.json").write_text(
        json.dumps({"external_calls": [grant]})
    )
    module.verify_authorization(plan, "D-777")


def test_digits_confirmation_plan_cannot_expand_to_a_passed_case_or_other_model():
    original = probe().build_plan()
    minimal = probe().build_plan(repair_confirmation=True)
    assert minimal["max_calls"] == len(minimal["cases"]) == 1
    assert minimal["cases"][0]["id"] == "digits"
    assert minimal["cases"][0]["model"] == "flux-general-en"
    assert minimal["cases"][0]["sha256"] == original["cases"][1]["sha256"]
    assert minimal["batch_id"] != original["batch_id"]
    assert minimal["request_sha256"] != original["request_sha256"]
    assert minimal["cost_ceiling_usd"] == "0.02"
    with pytest.raises(ValueError, match="one exact"):
        probe().build_plan(diagnostic=True, repair_confirmation=True)


def test_fresh_digits_plan_does_not_reuse_consumed_media_or_authorization():
    """Use the pinned replacement sample independently of vanished old inputs."""
    module = probe()
    old = module.build_plan(repair_confirmation=True)
    plan = module.build_plan(fresh_digits=True)
    assert plan["batch_id"] == "deepgram-td-fresh-digits-confirmation-v1"
    assert plan["batch_id"] != old["batch_id"]
    assert plan["request_sha256"] != old["request_sha256"]
    assert plan["max_calls"] == len(plan["cases"]) == 1
    row = plan["cases"][0]
    assert row["sha256"] == "a93499196b16dd1e9307ba97bedd24d246dedf995755e05bc9f20e382139966e"
    assert row["duration_seconds"] == 5.1675
    assert row["model"] == "flux-general-en"
    assert row["silence_tail_seconds"] == 3
    assert plan["connection_wall_seconds"] == 30
    assert plan["maximum_public_price_usd"] == "0.00385"
    assert plan["cost_ceiling_usd"] == "0.02"
    with pytest.raises(ValueError, match="exact batch scope"):
        module.build_plan(fresh_digits=True, diagnostic=True)


def test_remaining_deepgram_plan_excludes_the_verified_english_model():
    """A compatibility batch must not spend another call on an unchanged passing case."""
    module = probe()
    plan = module.build_plan(remaining_deepgram=True)
    assert plan["max_calls"] == len(plan["cases"]) == 2
    assert [row["model"] for row in plan["cases"]] == ["flux-general-multi", "nova-3"]
    assert plan["cases"][1]["options"] == {"language": "en"}
    assert plan["cases"][0]["options"] == {}
    assert plan["maximum_public_price_usd"] == "0.00850"
    assert plan["cost_ceiling_usd"] == "0.02"
    assert plan["request_sha256"] != module.build_plan(fresh_digits=True)["request_sha256"]
    with pytest.raises(ValueError, match="exact batch scope"):
        module.build_plan(remaining_deepgram=True, fresh_digits=True)


@pytest.mark.parametrize(
    "provider,model,host,upper",
    [
        ("assemblyai", "universal-3-5-pro", "streaming.assemblyai.com", "0.00375"),
        ("speechmatics", "enhanced", "eu2.rt.speechmatics.com", "0.00667"),
    ],
)
def test_single_vendor_plan_pins_independent_receiver_and_budget(provider, model, host, upper):
    """A Deepgram grant cannot authorize a new provider, even with identical audio."""
    module = probe()
    plan = module.build_plan(single_vendor=provider)
    assert plan["max_calls"] == len(plan["cases"]) == 1
    assert plan["recipient"] == host
    assert plan["cases"][0]["provider"] == provider
    assert plan["cases"][0]["model"] == model
    assert plan["maximum_public_price_usd"] == upper
    assert plan["cost_ceiling_usd"] == "0.02"
    assert plan["cases"][0]["options"] == (
        {"language_codes": ["en"]} if provider == "assemblyai" else {"language": "en"}
    )
    assert plan["request_sha256"] != module.build_plan(fresh_digits=True)["request_sha256"]
    with pytest.raises(ValueError, match="exact batch scope"):
        module.build_plan(single_vendor=provider, fresh_digits=True)


async def test_speechmatics_guard_limits_the_low_level_transport_and_restores_it(monkeypatch):
    """Guard the actual handshake path, rather than just the outer Voice client."""
    from speechmatics.rt import _transport

    calls = []

    async def inert_connect(instance, *args, **kwargs):
        calls.append(instance)
        return "offline"

    monkeypatch.setattr(_transport.Transport, "connect", inert_connect)
    module = probe()
    budget = module.ConnectionBudget()
    restore = module.guard_connection(object(), "speechmatics", "enhanced", budget)
    try:
        assert await _transport.Transport.connect("local") == "offline"
        with pytest.raises(RuntimeError, match="budget"):
            await _transport.Transport.connect("retry")
        assert calls == ["local"]
    finally:
        restore()
    assert _transport.Transport.connect is inert_connect


async def test_assemblyai_guard_matches_the_locked_sdk_handshake(monkeypatch):
    """Use the actual configured service and replace only its socket-opening operation."""
    from src.asr.factory import create_default_asr_registry
    from src.config import AudioConfig

    module = probe()
    row = module.build_plan(single_vendor="assemblyai")["cases"][0]
    service = create_default_asr_registry().create(
        provider=row["provider"],
        model=row["model"],
        options=row["options"],
        api_key="inert-no-network",
        audio=AudioConfig(),
        turn_detection_source="self_developed",
    )
    assert service.source_normalizer.provider == "assemblyai"
    assert service.processor._settings.model == "universal-3-5-pro"
    assert "streaming.assemblyai.com" in service.processor._build_ws_url()
    assert "speech_model=universal-3-5-pro" in service.processor._build_ws_url()
    calls = []

    async def inert_connect(*args, **kwargs):
        calls.append(True)
        return object()

    monkeypatch.setattr(service.processor, "_websocket_connect", inert_connect)
    budget = module.ConnectionBudget()
    restore = module.guard_connection(service.processor, "assemblyai", row["model"], budget)
    try:
        await service.processor._websocket_connect("inert")
        with pytest.raises(RuntimeError, match="budget"):
            await service.processor._websocket_connect("retry")
    finally:
        restore()
    assert calls == [True]
    assert service.processor._websocket_connect is inert_connect


def test_speechmatics_probe_preserves_null_timing_details_without_arbitrary_metadata():
    """Keep enough raw evidence to distinguish missing provider timing from parsing errors."""
    payload = {
        "message": "AddPartialSegment",
        "headers": {"Authorization": "never-save"},
        "segments": [
            {
                "text": "One",
                "speaker_id": "S1",
                "api_key": "never-save",
                "metadata": {"start_time": 0.1, "end_time": None, "secret": "never"},
                "fragments": None,
            }
        ],
    }
    result = probe().source_evidence(payload)
    assert result["segments"] == [
        {
            "text": "One",
            "speaker_id": "S1",
            "metadata": {"start_time": 0.1, "end_time": None},
            "fragments": None,
        }
    ]
    assert "headers" not in result
    assert "never" not in str(result)


def test_soniox_plan_reserves_tokens_instead_of_claiming_an_hourly_cap():
    """Token billing needs explicit headroom and a bounded receive policy."""
    plan = probe().build_plan(single_vendor="soniox")
    assert plan["recipient"] == "stt-rt.soniox.com"
    assert plan["cases"][0]["model"] == "stt-rt-v5"
    assert plan["cases"][0]["options"] == {"language_hints": ["en"]}
    assert plan["cases"][0]["max_received_tokens"] == 1000
    assert plan["cost_ceiling_usd"] == "0.02"
    assert plan["estimated_reserve_usd"] == "0.018"
    assert plan["vendor_enforced_cost_cap"] is False


async def test_token_guard_stops_abnormal_output_before_forwarding_more_audio():
    """Count every reported token including repeated snapshots; do not undercount revisions."""
    import json

    class Socket:
        def __init__(self):
            self.messages = iter(
                [
                    json.dumps({"tokens": [{"text": "1"}]}),
                    json.dumps({"tokens": [{"text": "1"}, {"text": "2"}]}),
                ]
            )
            self.closed = False
            self.sent = []

        async def __aiter__(self):
            for message in self.messages:
                yield message

        async def close(self):
            self.closed = True

        async def send(self, data):
            self.sent.append(data)

    socket = Socket()
    wrapper = probe().TokenBoundSocket(socket, limit=2)
    await wrapper.__anext__()
    with pytest.raises(RuntimeError, match="token budget"):
        await wrapper.__anext__()
    with pytest.raises(RuntimeError, match="token budget"):
        await wrapper.send(b"no-more-audio")
    assert socket.closed and socket.sent == []
