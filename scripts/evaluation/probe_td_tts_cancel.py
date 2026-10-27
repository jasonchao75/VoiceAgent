"""Probe one authorized Flux cancellation/replacement through the production SDK queues."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluation.probe_td_compatibility import (  # noqa: E402
    ConnectionBudget,
    local_key,
    verify_authorization,
)

CHANGE = ROOT / 'openspec/changes/archive/2026-10-27-add-jev-semantic-turn-detection'
BATCH = 'deepgram-flux-cancel-replace-r94-v1'
TEXTS = [
    'This fictional booking answer is deliberately long so that the cancellation test can stop '
    'it while it is still being generated, before the replacement answer begins.',
    'This is the replacement answer.',
]
LOGGER = logging.getLogger(__name__)


def build_plan() -> dict[str, Any]:
    """Freeze all chargeable text and safety limits without touching a credential."""
    characters = sum(map(len, TEXTS))
    plan = {'batch_id': BATCH, 'recipient': 'api.deepgram.com',
            'endpoint': 'wss://api.deepgram.com/v2/speak', 'voice': 'flux-alexis-en',
            'texts': TEXTS, 'characters': characters, 'speed': 1., 'expressivity': 0,
            'sample_rate': 24000, 'channels': 1, 'encoding': 'linear16 PCM16',
            'max_connections': 1, 'max_calls': 2, 'timeout_seconds': 30,
            'cancel_ack_timeout_seconds': 2, 'connect_timeout_seconds': 5,
            'cost_ceiling_usd': '0.02', 'usd_per_1000_characters': '0.045',
            'maximum_text_price_usd': str(Decimal(characters) * Decimal('0.045') / 1000),
            'pricing_source': 'https://deepgram.com/pricing', 'price_verified': '2026-10-26',
            'protocol_source': 'https://developers.deepgram.com/docs/flux-tts/interrupt-handling',
            'asr_jev_llm_calls': 0, 'retries': 0, 'account_hard_cap_verified': False,
            'max_audio_bytes': 24000 * 2 * 40,
            'trigger': 'first old SDK output PCM -> fixed Final replacement -> Interrupt -> '
                       'new text',
            'stop': 'first error/format/scope/identity/budget failure; completed old speech or '
                    'no-active warning is untriggered, stop without another Speak; no retry',
            'scope': 'actual TTS SDK/control/PCM provenance only; no browser or physical playback'}
    plan['request_sha256'] = hashlib.sha256(json.dumps(
        plan, sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    return plan


async def run_case(
    key: str, *, timeout: float = 30, connector: Any = None,
) -> dict[str, Any]:
    """Run one exact two-text session; connector injection is for offline tests only.

    Args:
        key: Already authorized local credential, never returned.
        timeout: Whole connection/pipeline/cleanup time budget in seconds.
        connector: Optional in-memory socket factory for the offline SDK test.

    Returns:
        Bounded whitelisted control, PCM count and response identity evidence.
    """
    from pipecat.frames.frames import (
        ErrorFrame,
        InterruptionFrame,
        LLMFullResponseEndFrame,
        LLMFullResponseStartFrame,
        LLMTextFrame,
        StartFrame,
        TTSAudioRawFrame,
        TTSStoppedFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.workers.runner import WorkerRunner

    from src.asr.factory import _configure_provider_tls
    from src.config import AudioConfig, TTSConfig
    from src.pipeline.response_revision import ResponseRevisions
    from src.tts.factory import create_default_tts_registry

    _configure_provider_tls()
    plan = build_plan()
    owner = ResponseRevisions()
    old = owner.submit(turn_id='probe', source_ids=((0, 'synthetic'),),
                       text='Fictional booking question.', final=False)
    service = create_default_tts_registry().create(
        provider='deepgram_flux', api_key=key,
        config=TTSConfig(provider='deepgram_flux', voice=plan['voice'],
                         speed=1., expressivity=0, text_aggregation='token'),
        audio=AudioConfig(output_sample_rate=24000), response_owner=owner,
    )
    service._append_trailing_space = False
    if connector is not None:
        service._websocket_connect = connector
    budget = ConnectionBudget()
    service._websocket_connect = budget.async_connector(service._websocket_connect)
    ready, first_audio, interrupt_sent, finished, failed = (asyncio.Event() for _ in range(5))
    state: dict[str, Any] = {'status': 'ok', 'speak_attempts': 0, 'acknowledged_cancel': False,
                             'old_output_after_cancel_samples': 0, 'new_output_samples': 0,
                             'received_audio_bytes': 0, 'inflight_audio_bytes': 0,
                             'outgoing': [], 'incoming': [], 'billable_character_counts': []}
    speech_ids = []
    cancelled = False

    def stop(reason: str) -> None:
        """Preserve the first fixed failure category and stop all further paid sends."""
        if not failed.is_set():
            state['status'] = reason
        failed.set()

    send, receive, audio = (service._transport_send_json, service._handle_message,
                            service._handle_audio)

    async def guarded_send(message: dict[str, Any]) -> None:
        """Reserve exact Speak attempts before transport; never refund failed sends."""
        kind = message.get('type')
        if kind == 'Speak':
            index = state['speak_attempts']
            if failed.is_set() or index >= 2 or message != {'type': 'Speak', 'text': TEXTS[index]}:
                stop('scope_error')
                raise ValueError('Speak outside frozen scope')
            if index == 1 and not state['acknowledged_cancel']:
                stop('new_speak_before_ack')
                raise ValueError('Cancel boundary absent')
            state['speak_attempts'] += 1
        elif kind == 'Configure':
            if message != {'type': 'Configure', 'speed': 1.}:
                stop('configuration_scope_error')
                raise ValueError('Configure outside frozen scope')
        elif kind in {'Flush', 'Interrupt'}:
            if message != {'type': kind}:
                stop('protocol_scope_error')
                raise ValueError('Unexpected control fields')
        else:
            stop('protocol_scope_error')
            raise ValueError('Unexpected control kind')
        if len(state['outgoing']) < 64:
            state['outgoing'].append(kind)
        if kind == 'Interrupt':
            interrupt_sent.set()
        await send(message)

    async def observed_message(message: dict[str, Any]) -> None:
        """Keep only known kinds/numeric counts and hashes of ordered speech identities."""
        kind = message.get('type')
        if kind in {'Connected', 'ConfigureSuccess', 'ConfigureFailure', 'SpeechStarted',
                    'SpeechMetadata', 'SpeechInterrupted', 'Flushed', 'SessionMetadata',
                    'Warning', 'Error'} and len(state['incoming']) < 64:
            state['incoming'].append(kind)
        if kind in {'Error', 'ConfigureFailure'}:
            stop('provider_error')
        metadata = message.get('metadata')
        metadata = metadata if isinstance(metadata, dict) else message
        speech_id = metadata.get('speech_id')
        if kind == 'SpeechStarted':
            if not isinstance(speech_id, str) or not 0 < len(speech_id) <= 256:
                stop('speech_identity_missing')
            else:
                speech_ids.append(speech_id)
        if kind == 'SpeechMetadata':
            count = metadata.get('billable_character_count')
            if type(count) is int and 0 <= count <= plan['characters']:
                state['billable_character_counts'].append(count)
            if state['speak_attempts'] == 1 and not interrupt_sent.is_set():
                stop('not_triggered:old_completed_before_interrupt')
        if kind == 'SpeechInterrupted':
            if not speech_ids or speech_id != speech_ids[0] or not interrupt_sent.is_set():
                stop('cancel_identity_mismatch')
            else:
                state['acknowledged_cancel'] = True
        if kind == 'Warning' and message.get('code') in {'NO_ACTIVE_SPEECH', 'NO_AUDIO_GENERATED'}:
            stop('not_triggered:no_active_speech')
        elif kind == 'Warning':
            stop('provider_warning')
        await receive(message)

    async def observed_audio(data: bytes) -> None:
        """Observe wire bytes independently from accepted SDK output PCM."""
        state['received_audio_bytes'] += len(data)
        if len(data) % 2 or state['received_audio_bytes'] > plan['max_audio_bytes']:
            stop('audio_format_or_size_error')
            return
        if interrupt_sent.is_set() and not state['acknowledged_cancel']:
            state['inflight_audio_bytes'] += len(data)
        await audio(data)

    service._transport_send_json = guarded_send
    service._handle_message = observed_message
    service._handle_audio = observed_audio

    class Sink(FrameProcessor):
        """Only actual accepted SDK frames prove output; no client playback is inferred."""
        async def process_frame(self, frame: Any, direction: Any) -> None:
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            elif isinstance(frame, ErrorFrame):
                stop('provider_or_pipeline_error')
            elif isinstance(frame, TTSAudioRawFrame):
                if frame.sample_rate != 24000 or frame.num_channels != 1 or len(frame.audio) % 2:
                    stop('output_format_error')
                elif frame.metadata.get('td_response_id') == old.response_id:
                    if cancelled:
                        state['old_output_after_cancel_samples'] += len(frame.audio) // 2
                        stop('old_output_after_cancel')
                    else:
                        first_audio.set()
                elif (
                    cancelled and frame.metadata.get('td_response_id') == owner.current.response_id
                ):
                    state['new_output_samples'] += len(frame.audio) // 2
                else:
                    stop('output_identity_missing')
            elif isinstance(frame, TTSStoppedFrame) and cancelled:
                if frame.metadata.get('td_response_id') == owner.current.response_id:
                    finished.set()
            await self.push_frame(frame, direction)

    worker = PipelineWorker(Pipeline([service, Sink()]),
                            params=PipelineParams(audio_out_sample_rate=24000), enable_rtvi=False)
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())

    async def wait(event: asyncio.Event, seconds: float) -> None:
        """A first provider error wins over waiting for another expected frame."""
        wanted = asyncio.create_task(event.wait())
        aborted = asyncio.create_task(failed.wait())
        try:
            await asyncio.wait_for(asyncio.wait([wanted, aborted],
                                               return_when=asyncio.FIRST_COMPLETED), seconds)
            if failed.is_set():
                raise ValueError('Probe stopped')
        finally:
            wanted.cancel()
            aborted.cancel()
            await asyncio.gather(wanted, aborted, return_exceptions=True)

    async def text(version: Any, value: str) -> None:
        """Use actual response metadata on the same production LLM-to-TTS frames."""
        frames = [LLMFullResponseStartFrame(), LLMTextFrame(value), LLMFullResponseEndFrame()]
        for frame in frames:
            frame.metadata['td_response_id'] = version.response_id
        await worker.queue_frames(frames)

    try:
        async with asyncio.timeout(timeout - 3):
            await wait(ready, 5)
            await text(old, TEXTS[0])
            await wait(first_audio, 10)
            owner.finalize(turn_id='probe', source_ids=((0, 'synthetic'),), revision=2,
                           text='Fictional revised booking question.')
            cancelled = True
            await worker.queue_frame(InterruptionFrame())
            await wait(interrupt_sent, 3)
            await text(owner.current, TEXTS[1])
            await wait(finished, 10)
    except TimeoutError:
        stop('timeout')
    except Exception:
        if not failed.is_set():
            stop('local_or_provider_error')
    finally:
        try:
            await asyncio.wait_for(worker.cancel(), 1)
            await asyncio.wait_for(running, 2)
        except TimeoutError:
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
    state.update(connections=budget.attempts,
                 speech_id_hashes=[hashlib.sha256(x.encode()).hexdigest() for x in speech_ids],
                 scope=plan['scope'], actual_billed_cost_usd=None)
    if state['status'] == 'ok' and not (
        state['connections'] == 1 and state['speak_attempts'] == 2
        and state['acknowledged_cancel'] and state['new_output_samples'] > 0
    ):
        state['status'] = 'incomplete_evidence'
    return state


def main(argv: list[str] | None = None) -> int:
    """Claim a single reviewed batch before key access; no implicit replay or retry."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization-decision', default='')
    args = parser.parse_args(argv)
    try:
        plan = build_plan()
        if not args.execute:
            LOGGER.info('Dry plan: sha256=%s', plan['request_sha256'])
            return 0
        verify_authorization(plan, args.authorization_decision)
        path = ROOT / 'scripts/vendor/deepgram/logs' / (
            BATCH + '-' + args.authorization_decision + '.log')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as output:
            manifest = CHANGE / 'verification/delivery-status.json'
            data = json.loads(manifest.read_text())
            grant = next(row for row in data['external_calls'] if row['batch_id'] == BATCH)
            grant['execution_status'] = 'started_no_replay'
            manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
            output.write(json.dumps({'status': 'claimed_no_replay',
                                     'request_sha256': plan['request_sha256']}) + '\n')
            output.flush()
            from loguru import logger
            logger.remove()
            logging.getLogger().setLevel(logging.CRITICAL)
            result = asyncio.run(run_case(local_key()))
            output.write(json.dumps(result) + '\n')
        return 0 if result['status'] == 'ok' else 1
    except Exception:
        LOGGER.error('Stopped: authorization or local probe boundary failed')
        return 2


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
