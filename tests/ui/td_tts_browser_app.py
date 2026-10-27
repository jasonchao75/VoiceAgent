"""Disposable production-page fixture: bounded Flux TTS, offline ASR/Jev/LLM."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import ipaddress
import json
import logging
import os
import socket
import sys
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluation.probe_td_compatibility import (  # noqa: E402
    ConnectionBudget,
    local_key,
    verify_authorization,
)
from scripts.evaluation.probe_td_tts_cancel import TEXTS  # noqa: E402
from scripts.evaluation.probe_td_tts_cancel import build_plan as sdk_plan  # noqa: E402

CHANGE = ROOT / "openspec/changes/archive/2026-10-27-add-jev-semantic-turn-detection"
BATCH = "deepgram-tts-formal-browser-r96-v1"
VENDOR_CONNECT: ContextVar[bool] = ContextVar("approved_tts_connect", default=False)
LOGGER = logging.getLogger(__name__)


def build_plan() -> dict[str, Any]:
    """Freeze the new browser batch independently of the consumed SDK-only grant."""
    plan = sdk_plan()
    plan.pop("request_sha256")
    plan.update(
        batch_id=BATCH,
        scope="production WebSocket page + real Flux TTS; "
        "fake microphone/ASR/VAD/Jev/LLM; not physical sound or RTC",
        trigger="authenticated old task_started receipt with rendered_samples>0 "
        "releases one fixed Final; no opening text",
        acceptance="old renderer task_stopped with positive samples; new task_started "
        "after old stop in same render clock; provider ended-old metadata or cancel ACK "
        "separately recorded; no old task_finished instead of interruption",
        stop="first error/format/scope/identity/budget failure; missing render proof "
        "stops batch; no retry or reconnection; server already-finished old synthesis "
        "is valid only if browser old task actually stops",
        ui_origin="http://127.0.0.1:18996",
        max_sessions=1,
    )
    plan["request_sha256"] = hashlib.sha256(
        json.dumps(
            plan,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return plan


def install_egress_guard(addresses: set[str]) -> Any:
    """Allow loopback, or approved TLS connect in the vendor task's own capability context."""
    originals = {name: getattr(socket.socket, name) for name in ("connect", "connect_ex", "sendto")}
    if hasattr(socket.socket, "sendmsg"):
        originals["sendmsg"] = socket.socket.sendmsg

    def check(sock: Any, target: Any) -> None:
        if sock.family not in {socket.AF_INET, socket.AF_INET6}:
            return
        host, port = target[:2]
        if host == "localhost" or ipaddress.ip_address(host).is_loopback:
            return
        if (
            VENDOR_CONNECT.get()
            and sock.type == socket.SOCK_STREAM
            and host in addresses
            and port == 443
        ):
            return
        raise RuntimeError("External destination lacks a task-local TTS capability")

    def connect(sock: Any, target: Any) -> Any:
        check(sock, target)
        return originals["connect"](sock, target)

    def connect_ex(sock: Any, target: Any) -> Any:
        check(sock, target)
        return originals["connect_ex"](sock, target)

    def sendto(sock: Any, data: Any, *args: Any) -> Any:
        # The capability is for TCP TLS only; it must not authorize external UDP.
        token = VENDOR_CONNECT.set(False)
        try:
            check(sock, args[-1])
        finally:
            VENDOR_CONNECT.reset(token)
        return originals["sendto"](sock, data, *args)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = sendto
    if "sendmsg" in originals:

        def sendmsg(
            sock: Any, buffers: Any, ancdata: Any = (), flags: int = 0, target: Any = None
        ) -> Any:
            if target is not None:
                token = VENDOR_CONNECT.set(False)
                try:
                    check(sock, target)
                finally:
                    VENDOR_CONNECT.reset(token)
            return originals["sendmsg"](sock, buffers, ancdata, flags, target)

        socket.socket.sendmsg = sendmsg

    def restore() -> None:
        for name, original in originals.items():
            setattr(socket.socket, name, original)

    return restore


