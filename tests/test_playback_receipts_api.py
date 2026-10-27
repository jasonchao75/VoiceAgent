"""Task-specific render reports need both the live lease and a prepared task."""

from fastapi.testclient import TestClient

from src.api import create_app


def test_receipt_endpoint_rejects_foreign_tasks_tokens_and_raw_text(monkeypatch, session_request):
    captures = []

    async def pipeline(**kwargs):
        capture = kwargs["call_capture"]
        captures.append(capture)
        capture.record_td_event(
            {
                "event": "playback_task_prepared",
                "playback_id": "a" * 32,
                "kind": "normal",
                "response_id": "1:1",
            }
        )
        await kwargs["websocket"].send_json({"ready": True})
        await kwargs["websocket"].receive_text()

    monkeypatch.setattr("src.api.run_voice_agent_session", pipeline)
    payload = session_request.model_dump(mode="json")
    payload.update(
        session_type="chat_test",
        deepgram_api_key="test-test-fixture-no-network-123",
        llm_api_key="test-test-fixture-no-network-456",
    )
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions", json=payload, headers={"Origin": "http://localhost:8000"}
        )
        assert created.status_code == 201, created.text
        session = created.json()
        with client.websocket_connect(
            session["websocket_path"], headers={"Origin": "http://localhost:8000"}
        ) as socket:
            assert socket.receive_json()["ready"]
            url = f"/api/sessions/{session['session_id']}/playback-events"
            headers = {"Authorization": f"Bearer {session['session_token']}"}
            receipt = {
                "playback_id": "a" * 32,
                "event": "task_started",
                "rendered_samples": 128,
                "elapsed_ms": 10,
                "evidence_source": "audio_worklet_render",
                "render_frame": 1024,
                "render_sample_rate": 24000,
                "render_clock_id": "c" * 32,
            }
            assert client.post(url, json=receipt).status_code == 401
            assert (
                client.post(
                    url, json={**receipt, "playback_id": "b" * 32}, headers=headers
                ).status_code
                == 409
            )
            assert (
                client.post(
                    url, json={**receipt, "rendered_samples": 0}, headers=headers
                ).status_code
                == 409
            )
            assert (
                client.post(
                    url, json={**receipt, "text": "private text"}, headers=headers
                ).status_code
                == 422
            )
            assert client.post(url, json=receipt, headers=headers).status_code == 204
            assert client.post(url, json=receipt, headers=headers).status_code == 204
            clock_receipt = next(
                event
                for event in captures[0].td_events
                if event["event"] == "playback_renderer_receipt"
            )
            assert clock_receipt["render_frame"] == 1024
            assert clock_receipt["render_sample_rate"] == 24000
            assert clock_receipt["render_clock_id"] == "c" * 32
            assert captures[0]._current.browser_playback_ms is None
            assert (
                client.post(
                    url, json={**receipt, "render_clock_id": "d" * 32}, headers=headers
                ).status_code
                == 409
            )
            assert (
                client.post(
                    url, json={**receipt, "render_frame": 1025}, headers=headers
                ).status_code
                == 409
            )

            failed = {**receipt, "event": "task_failed", "failure_reason": "render_queue_limit"}
            assert client.post(url, json=failed, headers=headers).status_code == 409
            # Queue rejection has no render timestamp, as emitted by the actual Worklet.
            failed = {key: value for key, value in failed.items() if not key.startswith("render_")}
            assert client.post(url, json=failed, headers=headers).status_code == 204
            assert (
                client.post(
                    url,
                    json={**failed, "failure_reason": "arbitrary private detail"},
                    headers=headers,
                ).status_code
                == 422
            )
            socket.send_text("done")


