"""Run explicitly authorized synthetic batches through the production ASR adapters."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import subprocess
import sys
import time
import wave
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHANGE = ROOT / 'openspec/changes/archive/2026-10-27-add-jev-semantic-turn-detection'
BATCH_ID = 'deepgram-td-asr-synthetic-v1'
LOGGER = logging.getLogger(__name__)


def build_plan(
    *, diagnostic: bool = False, repair_confirmation: bool = False,
    fresh_digits: bool = False,
    remaining_deepgram: bool = False,
    single_vendor: str | None = None,
) -> dict[str, Any]:
    """Freeze nine model/file pairs and conservative public-price connection bounds."""
    if sum((diagnostic, repair_confirmation, fresh_digits, remaining_deepgram,
            single_vendor is not None)) > 1:
        raise ValueError('Choose one exact batch scope')
    if single_vendor not in {None, 'assemblyai', 'speechmatics', 'soniox'}:
        raise ValueError('Unsupported exact batch scope')
    data = json.loads((CHANGE / 'verification/vendor-synthetic-data.json').read_text())['data']
    cases = []
    for model in ('flux-general-en', 'flux-general-multi', 'nova-3'):
        for row in data:
            cases.append({**row, 'model': model, 'provider': 'deepgram',
                          'options': {'language': 'en'} if model == 'nova-3' else {},
                          'silence_tail_seconds': 3})
    maximum = Decimal(len(cases)) * Decimal('0.5') * Decimal('0.0078')
    plan: dict[str, Any] = {'batch_id': BATCH_ID, 'cases': cases, 'max_calls': 9,
            'connection_wall_seconds': 30, 'connect_timeout_seconds': 5,
            'cost_ceiling_usd': '0.10', 'maximum_public_price_usd': str(maximum),
            'price_verified': '2026-10-22', 'pricing_source': 'https://deepgram.com/pricing',
            'turn_detection_source': 'self_developed', 'retries': 0,
            'recipient': 'api.deepgram.com', 'llm_jev_tts_calls': 0}
    if diagnostic:
        plan.update(batch_id='deepgram-td-asr-range-diagnostic-v1', cases=cases[:1],
                    max_calls=1, cost_ceiling_usd='0.02', maximum_public_price_usd='0.00325',
                    source_evidence='whitelisted provider timestamps and words; stop first gap')
    if repair_confirmation:
        digits = next(row for row in cases
                      if row['model'] == 'flux-general-en' and row['id'] == 'digits')
        plan.update(batch_id='deepgram-td-asr-digits-confirmation-v1', cases=[digits],
                    max_calls=1, cost_ceiling_usd='0.02', maximum_public_price_usd='0.00325',
                    source_evidence='known PCM rate, raw times, normalized ranges; stop first gap')
    if fresh_digits or remaining_deepgram or single_vendor:
        plan.update(
            batch_id='deepgram-td-fresh-digits-confirmation-v1',
            cases=[{
                'id': 'fresh-digits',
                'path': str(ROOT / 'test-results/td-vendor-inputs/20261024/digits-ready.wav'),
                'sha256': 'a93499196b16dd1e9307ba97bedd24d246dedf995755e05bc9f20e382139966e',
                'duration_seconds': 5.1675,
                'text': 'One two three. Four five six. Seven eight nine.',
                'provider': 'deepgram', 'model': 'flux-general-en', 'options': {},
                'silence_tail_seconds': 3,
            }],
            max_calls=1, cost_ceiling_usd='0.02', maximum_public_price_usd='0.00385',
            price_verified='2026-10-25',
            public_price_bound='USD0.0077/min regular price times 30 seconds; no promotion assumed',
            source_evidence='new pinned PCM; existing sample-boundary repair; stop first gap',
        )
        if remaining_deepgram:
            sample = plan['cases'][0]
            plan.update(
                batch_id='deepgram-td-remaining-models-v1',
                cases=[{**sample, 'model': model,
                        'options': {'language': 'en'} if model == 'nova-3' else {}}
                       for model in ('flux-general-multi', 'nova-3')],
                max_calls=2, maximum_public_price_usd='0.00850',
                public_price_bound='30s each at USD0.0078/min Flux multilingual and '
                                   'USD0.0092/min conservative Nova3 upper regular rate',
            )
        if single_vendor:
            is_assembly = single_vendor == 'assemblyai'
            sample = plan['cases'][0]
            plan.update(
                batch_id=f'{single_vendor}-td-single-digits-v1',
                recipient=('streaming.assemblyai.com' if is_assembly
                           else 'eu2.rt.speechmatics.com'),
                cases=[{**sample, 'provider': single_vendor,
                        'model': 'universal-3-5-pro' if is_assembly else 'enhanced',
                        'options': {'language_codes': ['en']} if is_assembly
                        else {'language': 'en'}}],
                maximum_public_price_usd='0.00375' if is_assembly else '0.00667',
                public_price_bound='30s at USD0.45/hr' if is_assembly
                else '30s at USD0.80/hr; real-time with quotation discounts disabled',
                pricing_source='https://www.assemblyai.com/products/streaming-speech-to-text'
                if is_assembly else 'https://www.speechmatics.com/pricing',
                price_verified='2026-10-25',
            )
            if single_vendor == 'soniox':
                plan.update(
                    recipient='stt-rt.soniox.com',
                    cases=[{**sample, 'provider': 'soniox', 'model': 'stt-rt-v5',
                            'options': {'language_hints': ['en']},
                            'max_received_tokens': 1000}],
                    maximum_public_price_usd='0.018', estimated_reserve_usd='0.018',
                    vendor_enforced_cost_cap=False,
                    public_price_bound='Budget reserve, not guaranteed billing cap: '
                    '1000 audio tokens at USD2/M plus 4000 text tokens at USD4/M; '
                    '1000 reported tokens stops client with in-flight headroom; '
                    'no context/translation',
                    pricing_source='https://soniox.com/pricing',
                )
    plan['request_sha256'] = hashlib.sha256(json.dumps(
        plan, sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    if len(plan['cases']) != plan['max_calls'] or (
        Decimal(plan['maximum_public_price_usd']) > Decimal(plan['cost_ceiling_usd'])
    ):
        raise ValueError('Invalid bounded batch')
    return plan


def verify_files(plan: dict[str, Any]) -> None:
    """Reject missing, changed, empty or wrongly formatted media before reading a key."""
    for row in plan['cases']:
        path = Path(row['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Authorized data hash changed')
        with wave.open(str(path), 'rb') as stream:
            audio_format = (stream.getframerate(), stream.getnchannels(), stream.getsampwidth())
            if audio_format != (16000, 1, 2):
                raise ValueError('Authorized media format changed')
            if stream.getnframes() <= 0 or stream.getnframes() / 16000 != row['duration_seconds']:
                raise ValueError('Authorized media duration changed')


class ConnectionBudget:
    """Allow one socket attempt per fixed case, including failed handshakes."""

    def __init__(self) -> None:
        """Initialize a consumed-before-attempt budget; retries cannot reclaim it."""
        self.attempts = 0

    def _claim(self) -> None:
        """Fail before a connector could initiate an unauthorized second handshake."""
        if self.attempts:
            raise RuntimeError('Connection budget exhausted')
        self.attempts += 1

    def async_connector(self, original: Any) -> Any:
        """Wrap the existing Flux connector without changing headers or TLS."""
        async def connect(*args: Any, **kwargs: Any) -> Any:
            """Claim before awaiting the real network handshake."""
            self._claim()
            return await asyncio.wait_for(original(*args, **kwargs), timeout=5)
        return connect

    def context_connector(self, original: Any) -> Any:
        """Wrap Nova's existing SDK context factory before it opens a socket."""
        from contextlib import asynccontextmanager

        def connect(**kwargs: Any) -> Any:
            """Claim before constructing the connection lifecycle."""
            self._claim()

            @asynccontextmanager
            async def bounded() -> Any:
                """Bound the handshake separately from the streaming session."""
                manager = original(**kwargs)
                connection = await asyncio.wait_for(manager.__aenter__(), timeout=5)
                try:
                    yield connection
                finally:
                    await asyncio.wait_for(manager.__aexit__(None, None, None), timeout=1)

            return bounded()
        return connect


