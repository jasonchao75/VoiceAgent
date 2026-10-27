"""R2: the fixed TTS batch may neither resend a Speak nor substitute its text."""

from importlib import import_module

import pytest


def probe():
    """Import the credential-free plan without starting a provider."""
    return import_module("scripts.evaluation.probe_td_tts")


def test_tts_plan_freezes_three_texts_voice_and_character_budget():
    plan = probe().build_plan()
    assert [row["text"] for row in plan["cases"]] == [
        "one",
        "two",
        "Your number has been cleared.",
    ]
    assert plan["max_calls"] == 3 and plan["cost_ceiling_usd"] == "0.10"
    assert plan["voice"] == "flux-alexis-en"
    assert plan["characters"] == 35
    assert plan["estimated_cost_usd"] == "0.001575"


async def test_speak_budget_rejects_repeat_or_changed_text_before_sending():
    module = probe()
    sent = []

    async def send(message):
        sent.append(message)

    guarded = module.speak_guard(send, "one")
    await guarded({"type": "Speak", "text": "one"})
    with pytest.raises(RuntimeError, match="budget"):
        await guarded({"type": "Speak", "text": "one"})
    assert len(sent) == 1
    changed = module.speak_guard(send, "two")
    with pytest.raises(RuntimeError, match="scope"):
        await changed({"type": "Speak", "text": "other"})
    assert len(sent) == 1


def test_tts_cli_refuses_key_loading_without_specific_authorization(monkeypatch):
    module = probe()
    touched = []
    monkeypatch.setattr(module, "local_key", lambda: touched.append(True))
    assert module.main([]) == 0
    assert module.main(["--execute", "--authorization-decision", "D-999"]) == 2
    assert touched == []


def test_actual_flux_tts_exposes_both_guarded_transport_boundaries():
    """Confirm the locked provider can enforce socket and Speak limits before startup."""
    from src.config import AudioConfig, TTSConfig
    from src.tts.factory import create_default_tts_registry

    config = TTSConfig(voice="flux-alexis-en", text_aggregation="sentence")
    processor = create_default_tts_registry().create(
        provider="deepgram_flux",
        api_key="test-fixture-private-key",
        config=config,
        audio=AudioConfig(),
    )
    assert callable(processor._websocket_connect)
    assert callable(processor._transport_send_json)


def test_tts_probe_dependencies_import_in_a_fresh_process():
    """A full-suite import cache must not conceal the standalone registry import cycle."""
    import subprocess
    import sys
    from pathlib import Path

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from src.tts.factory import create_default_tts_registry; "
            "from src.tts.unit_synthesis import synthesize_unit",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


async def test_actual_sdk_handshake_failure_has_safe_diagnostics_without_a_paid_call(
    monkeypatch,
    tmp_path,
):
    """A failed real adapter must expose a safe stage/status instead of a blind retry."""
    from types import SimpleNamespace

    from websockets.exceptions import InvalidStatus

    from src.tts import factory

    registry = factory.create_default_tts_registry()
    create = registry.create
    calls = []

    def offline_create(**kwargs):
        processor = create(**kwargs)

        async def handshake(*args, **kwargs):
            calls.append(True)
            raise InvalidStatus(
                SimpleNamespace(
                    status_code=403,
                    reason_phrase="test-fixture-private-key-do-not-record",
                )
            )

        processor._websocket_connect = handshake
        return processor

    registry.create = offline_create
    monkeypatch.setattr(factory, "create_default_tts_registry", lambda: registry)
    result = await probe().run_case(
        {"id": "1", "text": "one"}, "test-fixture-private-key", tmp_path, timeout=2
    )
    assert result["status"] == "synthesis_or_format_error"
    assert calls == [True] and result["connections"] == 1
    assert result["protocol"]["connection_failure"] == {"type": "InvalidStatus", "http_status": 403}
    assert result["protocol"]["audio_bytes"] == 0
    assert "test-fixture-private-key" not in __import__("json").dumps(result)


@pytest.mark.parametrize("changed", [False, True])
async def test_actual_sdk_single_unit_preserves_exact_authorized_text(
    monkeypatch,
    tmp_path,
    changed,
):
    """A unit does not need the continuous-sentence separator inserted by Flux SDK."""
    import asyncio
    import json

    from websockets.protocol import State

    from src.tts import factory

    sent = []

    class Socket:
        state = State.OPEN
        response = None

        def __init__(self):
            self.queue = asyncio.Queue()
            self.spoken = False
            self.queue.put_nowait(json.dumps({"type": "Connected"}))

        def __aiter__(self):
            return self

        async def __anext__(self):
            item = await self.queue.get()
            if item is None:
                raise StopAsyncIteration
            return item

        async def send(self, payload):
            message = json.loads(payload)
            sent.append(message)
            if message["type"] == "Speak":
                self.spoken = True
                await self.queue.put(b"\x01\x00" * 480)
            elif message["type"] == "Flush" and self.spoken:
                await self.queue.put(
                    json.dumps({"type": "SpeechMetadata", "billable_character_count": 3})
                )

        async def close(self):
            self.state = State.CLOSED
            await self.queue.put(None)

    registry = factory.create_default_tts_registry()
    create = registry.create

    def offline_create(**kwargs):
        processor = create(**kwargs)
        if changed:
            processor._prepare_text_for_tts = lambda text: text + "private-fixture-tail"

        async def connect(*args, **kwargs):
            return Socket()

        processor._websocket_connect = connect
        return processor

    registry.create = offline_create
    monkeypatch.setattr(factory, "create_default_tts_registry", lambda: registry)
    monkeypatch.setattr(probe(), "ROOT", tmp_path)
    result = await probe().run_case({"id": "1", "text": "one"}, "inert-key", tmp_path, timeout=2)
    if changed:
        assert result["status"] == "synthesis_or_format_error"
        assert result["protocol"]["failure_stage"] == "request_guard"
        assert result["protocol"]["scope_rejection"] == "text_scope_mismatch"
        assert result["protocol"]["speak_attempts"] == 1
        assert not [message for message in sent if message["type"] == "Speak"]
        assert "private-fixture-tail" not in json.dumps(result)
        return
    assert result["status"] == "ok"
    assert [message["text"] for message in sent if message["type"] == "Speak"] == ["one"]
    assert result["protocol"]["billable_characters"] == 3
    assert result["samples"] == 480


def test_one_unit_confirmation_plan_is_new_scope_not_the_old_three_text_grant():
    original = probe().build_plan()
    single = probe().build_plan(single_unit=True)
    assert single["cases"] == [{"id": "1", "text": "one"}]
    assert single["max_calls"] == 1 and single["characters"] == 3
    assert single["voice"] == original["voice"] == "flux-alexis-en"
    assert single["cost_ceiling_usd"] == "0.02"
    assert single["batch_id"] != original["batch_id"]
    assert single["request_sha256"] != original["request_sha256"]