def test_formal_websocket_pipeline_sends_task_pcm_and_accepts_matching_receipts(
    monkeypatch, session_request
):
    """Keep the real route, transport, SDK queues and serial output; stub external services only."""
    import json

    from pipecat.frames.frames import TTSAudioRawFrame, TTSStoppedFrame
    from pipecat.frames.protobufs import frames_pb2
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.services.settings import TTSSettings
    from pipecat.services.tts_service import TTSService

    from src.asr.factory import ASRService
    from src.pipeline.audio_identity import decode_audio_identity
    from src.tts.response_scope import ResponseScopedTTSMixin
    from tests.test_td_config import td_settings

    class Pass(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            await self.push_frame(frame, direction)

    class ASR:
        def create(self, **kwargs):
            return ASRService(processor=Pass())

    class Synth(ResponseScopedTTSMixin, TTSService):
        async def run_tts(self, text, context_id):
            yield TTSAudioRawFrame(b"\x01\x00" * 2400, 24000, 1, context_id=context_id)
            yield TTSStoppedFrame(context_id=context_id)

    class TTS:
        def create(self, **kwargs):
            return Synth(
                response_owner=kwargs.get("response_owner"),
                sample_rate=24000,
                settings=TTSSettings(model=None, voice=None, language=None),
            )

    import traceback

    from src.pipeline.voice_agent import run_voice_agent_session as actual_session

    errors = []

    async def checked_session(**kwargs):
        try:
            await actual_session(**kwargs)
        except Exception:
            errors.append(traceback.format_exc())
            raise

    monkeypatch.setattr("src.api.run_voice_agent_session", checked_session)
    monkeypatch.setattr("src.api.create_default_asr_registry", ASR)
    monkeypatch.setattr("src.api.create_default_tts_registry", TTS)
    monkeypatch.setattr("src.pipeline.voice_agent.create_llm_service", lambda **kwargs: Pass())
    payload = session_request.model_dump(mode="json")
    payload.update(
        turn_detection_source="self_developed",
        td_config=td_settings(),
        jev_api_key="test-test-fixture-no-network-jev",
        opening_script="Welcome.",
    )
    import threading

    persisted = threading.Event()
    app = create_app()
    original_finish = app.state.history_store.finish_call

    async def finish_call(**kwargs):
        await original_finish(**kwargs)
        persisted.set()

    app.state.history_store.finish_call = finish_call
    with TestClient(app) as client:
        created = client.post(
            "/api/sessions", json=payload, headers={"Origin": "http://localhost:8000"}
        )
        assert created.status_code == 201, created.text
        session = created.json()
        with client.websocket_connect(
            session["websocket_path"], headers={"Origin": "http://localhost:8000"}
        ) as socket:
            ready = frames_pb2.Frame()
            ready.message.data = json.dumps(
                {
                    "label": "rtvi-ai",
                    "type": "client-ready",
                    "id": "fixture",
                    "data": {"version": "1.0.0"},
                }
            )
            socket.send_bytes(ready.SerializeToString())
            identity = None
            samples = 0
            # The existing sender may split/pad short PCM; every output chunk retains identity.
            for _ in range(100):
                try:
                    frame = frames_pb2.Frame.FromString(socket.receive_bytes())
                except Exception:
                    assert not errors, errors
                    raise
                if frame.WhichOneof("frame") == "audio":
                    found = decode_audio_identity(frame.audio.name)
                    assert found is not None
                    identity = identity or found
                    assert found == identity
                    samples += len(frame.audio.audio) // 2
                elif frame.WhichOneof("frame") == "message":
                    message = json.loads(frame.message.data)
                    if (
                        message.get("label") == "voice-agent-playback"
                        and message.get("event") == "task_end"
                    ):
                        assert identity and message["playback_id"] == identity["playback_id"]
                        break
            else:
                raise AssertionError("No task EOS from formal pipeline")
            assert identity["kind"] == "normal" and identity["response_id"] is None
            assert samples >= 2400
            url = f"/api/sessions/{session['session_id']}/playback-events"
            headers = {"Authorization": f"Bearer {session['session_token']}"}
            for event in ["task_started", "task_finished"]:
                response = client.post(
                    url,
                    headers=headers,
                    json={
                        "playback_id": identity["playback_id"],
                        "event": event,
                        "rendered_samples": samples,
                        "elapsed_ms": 100,
                        "evidence_source": "audio_worklet_render",
                    },
                )
                assert response.status_code == 204, response.text

            # Explicit close lets the production disconnect handler finish before TestClient
            # cancels its ASGI task at context exit.
            socket.close()
            assert persisted.wait(3), "Production disconnect did not persist history"
        history = client.get(f"/api/history/{session['session_id']}")
        assert history.status_code == 200, history.text
        events = history.json()["td_events"]
        settings = next(event for event in events if event["event"] == "td_settings_snapshot")
        assert settings["turn_id"] is None and settings["minimum_ms"] == 600
        assert settings["noul_instructions"] == "Has the user yielded the floor?"
        assert "test-test-fixture-no-network-jev" not in json.dumps(events)
        assert not any("endpoint" in event or "api_key" in event for event in events)


def test_receipt_schema_preserves_complete_bounded_render_clock():
    """Sample coordinates are optional for old clients but cannot be partially specified."""
    import pytest
    from pydantic import ValidationError

    from src.api import PlaybackReceipt

    data = {
        "playback_id": "a" * 32,
        "event": "task_started",
        "rendered_samples": 128,
        "elapsed_ms": 20,
        "evidence_source": "audio_worklet_render",
        "render_frame": 1024,
        "render_sample_rate": 24000,
        "render_clock_id": "b" * 32,
    }
    assert PlaybackReceipt.model_validate(data).render_frame == 1024
    for field in ("render_frame", "render_sample_rate", "render_clock_id"):
        incomplete = {key: value for key, value in data.items() if key != field}
        with pytest.raises(ValidationError):
            PlaybackReceipt.model_validate(incomplete)
    with pytest.raises(ValidationError):
        PlaybackReceipt.model_validate({**data, "render_frame": True})
    with pytest.raises(ValidationError):
        PlaybackReceipt.model_validate({**data, "render_frame": -1})


def test_clock_challenges_are_session_owned_bounded_and_acknowledged_once(
    monkeypatch,
    session_request,
):
    """D-073 clock evidence needs the original live lease and cannot retarget a nonce."""
    captures = []

    async def pipeline(**kwargs):
        captures.append(kwargs["call_capture"])
        await kwargs["websocket"].send_json({"ready": True})
        await kwargs["websocket"].receive_text()

    monkeypatch.setattr("src.api.run_voice_agent_session", pipeline)
    payload = session_request.model_dump(mode="json")
    payload.update(
        session_type="chat_test",
        deepgram_api_key="inert-no-network",
        llm_api_key="inert-no-network",
    )
    with TestClient(create_app()) as client:
        session = client.post(
            "/api/sessions", json=payload, headers={"Origin": "http://localhost:8000"}
        ).json()
        with client.websocket_connect(
            session["websocket_path"], headers={"Origin": "http://localhost:8000"}
        ) as socket:
            assert socket.receive_json()["ready"]
            url = f"/api/sessions/{session['session_id']}/playback-clock"
            headers = {"Authorization": f"Bearer {session['session_token']}"}
            probe = {"render_clock_id": "a" * 32, "render_sample_rate": 48000}
            assert client.post(url, json=probe).status_code == 401
            issued = client.post(url, json=probe, headers=headers)
            assert issued.status_code == 201, issued.text
            sample_id = issued.json()["sample_id"]
            ack = {**probe, "render_frame": 1000}
            assert client.post(f"{url}/{sample_id}", json=ack, headers=headers).status_code == 204
            original = captures[0].render_clock.observation(sample_id)
            assert client.post(f"{url}/{sample_id}", json=ack, headers=headers).status_code == 204
            assert (
                client.post(
                    f"{url}/{sample_id}", json={**ack, "render_frame": 1001}, headers=headers
                ).status_code
                == 409
            )
            assert captures[0].render_clock.observation(sample_id) == original
            assert original["sample_id"] == sample_id
            assert original["server_issued_ms"] <= original["server_received_ms"]
            assert not any(row["event"] == "playback_clock_anchor" for row in captures[0].td_events)
            assert (
                client.post(url, json={**probe, "text": "forbidden"}, headers=headers).status_code
                == 422
            )
            input_probe = {**probe, "clock_kind": "capture"}
            input_id = client.post(url, json=input_probe, headers=headers).json()["sample_id"]
            input_ack = {**input_probe, "render_frame": 2000}
            assert (
                client.post(
                    f"{url}/{input_id}", json={**input_ack, "clock_kind": "render"}, headers=headers
                ).status_code
                == 409
            )
            assert (
                client.post(f"{url}/{input_id}", json=input_ack, headers=headers).status_code == 204
            )
            assert captures[0].render_clock.observation(input_id) is None
            assert captures[0].capture_clock.observation(input_id) is not None
            for _ in range(8):
                assert client.post(url, json=probe, headers=headers).status_code == 201
            assert client.post(url, json=probe, headers=headers).status_code == 429


def test_rtp_capture_endpoint_requires_live_auth_and_the_server_epoch(monkeypatch, session_request):
    """A raw timestamp POST cannot create input evidence without native PCM provenance."""
    captures = []

    async def pipeline(**kwargs):
        """Keep a real live lease while replacing only provider inference."""
        capture = kwargs["call_capture"]
        captures.append(capture)
        await kwargs["websocket"].send_json({"ready": True})
        if await kwargs["websocket"].receive_text() == "arm-native-source":
            capture.rtp_source.begin_epoch("a" * 32)
            await kwargs["websocket"].send_json({"armed": True})
            await kwargs["websocket"].receive_text()

    monkeypatch.setattr("src.api.run_voice_agent_session", pipeline)
    payload = session_request.model_dump(mode="json")
    payload.update(session_type="chat_test", deepgram_api_key="inert-asr", llm_api_key="inert-llm")
    with TestClient(create_app()) as client:
        session = client.post(
            "/api/sessions", json=payload, headers={"Origin": "http://localhost:8000"}
        ).json()
        with client.websocket_connect(
            session["websocket_path"], headers={"Origin": "http://localhost:8000"}
        ) as socket:
            assert socket.receive_json()["ready"]
            body = {
                "connection_id": "a" * 32,
                "records": [
                    {
                        "clock_id": "b" * 32,
                        "ssrc": 7,
                        "rtp_timestamp": 1,
                        "payload_sha256": "c" * 64,
                        "capture_time_ms": 100.0,
                        "capture_clock": "worker_performance",
                    }
                ],
            }
            url = f"/api/sessions/{session['session_id']}/rtp-input"
            assert client.post(url, json=body).status_code == 401
            headers = {"Authorization": f"Bearer {session['session_token']}"}
            assert client.post(url, json=body, headers=headers).status_code == 409
            socket.send_text("arm-native-source")
            assert socket.receive_json()["armed"]
            assert client.post(url, json=body, headers=headers).status_code == 204
            assert captures[0].rtp_source.locate_sample(0) is None
            assert (
                client.post(
                    url, json={**body, "connection_id": "d" * 32}, headers=headers
                ).status_code
                == 409
            )
            bad = {**body, "records": [{**body["records"][0], "input_offset": 0}]}
            assert client.post(url, json=bad, headers=headers).status_code == 422
            assert (
                client.post(
                    url, json={**body, "records": body["records"] * 17}, headers=headers
                ).status_code
                == 422
            )
            socket.send_text("end")