class WireFixture:
    """Offline protocol replacement, with long buffered old PCM to test real browser stop."""

    def __init__(self) -> None:
        from websockets.protocol import State

        self.state = State.OPEN
        self.response = None
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.count = 0

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> Any:
        item = await self.queue.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def send(self, encoded: str) -> None:
        message = json.loads(encoded)
        kind = message["type"]
        if kind == "Configure":
            await self.queue.put(json.dumps({"type": "ConfigureSuccess"}))
        elif kind == "Speak":
            self.count += 1
            await self.queue.put(
                json.dumps({"type": "SpeechStarted", "speech_id": f"fixture-{self.count}"})
            )
            await self.queue.put(b"\x01\x08" * 48000 if self.count == 1 else b"\x02\x08" * 12000)
            if self.count == 2:
                await self.queue.put(
                    json.dumps({"type": "SpeechMetadata", "speech_id": "fixture-2"})
                )
        elif kind == "Interrupt":
            await self.queue.put(b"\x09\x00" * 240)
            await self.queue.put(
                json.dumps({"type": "SpeechInterrupted", "metadata": {"speech_id": "fixture-1"}})
            )

    async def close(self) -> None:
        from websockets.protocol import State

        self.state = State.CLOSED
        await self.queue.put(None)


def require_old_identity(identity: Any, started: list[str]) -> None:
    """Reject missing or unrelated completion identities before opening a new Speak."""
    if not started or not isinstance(identity, str) or not identity or identity != started[0]:
        raise ValueError("Old terminal identity is missing or unrelated")


async def stop_owned_connections(connections: list[Any]) -> None:
    """Stop only this isolated batch's sockets without waiting on provider backpressure."""
    for connection in connections:
        transport = getattr(connection, "transport", None)
        if transport is not None:
            transport.abort()
        else:
            await asyncio.wait_for(connection.close(), timeout=1)