class TokenBoundSocket:
    """Stop a synthetic Soniox probe on excessive received tokens, without changing PCM.

    This is a client stop guard, not an account-level vendor billing cap.
    """

    def __init__(self, socket: Any, *, limit: int) -> None:
        """Wrap one authorized connection with a conservative repeated-token counter."""
        self.socket = socket
        self.iterator = socket.__aiter__()
        self.limit = limit
        self.tokens = 0
        self.exhausted = False

    def __getattr__(self, name: str) -> Any:
        """Delegate state and ordinary connection operations to the original SDK socket."""
        return getattr(self.socket, name)

    def __aiter__(self) -> Any:
        """Expose the native receive iterator with the token stop guard."""
        return self

    async def __anext__(self) -> Any:
        """Count every raw reported token before the SDK can process another response."""
        if self.exhausted:
            raise RuntimeError('Received token budget exhausted')
        message = await anext(self.iterator)
        try:
            value = json.loads(message)
            tokens = value.get('tokens') if isinstance(value, dict) else None
            if isinstance(tokens, list):
                self.tokens += len(tokens)
        except (ValueError, TypeError):
            pass
        if self.tokens > self.limit:
            self.exhausted = True
            await asyncio.wait_for(self.socket.close(), timeout=1)
            raise RuntimeError('Received token budget exhausted')
        return message

    async def send(self, data: Any) -> Any:
        """Reject additional audio or controls once the client stop limit has fired."""
        if self.exhausted:
            raise RuntimeError('Received token budget exhausted')
        return await self.socket.send(data)


