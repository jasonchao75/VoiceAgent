"""Finite D-064 native RTP/production serial actor scenarios, with local resources."""

import asyncio
import json
import math
import struct
import tempfile
from pathlib import Path

from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from aiortc.rtp import RtpPacket, is_rtcp
from pipecat.frames.frames import InterruptionFrame, OutputTransportMessageFrame, StartFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.workers.runner import WorkerRunner

from src.config import TTSConfig
from src.history.capture import CallCapture
from src.pipeline.audio_identity import TaskAudioFrame
from src.pipeline.echo_audio import EchoAudio
from src.pipeline.identifier_output import IdentifierOutput
from src.pipeline.response_revision import ResponseRevisions
from src.pipeline.rtp_mapping import MappedOpusEncoder, MappedRawAudioTrack, RTPTaskLedger
from src.pipeline.rtp_output import RTPCandidateWriter
from src.pipeline.serial_output import SerialAudioOutput
from src.tts.echo_cache import EchoAudioCache
from tests.test_td_identifier_output import view
from tests.test_td_identifier_rules import policy


def pcm(frequency: int = 1000, samples: int = 7440) -> bytes:
    """Generate bounded synthetic mono PCM locally, without a provider."""
    return b"".join(
        struct.pack("<h", round(10000 * math.sin(n * 2 * math.pi * frequency / 24000)))
        for n in range(samples)
    )