def create_mixed_app(data_dir: Path, *, key: str, external: bool, addresses: set[str]) -> Any:
    """Bind the same production routes to a single capped TTS session in disposable storage."""
    if not data_dir.resolve().is_relative_to(Path("/tmp").resolve()):
        raise ValueError("Disposable /tmp storage required")
    from pipecat.frames.frames import InputAudioRawFrame, LLMTextFrame
    from pipecat.processors.frame_processor import FrameProcessor

    import src.pipeline.voice_agent as pipeline
    import tests.ui.td_local_app as local
    from src.asr.factory import _configure_provider_tls
    from src.tts.factory import create_default_tts_registry

    _configure_provider_tls()
    render_started = asyncio.Event()
    budget = ConnectionBudget()
    native_registry = create_default_tts_registry()
    state: dict[str, Any] = {
        "mode": "external" if external else "wire-fixture",
        "status": "ok",
        "connections": 0,
        "speak_attempts": 0,
        "sessions": 0,
        "old_terminal": False,
        "cancel_ack": False,
        "render_gate_released": False,
        "incoming": [],
        "outgoing": [],
        "audio_bytes": 0,
        "speech_id_hashes": [],
    }
    services = []
    timers = []
    speech_ids = []
    owned_connections = []

    def fail(reason: str) -> None:
        if state["status"] == "ok":
            state["status"] = reason
            for service in services:
                connection = getattr(service, "_websocket", None)
                transport = getattr(connection, "transport", None)
                if transport is not None:
                    transport.abort()

    class GatedASR(local.LocalASR):
        async def process_frame(self, frame: Any, direction: Any) -> None:
            if (
                isinstance(frame, InputAudioRawFrame)
                and self.partial_sent
                and not render_started.is_set()
            ):
                await FrameProcessor.process_frame(self, frame, direction)
                self.audio_ms += (
                    len(frame.audio) / (frame.sample_rate * frame.num_channels * 2) * 1000
                )
                await self.push_frame(frame, direction)
                return
            await super().process_frame(frame, direction)

    class FixedLLM(local.LocalLLM):
        async def _process_context(self, context: Any) -> None:
            version = self.response_scope.provenance(context)
            if version is None or version.text not in {"local partial", "local final"}:
                raise ValueError("Unexpected fixed inference input")
            await self.push_frame(LLMTextFrame(TEXTS[version.text == "local final"]))

    class BoundedRegistry:
        providers = ["deepgram_flux"]

        def create(self, **kwargs: Any) -> Any:
            config, audio = kwargs["config"], kwargs["audio"]
            if (
                services
                or state.get("stopped")
                or kwargs.get("response_owner") is None
                or kwargs["provider"] != "deepgram_flux"
                or config.voice != "flux-alexis-en"
                or config.speed != 1
                or config.expressivity != 0
                or config.dynamic_speed_enabled
                or audio.output_sample_rate != 24000
            ):
                fail("registry_scope_error")
                raise ValueError("Unexpected TTS creation")
            kwargs["api_key"] = key
            service = native_registry.create(**kwargs)
            service._append_trailing_space = False
            services.append(service)
            original_connect = service._websocket_connect
            send, receive, raw_audio = (
                service._transport_send_json,
                service._handle_message,
                service._handle_audio,
            )

            async def connect(url: str, **options: Any) -> Any:
                query = parse_qs(urlsplit(url).query)
                if (
                    state["status"] != "ok"
                    or state.get("stopped")
                    or urlsplit(url).hostname != "api.deepgram.com"
                    or urlsplit(url).path != "/v2/speak"
                    or query.get("model") != ["flux-alexis-en"]
                    or query.get("sample_rate") != ["24000"]
                    or query.get("encoding") != ["linear16"]
                ):
                    fail("connection_scope_error")
                    raise ValueError("Unexpected vendor connection")
                state["connections"] += 1
                if not external:
                    connection = WireFixture()
                    owned_connections.append(connection)
                    return connection
                token = VENDOR_CONNECT.set(True)
                try:
                    connection = await original_connect(url, close_timeout=1, **options)
                finally:
                    VENDOR_CONNECT.reset(token)

                owned_connections.append(connection)

                def deadline() -> None:
                    if connection.state.name == "OPEN":
                        fail("connection_deadline")
                        connection.transport.abort()

                timers.append(asyncio.get_running_loop().call_later(25, deadline))
                return connection

            service._websocket_connect = budget.async_connector(connect)

            async def guarded_send(message: dict[str, Any]) -> None:
                if state.get("stopped") or state["status"] != "ok":
                    raise ValueError("Batch already stopped")
                kind = message.get("type")
                if kind == "Speak":
                    index = state["speak_attempts"]
                    if (
                        state["status"] != "ok"
                        or index >= 2
                        or message != {"type": "Speak", "text": TEXTS[index]}
                        or (index == 1 and not (state["old_terminal"] or state["cancel_ack"]))
                    ):
                        fail("speak_scope_error")
                        raise ValueError("Unexpected Speak or absent wire boundary")
                    state["speak_attempts"] += 1
                elif kind == "Configure":
                    if message != {"type": "Configure", "speed": 1.0}:
                        fail("configure_scope_error")
                        raise ValueError("Unexpected Configure")
                elif kind not in {"Interrupt", "Flush"} or message != {"type": kind}:
                    fail("control_scope_error")
                    raise ValueError("Unexpected protocol control")
                state["outgoing"].append(kind)
                await send(message)

            async def observed_message(message: dict[str, Any]) -> None:
                kind = message.get("type")
                if kind in {
                    "Connected",
                    "SpeechStarted",
                    "SpeechMetadata",
                    "SpeechInterrupted",
                    "Flushed",
                    "ConfigureSuccess",
                    "ConfigureFailure",
                    "Error",
                    "Warning",
                }:
                    state["incoming"].append(kind)
                if kind in {"ConfigureFailure", "Error"}:
                    fail("provider_error")
                metadata = message.get("metadata")
                metadata = metadata if isinstance(metadata, dict) else message
                identity = metadata.get("speech_id")
                if kind == "SpeechStarted":
                    if not isinstance(identity, str) or not 0 < len(identity) <= 256:
                        fail("speech_identity_missing")
                    else:
                        speech_ids.append(identity)
                        state["speech_id_hashes"].append(
                            hashlib.sha256(identity.encode()).hexdigest()
                        )
                if kind == "SpeechMetadata" and state["speak_attempts"] == 1:
                    try:
                        require_old_identity(identity, speech_ids)
                    except ValueError:
                        fail("terminal_identity_mismatch")
                        raise
                    state["old_terminal"] = True
                if kind == "SpeechInterrupted":
                    if not speech_ids or identity != speech_ids[0]:
                        fail("cancel_identity_mismatch")
                    else:
                        state["cancel_ack"] = True
                if kind == "Warning":
                    if message.get("code") in {"NO_ACTIVE_SPEECH", "NO_AUDIO_GENERATED"}:
                        state["cancel_ack"] = True
                    else:
                        fail("provider_warning")
                await receive(message)

            async def observed_audio(data: bytes) -> None:
                state["audio_bytes"] += len(data)
                if len(data) % 2 or state["audio_bytes"] > build_plan()["max_audio_bytes"]:
                    fail("audio_format_or_size")
                    raise ValueError("Invalid audio")
                await raw_audio(data)

            service._transport_send_json = guarded_send
            service._handle_message = observed_message
            service._handle_audio = observed_audio
            return service

    local.LocalASR = GatedASR
    local.LocalLLM = FixedLLM
    local.LocalTTSRegistry = BoundedRegistry
    local.block_external_connections = lambda: install_egress_guard(addresses)
    os.environ["VOICE_AGENT_TD_LOCAL_RTP_CANDIDATE"] = "0"
    app = local.create_local_app(data_dir, build_plan()["ui_origin"])
    # Preserve the production lifecycle and providers, replacing only inference and Key injection.
    assert pipeline.prepare_custom_td is local.prepare_local_td
    app.state.tts_probe = state
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def bounded_lifespan(app_instance: Any) -> Any:
        try:
            async with original_lifespan(app_instance) as context:
                yield context
        finally:
            for timer in timers:
                timer.cancel()
            await stop_owned_connections(owned_connections)

    app.router.lifespan_context = bounded_lifespan

    @app.middleware("http")
    async def accepted_render_gate(request: Any, call_next: Any) -> Any:
        if request.method == "POST" and request.url.path == "/api/sessions":
            if state["sessions"] or state["status"] != "ok" or state.get("stopped"):
                from starlette.responses import JSONResponse

                return JSONResponse({"detail": "Single session budget exhausted"}, status_code=409)
            state["sessions"] += 1
        payload = None
        if request.method == "POST" and request.url.path.endswith("/playback-events"):
            payload = await request.json()
        response = await call_next(request)
        if (
            response.status_code == 204
            and isinstance(payload, dict)
            and payload.get("event") == "task_started"
            and payload.get("rendered_samples", 0) > 0
            and state["speak_attempts"] == 1
        ):
            render_started.set()
            state["render_gate_released"] = True
        response.headers["X-VoiceAgent-Test-Fixture"] = "td-local-mixed-tts"
        response.headers["X-VoiceAgent-TTS-Test-Mode"] = state["mode"]
        return response

    @app.get("/__tts_probe")
    async def probe_state() -> dict[str, Any]:
        return state

    app.router.routes.insert(0, app.router.routes.pop())

    @app.post("/__tts_probe/stop")
    async def stop_probe(request: Request) -> dict[str, Any]:
        # This endpoint exists only in the disposable test process, before the SPA fallback.
        from fastapi import HTTPException

        if (
            request.client is None
            or not ipaddress.ip_address(request.client.host).is_loopback
            or request.headers.get("origin") != build_plan()["ui_origin"]
        ):
            raise HTTPException(status_code=403)
        state["stopped"] = True
        await stop_owned_connections(owned_connections)
        for timer in timers:
            timer.cancel()
        return {"stopped": True, "owned_connections": len(owned_connections)}

    app.router.routes.insert(0, app.router.routes.pop())
    return app