def verify_authorization(plan: dict[str, Any], decision: str) -> None:
    """Require the same exact-scope decision/manifest contract used for Jev batches."""
    import re

    if not re.fullmatch(r'D-\d+', decision):
        raise ValueError('Explicit batch decision required')
    manifest = json.loads((CHANGE / 'verification/delivery-status.json').read_text())
    grant: dict[str, Any] = next((row for row in manifest['external_calls']
                  if row.get('batch_id') == plan['batch_id']
                  and row.get('authorization_decision_id') == decision), {})
    if grant.get('authorization_status') != 'confirmed' or any(
        grant.get(field) != plan[field]
        for field in ('request_sha256', 'max_calls', 'cost_ceiling_usd')
    ):
        raise ValueError('Matching authorization absent')
    if grant.get('execution_status') != 'authorized_not_started':
        raise ValueError('Grant is already started or consumed')
    source = (CHANGE / 'decisions/decision-log.md').read_text()
    block = re.search(rf'(?ms)^### {re.escape(decision)}\b[^\n]*\n(.*?)(?=^### |\Z)', source)
    if not block or '- Status: Confirmed' not in block[1] or not all(
        re.search(rf'(?m)^- {label}:[ \t]*\S[^\n]*$', block[1])
        for label in ('Confirmation quote', 'Source thread/message')
    ):
        raise ValueError('Human confirmation source absent')


def local_key(provider: str = 'deepgram') -> str:
    """Read only the ignored local credential after explicit batch authorization."""
    from dotenv import dotenv_values

    subprocess.run(['git', 'check-ignore', '-q', '.env'], cwd=ROOT,
                   capture_output=True, check=True)
    names = {'deepgram': 'DEEPGRAM_API_KEY', 'assemblyai': 'ASSEMBLYAI_API_KEY',
             'speechmatics': 'SPEECHMATICS_API_KEY', 'soniox': 'SONIOX_API_KEY'}
    key = dotenv_values(ROOT / '.env').get(names[provider]) or ''
    if not key.strip():
        raise ValueError('Local credential absent')
    return key.strip()


def guard_connection(processor: Any, provider: str, model: str,
                     budget: ConnectionBudget) -> Any:
    """Bound the actual SDK handshake and return its process-local restoration callback."""
    if provider == 'speechmatics':
        from speechmatics.rt._transport import Transport

        original = Transport.connect
        Transport.connect = budget.async_connector(original)
        return lambda: setattr(Transport, 'connect', original)
    if provider == 'deepgram' and model == 'nova-3':
        client = processor._client.listen.v1
        original = client.connect
        client.connect = budget.context_connector(original)
        return lambda: setattr(client, 'connect', original)
    if provider not in {'deepgram', 'assemblyai', 'soniox'}:
        raise ValueError('Unsupported provider handshake')
    original = processor._websocket_connect
    processor._websocket_connect = budget.async_connector(original)
    return lambda: setattr(processor, '_websocket_connect', original)


