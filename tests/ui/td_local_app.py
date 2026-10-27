"""Loopback-only production-route test app with deterministic external provider replacements."""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import math
import os
import socket
import struct
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from pipecat.audio.vad.vad_analyzer import VADState
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    FunctionCallFromLLM,
    InputAudioRawFrame,
    InterimTranscriptionFrame,
    LLMTextFrame,
    TTSAudioRawFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService

from src.asr.factory import ASRService
from src.asr.turn_events import SourceNormalizer
from src.llm.scoped import ScopedOpenAILLMService
from src.pipeline.custom_td import CustomTDAudioInput, CustomTDCoordinator
from src.pipeline.jev import JevResult
from src.tts.response_scope import ResponseScopedTTSMixin


def block_external_connections() -> None:
    """Fail closed if a test replacement accidentally attempts any non-loopback connection."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto

    def check(sock: socket.socket, address: Any) -> None:
        """Reject non-loopback targets before any native TCP or UDP operation."""
        if sock.family not in {socket.AF_INET, socket.AF_INET6}:
            return
        host = address[0]
        try:
            allowed = ipaddress.ip_address(host).is_loopback
        except ValueError:
            allowed = host == "localhost"
        if not allowed:
            raise RuntimeError("External connections are forbidden in the local TD fixture")

    def connect(sock: socket.socket, address: Any) -> Any:
        """Apply the same ownership boundary to normal TCP connection setup."""
        check(sock, address)
        return original_connect(sock, address)

    def connect_ex(sock: socket.socket, address: Any) -> int:
        """Reject alternate non-raising connection setup before it reaches the OS."""
        check(sock, address)
        return original_connect_ex(sock, address)

    def sendto(sock: socket.socket, data: Any, *args: Any) -> int:
        """Cover datagram transports, including STUN, without blocking local RTP."""
        check(sock, args[-1])
        return original_sendto(sock, data, *args)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.socket.sendto = sendto  # type: ignore[method-assign]
    if hasattr(socket.socket, "sendmsg"):
        original_sendmsg = socket.socket.sendmsg

        def sendmsg(
            sock: socket.socket,
            buffers: Any,
            ancdata: Any = (),
            flags: int = 0,
            address: Any = None,
        ) -> int:
            """Cover the optional addressed scatter/gather datagram operation."""
            if address is not None:
                check(sock, address)
                return original_sendmsg(sock, buffers, ancdata, flags, address)
            return original_sendmsg(sock, buffers, ancdata, flags)

        socket.socket.sendmsg = sendmsg  # type: ignore[method-assign]


class LocalASR(FrameProcessor):
    """Emit known revisions from actual browser uplink sample progress, without a vendor."""

    ingress_proofs: list[dict[str, Any]] = []
    source_diagnostics: list[dict[str, Any]] = []

    def __init__(self) -> None:
        """Keep one deterministic source and two revision thresholds per session."""
        super().__init__()
        self.audio_ms = 0.0
        self.partial_sent = False
        self.final_sent = False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Preserve the real input graph and replace only transcription inference."""
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            proof = frame.metadata.get("td_rtp_input")
            if (
                os.environ.get("VOICE_AGENT_TD_ASSERT_RTP_INPUT") == "1"
                and isinstance(proof, dict)
                and len(self.ingress_proofs) < 8
            ):
                import copy

                self.ingress_proofs.append(copy.deepcopy(proof))
            self.audio_ms += len(frame.audio) / (frame.sample_rate * frame.num_channels * 2) * 1000
            final = self.audio_ms >= 3200 and not self.final_sent
            partial = self.audio_ms >= 1900 and not self.partial_sent
            if partial or final:
                text = "local final" if final else "local partial"
                self.partial_sent = True
                self.final_sent = self.final_sent or final
                transcript = InterimTranscriptionFrame(
                    text,
                    "",
                    "",
                    result={
                        "event": "EndOfTurn" if final else "Update",
                        "turn_index": 0,
                        "transcript": text,
                        "audio_window_start": 1,
                        "audio_window_end": 1.9,
                        "words": [{"word": text, "start": 1, "end": 1.9}],
                    },
                )
                transcript.metadata["td_source_only"] = True
                if os.environ.get("VOICE_AGENT_TD_LOCAL_SCENARIO") == "source_missing":
                    transcript.text = "local input without source evidence"
                    transcript.result = None
                await self.push_frame(transcript, direction)
        await self.push_frame(frame, direction)