def main(argv: list[str] | None = None) -> int:
    """Default to a dry plan; starting a paid fixture requires a new exact batch claim."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--wire-fixture", action="store_true")
    parser.add_argument("--authorization-decision", default="")
    parser.add_argument("--data-dir", type=Path, default=Path("/tmp/td-tts-browser-r96"))
    args = parser.parse_args(argv)
    try:
        plan = build_plan()
        if not args.execute and not args.wire_fixture:
            LOGGER.info("Dry plan: %s", plan["request_sha256"])
            return 0
        if args.data_dir.exists() and any(args.data_dir.iterdir()):
            raise ValueError("Fresh disposable storage required")
        if args.execute:
            verify_authorization(plan, args.authorization_decision)
            claim = (
                ROOT
                / "scripts/vendor/deepgram/logs"
                / (BATCH + "-" + args.authorization_decision + ".log")
            )
            claim.parent.mkdir(parents=True, exist_ok=True)
            with claim.open("x") as output:
                manifest = CHANGE / "verification/delivery-status.json"
                data = json.loads(manifest.read_text())
                grant = next(r for r in data["external_calls"] if r["batch_id"] == BATCH)
                grant["execution_status"] = "started_no_replay"
                manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                output.write(
                    json.dumps(
                        {"status": "claimed_no_replay", "request_sha256": plan["request_sha256"]}
                    )
                    + "\n"
                )
            addresses = {
                item[4][0]
                for item in socket.getaddrinfo("api.deepgram.com", 443, type=socket.SOCK_STREAM)
            }
            if not addresses or not all(ipaddress.ip_address(ip).is_global for ip in addresses):
                raise ValueError("Non-public vendor address")
            key = local_key()
        else:
            addresses, key = set(), "inert-wire-fixture-key"
        from loguru import logger

        logger.remove()
        logging.getLogger().setLevel(logging.CRITICAL)
        import uvicorn

        app = create_mixed_app(args.data_dir, key=key, external=args.execute, addresses=addresses)
        uvicorn.run(app, host="127.0.0.1", port=18996, access_log=False)
        if args.execute:
            with claim.open("a") as output:
                output.write(json.dumps(app.state.tts_probe) + "\n")
        return 0
    except Exception:
        LOGGER.error("Stopped: authorization or isolated fixture preparation failed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