def source_evidence(raw: Any, *, depth: int = 0) -> dict[str, Any]:
    """Whitelist bounded provider timing fields, retaining explicit null evidence.

    Args:
        raw: Provider payload or one of its known nested timing records.
        depth: Structural depth budget; arbitrary metadata is never copied.

    Returns:
        Safe timestamp, word and segment schema evidence without headers or credentials.
    """
    if depth > 3:
        return {}
    if isinstance(raw, list):
        return {'tokens': [source_evidence(item, depth=depth + 1)
                           for item in raw[:256] if isinstance(item, dict)]}
    if not isinstance(raw, dict):
        return {}
    evidence: dict[str, Any] = {}
    for field in ('event', 'message', 'type', 'turn_index', 'turn_order',
                  'audio_window_start', 'audio_window_end', 'start', 'end', 'duration',
                  'start_time', 'end_time', 'start_ms', 'end_ms',
                  'is_final', 'end_of_turn', 'turn_is_formatted',
                  'word', 'text', 'content', 'word_is_final', 'speaker_id'):
        value = raw.get(field)
        if field in raw and (value is None or isinstance(value, (str, int, float, bool))):
            evidence[field] = value[:4096] if isinstance(value, str) else value
    for field in ('words', 'segments', 'fragments', 'tokens'):
        value = raw.get(field)
        if field in raw and value is None:
            evidence[field] = None
        elif isinstance(value, list):
            evidence[field] = [source_evidence(item, depth=depth + 1)
                               for item in value[:256] if isinstance(item, dict)]
    if isinstance(raw.get('metadata'), dict):
        evidence['metadata'] = source_evidence(raw['metadata'], depth=depth + 1)
    return evidence


async def run_case(row: dict[str, Any], key: str, *, timeout: float = 30) -> dict[str, Any]:
    """Stream one fixed clip through the production factory, SDK and normalizer.

    Args:
        row: Frozen authorized model/media record.
        key: Local backend credential, never returned.
        timeout: Total processor lifecycle deadline; includes connection and silence.

    Returns:
        Safe evidence and explicit compatibility status, never arbitrary provider errors.
    """
    from pipecat.frames.frames import (
        ErrorFrame,
        InputAudioRawFrame,
        InterimTranscriptionFrame,
        StartFrame,
        TranscriptionFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.workers.runner import WorkerRunner

    from src.asr.factory import create_default_asr_registry
    from src.asr.turn_events import SourceNormalizer
    from src.config import AudioConfig

    provider = row.get('provider', 'deepgram')
    service = create_default_asr_registry().create(
        provider=provider, model=row['model'], turn_detection_source='self_developed',
        options=row['options'], api_key=key, audio=AudioConfig(),
    )
    processor: Any = service.processor
    selected_normalizer = service.source_normalizer
    if selected_normalizer is None:
        raise RuntimeError('Production source normalizer missing')
    normalizer: SourceNormalizer = selected_normalizer
    budget = ConnectionBudget()
    if provider == 'speechmatics':
        processor._base_url = 'wss://eu2.rt.speechmatics.com/v2'
    restore_connection = guard_connection(processor, provider, row['model'], budget)
    token_socket: TokenBoundSocket | None = None
    if provider == 'soniox':
        guarded = processor._websocket_connect

        async def token_bounded_connect(*args: Any, **kwargs: Any) -> Any:
            """Add a receive guard only to this bounded probe's real connection."""
            nonlocal token_socket
            token_socket = TokenBoundSocket(await guarded(*args, **kwargs),
                                            limit=row['max_received_tokens'])
            return token_socket

        processor._websocket_connect = token_bounded_connect
    ready, failed, range_failed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    events: list[dict[str, Any]] = []

    class Sink(FrameProcessor):
        """Observe only public transcription frames; do not log raw exceptions or headers."""
        async def process_frame(self, frame: Any, direction: Any) -> None:
            """Preserve source evidence at the same boundary used by CustomTDCoordinator."""
            await super().process_frame(frame, direction)
            if isinstance(frame, ErrorFrame):
                failed.set()
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, (InterimTranscriptionFrame, TranscriptionFrame)):
                segments = service.normalize_source_frame(frame)
                raw = frame.result
                if raw is not None and hasattr(raw, 'model_dump'):
                    raw = raw.model_dump()
                evidence = source_evidence(raw)
                events.append({'frame': type(frame).__name__, 'text': frame.text,
                               'missing_reason': normalizer.missing_reason,
                               'source_evidence': evidence,
                               'segments': [{'epoch': s.epoch, 'id': s.source_id,
                                             'revision': s.revision, 'start_ms': s.start_ms,
                                             'end_ms': s.end_ms, 'final': s.final,
                                             'sample_rate': s.sample_rate,
                                             'text': s.text} for s in segments]})
                if normalizer.missing_reason:
                    range_failed.set()
                    failed.set()
            await self.push_frame(frame, direction)

    worker = PipelineWorker(Pipeline([processor, Sink()]), enable_rtvi=False,
                            params=PipelineParams(audio_in_sample_rate=16000))
    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    await runner.add_workers(worker)
    started = time.monotonic()
    running = asyncio.create_task(runner.run())

    async def stream() -> None:
        """Pace the exact authorized input and three seconds of explicitly listed silence."""
        await asyncio.wait_for(ready.wait(), timeout=5)
        with wave.open(row['path'], 'rb') as audio:
            pcm = audio.readframes(audio.getnframes()) + bytes(16000 * 2 * 3)
        for offset in range(0, len(pcm), 640):
            if failed.is_set():
                return
            await worker.queue_frame(InputAudioRawFrame(pcm[offset:offset + 640], 16000, 1))
            await asyncio.sleep(.02)
        await asyncio.sleep(1)

    task = asyncio.create_task(stream())
    failure = asyncio.create_task(failed.wait())
    status = 'ok'
    try:
        async with asyncio.timeout(timeout - 3):
            done, _ = await asyncio.wait([task, failure, running],
                                         return_when=asyncio.FIRST_COMPLETED)
            if task in done:
                await task
            else:
                status = 'provider_or_pipeline_error'
    except TimeoutError:
        status = 'timeout'
    except Exception:
        status = 'local_or_provider_error'
    finally:
        if range_failed.is_set():
            status = 'transcript_or_range_missing'
        elif failed.is_set():
            status = 'provider_or_pipeline_error'
        task.cancel()
        failure.cancel()
        await asyncio.gather(task, failure, return_exceptions=True)
        try:
            await asyncio.wait_for(worker.cancel(), timeout=1)
            await asyncio.wait_for(running, timeout=1)
        except TimeoutError:
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
        finally:
            restore_connection()
    if status == 'ok' and (not events or any(e['missing_reason'] for e in events)):
        status = 'transcript_or_range_missing'
    if status == 'ok' and not any(e['segments'] for e in events):
        status = 'normalized_segments_missing'
    safe = {'provider': provider, 'model': row['model'], 'data_id': row['id'], 'status': status,
            'connections': budget.attempts, 'elapsed_ms': (time.monotonic() - started) * 1000,
            'events': events}
    if token_socket is not None:
        safe['receive_budget'] = {'reported_tokens_including_revisions': token_socket.tokens,
                                  'limit': token_socket.limit, 'exhausted': token_socket.exhausted}
    # A synthetic-data provider response still must not be able to echo a credential to disk.
    return json.loads(json.dumps(safe).replace(key, '[REDACTED]'))