class LocalASRRegistry:
    """Replace ASR only while retaining the production normalization contract."""

    models = (("deepgram", "flux-general-en"),)

    def create(self, **kwargs: Any) -> ASRService:
        """Return an inert source; never instantiate the vendor registry."""
        return ASRService(
            processor=(IdentifierASR() if identifier_scenario() else LocalASR()),  # type: ignore[arg-type]
            source_normalizer=SourceNormalizer("deepgram", "flux-general-en"),
        )


def identifier_scenario() -> bool:
    """Select only an explicitly launched offline acceptance scenario."""
    return os.environ.get("VOICE_AGENT_TD_LOCAL_SCENARIO") in {
        "identifier",
        "identifier_cache_repair",
        "identifier_cache_failure",
    }


class IdentifierASR(FrameProcessor):
    """Replay four source-proven inputs from browser PCM progress, without recognition."""

    def __init__(self) -> None:
        """Use fixed source intervals and one emission per input."""
        super().__init__()
        self.audio_ms = 0.0
        self.sent: set[int] = set()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Keep the original input path and emit only deterministic provider replacements."""
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            self.audio_ms += len(frame.audio) / (frame.sample_rate * 2) * 1000
            for index, (start, end, text) in enumerate(
                [
                    (1, 1.95, "one"),
                    (3, 3.95, "two"),
                    (4.5, 5.45, "How many digits are needed?"),
                    (6.5, 7.45, "No, clear that number."),
                ]
            ):
                offset = float(os.environ.get("VOICE_AGENT_TD_INPUT_DELAY", "0"))
                start, end = start + offset, end + offset
                if self.audio_ms < end * 1000 or index in self.sent:
                    continue
                self.sent.add(index)
                source = InterimTranscriptionFrame(
                    text,
                    "",
                    "",
                    result={
                        "event": "EndOfTurn",
                        "turn_index": index,
                        "transcript": text,
                        "audio_window_start": start,
                        "audio_window_end": end,
                        "words": [{"word": text, "start": start, "end": end}],
                    },
                )
                source.metadata["td_source_only"] = True
                await self.push_frame(source, direction)
        await self.push_frame(frame, direction)


class LocalVAD:
    """Deterministic VAD fixture; it proves wiring, never real speech/noise accuracy."""

    def __init__(self) -> None:
        """Count original 16kHz PCM independent of browser chunk size."""
        self.samples = 0

    async def analyze_audio(self, audio: bytes) -> VADState:
        """Return one speaking interval followed by sustained quiet."""
        self.samples += len(audio) // 2
        if identifier_scenario():
            seconds = self.samples / 16000 - float(
                os.environ.get("VOICE_AGENT_TD_INPUT_DELAY", "0")
            )
            speaking = any(
                start <= seconds <= end
                for start, end in [
                    (1, 2),
                    (3, 4),
                    (4.5, 5.5),
                    (6.5, 7.5),
                ]
            )
            return VADState.SPEAKING if speaking else VADState.QUIET
        return VADState.SPEAKING if 16000 <= self.samples <= 32000 else VADState.QUIET

    async def cleanup(self) -> None:
        """Provide the same cleanup boundary without a model executor."""


class LocalSynth(ResponseScopedTTSMixin, TTSService):
    """Generate synthetic PCM in the real TTS queues with original response provenance."""

    async def run_tts(self, text: str, context_id: str) -> Any:
        """Keep the Partial reply long enough to exercise actual browser cancellation."""
        if (
            os.environ.get("VOICE_AGENT_TD_LOCAL_SCENARIO") == "identifier_cache_failure"
            and text == "1"
        ):
            yield ErrorFrame(error="Offline fixture unit synthesis failed")
            return
        if text == "Please say your identifier.":
            # Model provider startup latency while keeping all audio local and synthetic.
            await asyncio.sleep(float(os.environ.get("VOICE_AGENT_TD_OPENING_DELAY", "0")))
        count = 120000 if "partial" in text else 12000 if "final" in text else 2400
        if (
            os.environ.get("VOICE_AGENT_TD_LOCAL_SCENARIO") == "identifier_cache_repair"
            and text == "1"
        ):
            count = 240000
        frequency = 440 if "partial" in text else 880 if "final" in text else 220
        for offset in range(0, count, 480):
            length = min(480, count - offset)
            audio = struct.pack(
                "<" + "h" * length,
                *(
                    int(6000 * math.sin(2 * math.pi * frequency * sample / 24000))
                    for sample in range(offset, offset + length)
                ),
            )
            yield TTSAudioRawFrame(audio, 24000, 1, context_id=context_id)
        yield TTSStoppedFrame(context_id=context_id)


class LocalTTSRegistry:
    """Use no vendor client, credential or network operation."""

    providers = ["deepgram_flux", "elevenlabs"]

    def create(self, **kwargs: Any) -> LocalSynth:
        """Retain production TTS context/aggregation and response fences."""
        return LocalSynth(
            response_owner=kwargs.get("response_owner"),
            sample_rate=24000,
            settings=TTSSettings(model=None, voice=None, language=None),
        )


class LocalLLM(ScopedOpenAILLMService):
    """Keep actual response scoping and SDK lifecycle; replace only inference."""

    async def _process_context(self, context: Any) -> None:
        """Reply from the immutable request provenance without sending an HTTP request."""
        version = self.response_scope.provenance(context)
        if version is None:
            raise RuntimeError("Local TD inference requires captured request provenance")
        if identifier_scenario():
            if "clear" in version.text:
                invoked = getattr(self, "_fixture_invoked", set())
                self._fixture_invoked = invoked
                if version.response_id not in invoked:
                    invoked.add(version.response_id)
                    await self.run_function_calls(
                        [
                            FunctionCallFromLLM(
                                function_name="clear_identifier",
                                tool_call_id=version.response_id,
                                arguments={},
                                context=context,
                            )
                        ]
                    )
                    return
                cleared = any(
                    message.get("role") == "tool"
                    and '"status":"cleared"' in "".join(str(message.get("content")).split())
                    for message in context.get_messages()
                )
                await self.push_frame(
                    LLMTextFrame(
                        "The identifier was cleared. Please say the full identifier."
                        if cleared
                        else "Could not clear the identifier."
                    )
                )
            else:
                await self.push_frame(LLMTextFrame("Please continue providing the identifier."))
            return
        await self.push_frame(LLMTextFrame(f"Response to {version.text}."))


async def prepare_local_td(**kwargs: Any) -> tuple[CustomTDAudioInput, CustomTDCoordinator, Any]:
    """Keep the production coordinator and input adapter, substituting local inference only."""

    async def decide(**_: Any) -> JevResult:
        """Return a labelled deterministic decision; no vendor effectiveness is asserted."""
        return JevResult("ok", noul=1, probabilities={"complete": 1, "incomplete": 0})

    class Client:
        """Match lifecycle cleanup without constructing an HTTP client."""

        async def aclose(self) -> None:
            """No external connection exists to close."""

    coordinator = CustomTDCoordinator(
        asr=kwargs["asr"],
        settings=kwargs["settings"],
        decide=decide,
        evidence_sink=kwargs.get("evidence_sink"),
        responses=kwargs.get("responses"),
        bind_input=kwargs.get("bind_input"),
        identifier_rules=kwargs.get("identifier_rules"),
        identifier_output=kwargs.get("identifier_output"),
        identifier_observe=kwargs.get("identifier_observe"),
    )
    return CustomTDAudioInput(coordinator, LocalVAD()), coordinator, Client()


def create_local_app(
    data_dir: Path,
    ui_origin: str = "http://127.0.0.1:5174",
    scenario: str = "ordinary",
) -> Any:
    """Build the actual application against isolated storage and fail-closed offline providers."""
    from urllib.parse import urlsplit

    import src.api as api
    import src.pipeline.voice_agent as pipeline

    if scenario not in {
        "ordinary",
        "identifier",
        "source_missing",
        "identifier_cache_repair",
        "identifier_cache_failure",
    }:
        raise ValueError("Unknown offline scenario")
    os.environ["VOICE_AGENT_TD_LOCAL_SCENARIO"] = scenario
    handshake_delay = float(os.environ.get("VOICE_AGENT_TD_SCTP_DELAY", "0"))
    if handshake_delay:
        from aiortc.rtcsctptransport import InitAckChunk, InitChunk, RTCSctpTransport

        original_send_chunk = RTCSctpTransport._send_chunk

        async def delayed_send_chunk(self: Any, chunk: Any) -> None:
            """Delay only initial SCTP setup; real RTP still takes its native path."""
            if isinstance(chunk, (InitChunk, InitAckChunk)):
                await asyncio.sleep(handshake_delay)
            await original_send_chunk(self, chunk)

        RTCSctpTransport._send_chunk = delayed_send_chunk
    LocalASR.ingress_proofs = []
    LocalASR.source_diagnostics = []
    if os.environ.get("VOICE_AGENT_TD_RTC_SOURCE_DIAGNOSTIC") == "1":
        import copy
        from dataclasses import asdict

        from src.history.capture import CallCapture
        from src.history.rtp_source import RTPCaptureLedger

        native_observe = RTPCaptureLedger.observe
        source_refresh = CallCapture._refresh_source_ends
        capture_observe = CallCapture.observe
        capture_counts: dict[int, dict[str, int]] = {}

        def observe_capture(self: Any, frame: object) -> None:
            """Count input observations without changing the production observer's behavior."""
            if isinstance(frame, InputAudioRawFrame):
                counts = capture_counts.setdefault(id(self), {"input": 0, "proof": 0, "only": 0})
                counts["input"] += 1
                counts["proof"] += int(isinstance(frame.metadata.get("td_rtp_input"), dict))
                counts["only"] += int(bool(frame.metadata.get("td_source_only")))
            capture_observe(self, frame)

        def observe_source(self: Any, offset: int, count: int, proof: Any) -> bool:
            """Count actual native acceptance without modifying audio or accepted provenance."""
            accepted = native_observe(self, offset, count, proof)
            self.fixture_observed = getattr(self, "fixture_observed", 0) + 1
            self.fixture_accepted = getattr(self, "fixture_accepted", 0) + int(accepted)
            if not accepted:
                self.fixture_last_rejected = {
                    "offset": offset,
                    "count": count,
                    "proof": copy.deepcopy(proof),
                }
            return accepted

        def refresh_source(self: Any) -> None:
            """Keep at most sixteen candidate snapshots of only the missing join layers."""
            source_refresh(self)
            if len(LocalASR.source_diagnostics) >= 16:
                return
            for turn, source in self._source_ends.items():
                sample = math.floor(source["sample"])
                native = self.rtp_source
                chunks = []
                for offset, (count, proof, _) in native._chunks.items():
                    if offset <= sample <= offset + count:
                        chunks.append(
                            {
                                "offset": offset,
                                "count": count,
                                "proof": proof,
                                "reports": [
                                    native._packets.get(
                                        (
                                            part["ssrc"],
                                            part["rtp_timestamp"],
                                            part["payload_sha256"],
                                        )
                                    )
                                    for part in proof["packets"]
                                ],
                            }
                        )
                point = native.locate_sample(sample)
                LocalASR.source_diagnostics.append(
                    copy.deepcopy(
                        {
                            "elapsed_ms": self.elapsed_ms(),
                            "turn_id": turn,
                            "source": source,
                            "epoch": native.epoch,
                            "input_observations": capture_counts.get(id(self), {}),
                            "observed_native_chunks": getattr(native, "fixture_observed", 0),
                            "accepted_native_chunks": getattr(native, "fixture_accepted", 0),
                            "last_rejected_native": getattr(native, "fixture_last_rejected", None),
                            "retained_chunks": len(native._chunks),
                            "retained_reports": len(native._packets),
                            "matching_chunks": chunks,
                            "point": asdict(point) if point else None,
                            "capture_anchors": [
                                asdict(anchor) for anchor in self.capture_clock._anchors.values()
                            ],
                        }
                    )
                )

        RTPCaptureLedger.observe = observe_source
        CallCapture.observe = observe_capture
        CallCapture._refresh_source_ends = refresh_source
    os.environ["VOICE_AGENT_STUN_URLS"] = ""
    parsed = urlsplit(ui_origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("The test UI origin must be an explicit loopback HTTP origin")
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["VOICE_AGENT_DATA_DIR"] = str(data_dir)
    os.environ["VOICE_AGENT_EVALUATION_DATA_DIR"] = str(data_dir)
    key_path = data_dir / "storage.key"
    if not key_path.exists():
        descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(Fernet.generate_key())
    os.environ["VOICE_AGENT_STORAGE_KEY"] = key_path.read_text().strip()
    os.environ["VOICE_AGENT_ALLOWED_ORIGINS"] = (
        "http://127.0.0.1:5174,http://localhost:5174,http://127.0.0.1:8765," + ui_origin
    )
    os.environ.pop("VOICE_AGENT_BASIC_AUTH_USERNAME", None)
    os.environ.pop("VOICE_AGENT_BASIC_AUTH_PASSWORD", None)
    block_external_connections()
    api.create_default_asr_registry = LocalASRRegistry
    api.create_default_tts_registry = LocalTTSRegistry
    pipeline.prepare_custom_td = prepare_local_td
    pipeline.create_llm_service = lambda **kwargs: LocalLLM(
        api_key="test-local-inert-no-network", response_scope=kwargs["response_scope"]
    )
    if os.environ.get("VOICE_AGENT_TD_RTC_DIAGNOSTIC") in {"D-069", "D-070", "D-071"}:
        from aiortc.mediastreams import MediaStreamError

        from src.pipeline.rtp_mapping import MappedRawAudioTrack

        if os.environ.get("VOICE_AGENT_TD_RTC_DIAGNOSTIC") in {"D-070", "D-071"}:
            from aiortc.rtp import is_rtcp

            import src.pipeline.rtp_output as rtp_output

            install = rtp_output.install_candidate_transport

            def observed_install(transport: Any, connection: Any) -> None:
                """Observe actual native send completion only in the bounded fixture."""
                audio = [item for item in connection._pc.getTransceivers() if item.kind == "audio"]
                if len(audio) != 1:
                    raise RuntimeError("Diagnostic audio sender missing")
                dtls = audio[0].sender.transport
                send = dtls._send_rtp
                completed = 0

                async def observed_send(payload: bytes) -> None:
                    """Count completed native sends without retaining media or network fields."""
                    nonlocal completed
                    await send(payload)
                    if not is_rtcp(payload):
                        completed += 1
                        connection.send_app_message(
                            {
                                "label": "voice-agent-playback",
                                "event": "diagnostic_send_completed",
                                "count": completed,
                            }
                        )

                dtls._send_rtp = observed_send
                install(transport, connection)

            rtp_output.install_candidate_transport = observed_install

        original_recv = MappedRawAudioTrack.recv

        async def limited_recv(track: Any) -> Any:
            """Bound all native output, including silence, to the authorized two seconds."""
            if track._timestamp >= track._sample_rate * 2:
                raise MediaStreamError
            return await original_recv(track)

        async def no_inference(processor: Any, frame: Frame, direction: FrameDirection) -> None:
            """Do not generate any Final/identifier scenario in this diagnostic."""
            await FrameProcessor.process_frame(processor, frame, direction)
            await processor.push_frame(frame, direction)

        MappedRawAudioTrack.recv = limited_recv
        LocalASR.process_frame = no_inference

    app = api.create_app(
        development_rtp_candidate=os.environ.get("VOICE_AGENT_TD_LOCAL_RTP_CANDIDATE") == "1"
    )
    armed_bots: set[str] = set()
    failed_versions: dict[str, str] = {}
    original_read = app.state.echo_cache.read

    async def read_with_runtime_fault(asset: Any) -> bytes:
        """Fail only a published unit's first runtime read, without deleting any file."""
        if (
            scenario in {"identifier_cache_repair", "identifier_cache_failure"}
            and asset.bot_id in armed_bots
            and asset.unit == "1"
        ):
            failed_versions.setdefault(asset.bot_id, asset.version)
            if asset.version == failed_versions[asset.bot_id]:
                raise ValueError("Offline fixture runtime read failure")
        return await original_read(asset)

    app.state.echo_cache.read = read_with_runtime_fault

    diagnostic_offers = 0
    history_faults: set[str] = set()

    @app.middleware("http")
    async def fixture_header(request: Any, call_next: Any) -> Any:
        """Let destructive setup tests prove they reached this disposable app first."""
        nonlocal diagnostic_offers
        if (
            request.method == "GET"
            and request.url.path == "/api/_test/td-rtp-input"
            and os.environ.get("VOICE_AGENT_TD_ASSERT_RTP_INPUT") == "1"
        ):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                {"proofs": LocalASR.ingress_proofs},
                headers={
                    "X-VoiceAgent-Test-Fixture": "td-local-offline",
                },
            )
        if (
            request.method == "GET"
            and request.url.path == "/api/_test/td-source-diagnostic"
            and os.environ.get("VOICE_AGENT_TD_RTC_SOURCE_DIAGNOSTIC") == "1"
        ):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                {
                    "snapshots": LocalASR.source_diagnostics,
                    "first_native_proofs": LocalASR.ingress_proofs,
                },
                headers={
                    "X-VoiceAgent-Test-Fixture": "td-local-offline",
                },
            )
        history_fault = request.headers.get("X-VoiceAgent-Test-History-Failure")
        if (
            request.method == "GET"
            and request.url.path == "/api/history"
            and history_fault in {"1440", "390"}
            and history_fault not in history_faults
        ):
            from fastapi.responses import JSONResponse

            history_faults.add(history_fault)
            return JSONResponse(
                {"detail": "Local history temporarily unavailable"},
                503,
                headers={"X-VoiceAgent-Test-Fixture": "td-local-offline"},
            )
        if (
            os.environ.get("VOICE_AGENT_TD_RTC_DIAGNOSTIC") in {"D-069", "D-070", "D-071"}
            and request.method == "POST"
            and request.url.path.startswith("/api/public/webrtc/")
        ):
            from fastapi.responses import JSONResponse

            diagnostic_offers += 1
            if diagnostic_offers > 1:
                return JSONResponse({"detail": "Diagnostic connection budget exhausted"}, 409)
        is_session = request.method == "POST" and request.url.path == "/api/sessions"
        payload = await request.json() if is_session else {}
        response = await call_next(request)
        if is_session and response.status_code == 201 and isinstance(payload.get("bot_id"), str):
            armed_bots.add(payload["bot_id"])
        if (
            scenario in {"identifier_cache_repair", "identifier_cache_failure"}
            and response.status_code == 201
            and request.method == "POST"
            and request.url.path.startswith("/api/public/demos/")
            and request.url.path.endswith("/sessions")
        ):
            public_id = request.url.path.split("/")[4]
            publication = await app.state.publication_store.get_public(public_id)
            if publication is not None:
                armed_bots.add(publication.bot_id)
        response.headers["X-VoiceAgent-Test-Fixture"] = "td-local-offline"
        response.headers["X-VoiceAgent-Test-Scenario"] = scenario
        return response

    async def synthesize(
        unit: str, config: Any, rate: int, *, timeout: float, api_key: str
    ) -> bytes:
        """Return deterministic local unit PCM through the original permanent cache APIs."""
        samples = rate * (10 if unit == "1" else 2) if identifier_scenario() else 2400
        return b"\x00\x08" * samples

    app.state.echo_synthesize = synthesize
    return app


def main() -> None:
    """Run only on loopback with an explicitly selected disposable data directory."""
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--ui-origin", default="http://127.0.0.1:5174")
    parser.add_argument(
        "--scenario",
        choices=[
            "ordinary",
            "identifier",
            "source_missing",
            "identifier_cache_repair",
            "identifier_cache_failure",
        ],
        default="ordinary",
    )
    args = parser.parse_args()
    if not args.data_dir.resolve().is_relative_to(Path("/tmp").resolve()):
        raise ValueError("The local fixture requires disposable storage under /tmp")
    uvicorn.run(
        create_local_app(args.data_dir, args.ui_origin, args.scenario),
        host="127.0.0.1",
        port=args.port,
    )


if __name__ == "__main__":
    main()