class SerialRTCFixture:
    """Join real serial/identifier actors to the finite RTP candidate, not production routes."""

    def __init__(self, scenario: str) -> None:
        """Own one local peer, scope, cache and evidence stream."""
        if scenario not in {"final", "identifier"}:
            raise ValueError("Unknown finite scenario")
        self.scenario = scenario
        self.peer = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        self.capture = CallCapture(provider="local-fixture", model="synthetic")
        self.responses = ResponseRevisions()
        self.output = SerialAudioOutput(
            responses=self.responses, evidence_sink=self.capture.record_td_event
        )
        self.capture.playback_listener = self.output.receipt
        self.ledger = RTPTaskLedger()

        class BoundedTrack(MappedRawAudioTrack):
            """A finite repair confirmation cannot emit more than two seconds of media."""

            async def recv(self):
                """Stop the local source independently of browser cleanup or assertions."""
                if self._timestamp >= 48000:
                    raise MediaStreamError
                return await super().recv()

        self.track = BoundedTrack(24000, self.ledger)
        self.channel = None
        self.messages = []
        self.receipts = []
        self.actions = []
        self.jobs = set()
        self.ready = asyncio.Event()
        self.marker = asyncio.Event()
        self.runner_task = None
        self.echo = None
        self.cache = None
        self.writer = RTPCandidateWriter(self.track, self.emit)
        owner = self

        class Sink(FrameProcessor):
            """Keep normal SDK actor dispatch, adapting only its final transport boundary."""

            async def process_frame(self, frame, direction):
                """Route exact task PCM/control into native RTP and the control sidecar."""
                await super().process_frame(frame, direction)
                if isinstance(frame, StartFrame):
                    owner.ready.set()
                elif isinstance(frame, TaskAudioFrame):
                    owner.writer.audio(frame)
                elif getattr(frame, "message", {}).get("label") == "voice-agent-playback":
                    owner.writer.control(frame.message)
                elif getattr(frame, "message", {}).get("event") == "fixture_marker":
                    owner.marker.set()
                await self.push_frame(frame, direction)

        self.worker = PipelineWorker(Pipeline([self.output, Sink()]), enable_rtvi=False)
        self.runner = WorkerRunner(handle_sigint=False)
        sender = self.peer.addTrack(self.track)
        sender._RTCRtpSender__encoder = MappedOpusEncoder(self.ledger)
        original_send = sender.transport._send_rtp

        async def send_rtp(payload):
            """Bind actual serialized wire packets before passing them unchanged to DTLS."""
            if not is_rtcp(payload):
                self.emit(
                    {"event": "mapping", "mapping": self.ledger.bind_rtp(RtpPacket.parse(payload))}
                )
            await original_send(payload)

        sender.transport._send_rtp = send_rtp

        @self.peer.on("datachannel")
        def connected(channel):
            """Accept fixture commands and genuine renderer receipts from this peer only."""

            @channel.on("message")
            def message(value):
                """Keep receipt handling on the same event loop as the playback authority."""
                if value == "ready" and self.channel is None:
                    self.channel = channel
                    for item in self.messages:
                        channel.send(json.dumps(item))
                    self.job(self.start())
                elif value != "ready":
                    self.receive(json.loads(value))

    def job(self, coroutine) -> None:
        """Retain finite actor actions for cleanup and error visibility."""
        task = asyncio.create_task(coroutine)
        self.jobs.add(task)

    def emit(self, message: dict) -> None:
        """Send bounded control records only; PCM always travels through RTP."""
        if len(self.messages) >= 1000:
            raise ValueError("Finite candidate control record limit")
        self.messages.append(message)
        if self.channel and self.channel.readyState == "open":
            self.channel.send(json.dumps(message))

    async def answer(self, data: dict, *, timeout: float = 8.0) -> dict:
        """Perform bounded local SDP setup without STUN or remote providers."""
        async with asyncio.timeout(timeout):
            await self.peer.setRemoteDescription(RTCSessionDescription(**data))
            await self.peer.setLocalDescription(await self.peer.createAnswer())
        return {"sdp": self.peer.localDescription.sdp, "type": self.peer.localDescription.type}

    async def stream(self, identity: str, *, response=None, frequency=3000) -> None:
        """Use the actual serial actor's source fences and immutable preparation record."""
        self.capture.record_td_event(
            {
                "event": "playback_task_prepared",
                "playback_id": identity,
                "kind": "normal",
                "turn_id": 1,
                "response_id": response.response_id if response else None,
            }
        )

        async def samples():
            """Return only one locally generated finite source buffer."""
            yield pcm(frequency)

        await self.output.stream_audio(
            playback_id=identity,
            kind="normal",
            generation=self.output.arbiter.generation,
            source_id="reply",
            revision=2 if response and response.final else 1,
            source_order=2,
            samples=samples(),
            valid=(lambda: self.responses.accepts_output(response.response_id))
            if response
            else lambda: True,
            sample_rate=24000,
            turn_id=1,
        )

    async def start(self) -> None:
        """Start native SDK actors and one scenario after the peer control channel is ready."""
        await self.runner.add_workers(self.worker)
        self.runner_task = asyncio.create_task(self.runner.run())
        await asyncio.wait_for(self.ready.wait(), 2)
        if self.scenario == "final":
            initial = self.responses.submit(
                turn_id="1", source_ids=((0, "a"),), text="partial input", final=False
            )
            self.responses.claim_operation("1", "successful_tool", ((0, "a"),))
            await self.stream("partial-A", response=initial, frequency=1000)
        else:
            self.rules = policy()
            self.cache = EchoAudioCache(Path(tempfile.mkdtemp(prefix="td-rtp-cache-")))
            config = TTSConfig(voice="local-fixture")

            async def synthesize(unit, config, rate, *, timeout):
                """Populate real persistent unit resources with explicit synthetic input."""
                return pcm(1000 if unit == "1" else 2000)

            await self.cache.prepare("local", ["1", "2", "3"], config, 24000, synthesize, timeout=2)
            self.echo = IdentifierOutput(
                collection=self.rules.collection,
                audio=EchoAudio(
                    cache=self.cache,
                    bot_id="local",
                    collection=self.rules.collection,
                    config=config,
                    sample_rate=24000,
                    gap_ms=50,
                    manifest={},
                    synthesize=synthesize,
                    record=lambda event, **fields: self.capture.record_td_event(
                        {"event": event, **fields}
                    ),
                ),
                output=self.output,
                evidence_sink=self.capture.record_td_event,
            )
            current = view("12")
            self.echo.consider(current, self.rules.evaluate(current, "编号"), 1)

    def receive(self, message: dict) -> None:
        """Validate actual render coordinates before releasing any serial slot."""
        if message.get("event") != "receipt":
            self.actions.append(message)
            return
        receipt = message["receipt"]
        accepted = self.capture.playback_receipt(
            receipt["playback_id"],
            receipt["event"],
            receipt["rendered_samples"],
            receipt["elapsed_ms"],
            receipt.get("request_id"),
            render_frame=receipt.get("render_frame"),
            render_sample_rate=receipt.get("render_sample_rate"),
            render_clock_id=receipt.get("render_clock_id"),
        )
        self.receipts.append({**receipt, "accepted": accepted})
        if accepted and receipt["event"] == "task_started" and not self.actions:
            self.actions.append({"event": "scenario_started", "task": receipt["playback_id"]})
            self.job(self.advance())

    async def advance(self) -> None:
        """Drive known Final or identifier continuation/question/clear after actual start."""
        if self.scenario == "final":
            restart = self.responses.finalize(
                turn_id="1", source_ids=((0, "a"),), revision=2, text="final input"
            )
            self.output.revalidate()
            await self.stream("final-B", response=restart.new_response)
            duplicate = self.responses.finalize(
                turn_id="1", source_ids=((0, "a"),), revision=2, text="final input"
            )
            replay = self.responses.claim_operation("1", "successful_tool", ((0, "a"),))
            self.actions.append(
                {
                    "event": "final_replaced",
                    "duplicate_restart": duplicate is not None,
                    "tool_replayed": replay,
                }
            )
        else:
            await self.worker.queue_frame(InterruptionFrame())
            await self.worker.queue_frame(
                OutputTransportMessageFrame(message={"event": "fixture_marker"})
            )
            await asyncio.wait_for(self.marker.wait(), 2)
            # Queue insertion is not completion: observe the SDK marker before
            # preparing the later answer, so continuation cannot cancel it.
            await self.stream("question-Q")
            active = self.output.arbiter._active
            self.actions.append(
                {
                    "event": "continuation_and_question",
                    "active_kind": active.kind,
                    "active_status": active.status,
                    "question_status": self.output.arbiter.tasks["question-Q"].status,
                    "stop_requests": list(self.output.arbiter.stop_requests),
                }
            )
            result = self.rules.collection.clear_tool(
                self.rules.collection.bind_source(0, "clear", 1, "clear")
            )
            self.actions.append(
                {
                    "event": "clear_result",
                    "result": result,
                    "generation": self.rules.collection.generation,
                }
            )

    def result(self) -> dict:
        """Expose actual actor transitions and receipts without asserting untested paths."""
        return {
            "scenario": self.scenario,
            "actions": self.actions,
            "receipts": self.receipts,
            "td_events": self.capture.td_events,
            "user_submissions": self.responses.user_submission_count,
            "tasks": {
                key: {"status": task.status, "kind": task.kind}
                for key, task in self.output.arbiter.tasks.items()
            },
            "job_errors": [
                str(task.exception())
                for task in self.jobs
                if task.done() and not task.cancelled() and task.exception()
            ],
        }

    async def close(self) -> None:
        """Release only resources owned by this finite peer."""
        if self.echo:
            await self.echo.close()
        await self.worker.cancel()
        if self.runner_task:
            await asyncio.wait_for(self.runner_task, 3)
        for job in self.jobs:
            if not job.done():
                job.cancel()
        await asyncio.gather(*self.jobs, return_exceptions=True)
        await self.peer.close()
        if self.cache:
            await self.cache.close()