def main(argv: list[str] | None = None) -> int:
    """Default to a dry plan; execution consumes one exclusive authorization claim."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization-decision', default='')
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--diagnostic', action='store_true')
    scope.add_argument('--repair-confirmation', action='store_true')
    scope.add_argument('--fresh-digits', action='store_true')
    scope.add_argument('--remaining-deepgram', action='store_true')
    scope.add_argument('--single-vendor', choices=['assemblyai', 'speechmatics', 'soniox'])
    args = parser.parse_args(argv)
    try:
        plan = build_plan(
            diagnostic=args.diagnostic, repair_confirmation=args.repair_confirmation,
            fresh_digits=args.fresh_digits,
            remaining_deepgram=args.remaining_deepgram,
            single_vendor=args.single_vendor,
        )
        verify_files(plan)
        if not args.execute:
            LOGGER.info('Dry plan: %s calls=%s ceiling=USD%s sha256=%s', plan['batch_id'],
                        plan['max_calls'], plan['cost_ceiling_usd'], plan['request_sha256'])
            return 0
        verify_authorization(plan, args.authorization_decision)
        provider = plan['cases'][0]['provider']
        key = local_key() if provider == 'deepgram' else local_key(provider)
        from loguru import logger
        logger.remove()
        logging.getLogger().setLevel(logging.CRITICAL)
        logs = ROOT / 'scripts/vendor' / provider / 'logs'
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / f'{plan["batch_id"]}-{args.authorization_decision}.log').open('x') as output:
            output.write(json.dumps({'batch_id': plan['batch_id'], 'sha256': plan['request_sha256'],
                                     'status': 'claimed_no_automatic_replay'}) + '\n')
            output.flush()
            for row in plan['cases']:
                result = asyncio.run(run_case(row, key))
                output.write(json.dumps(result) + '\n')
                output.flush()
                if result['status'] != 'ok':
                    return 1
        return 0
    except (ValueError, OSError, subprocess.SubprocessError):
        LOGGER.error('Stopped: authorization/data/local configuration not ready')
        return 2


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
