"""Probe three explicitly authorized fixed Flux TTS texts through the production unit path."""

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
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluation.probe_td_compatibility import (  # noqa: E402
    ConnectionBudget,
    local_key,
    verify_authorization,
)

LOGGER = logging.getLogger(__name__)


def build_plan(*, single_unit: bool = False) -> dict[str, Any]:
    """Return the complete fixed text/voice/character-price scope without any credential."""
    texts = ['one', 'two', 'Your number has been cleared.']
    if single_unit:
        texts = texts[:1]
    characters = sum(map(len, texts))
    plan = {'batch_id': 'deepgram-td-tts-synthetic-v1', 'max_calls': 3,
            'recipient': 'api.deepgram.com', 'endpoint': 'wss://api.deepgram.com/v2/speak',
            'voice': 'flux-alexis-en', 'speed': 1.0, 'expressivity': 0,
            'sample_rate': 24000, 'channels': 1, 'format': 'PCM16',
            'cases': [{'id': str(index + 1), 'text': text} for index, text in enumerate(texts)],
            'characters': characters, 'cost_ceiling_usd': '0.10',
            'usd_per_1000_characters': '0.045',
            'estimated_cost_usd': str(Decimal(characters) * Decimal('0.045') / 1000),
            'timeout_seconds': 15, 'retries': 0, 'asr_jev_llm_calls': 0,
            'pricing_source': 'https://deepgram.com/pricing', 'price_verified': '2026-10-22'}
    if single_unit:
        plan.update(batch_id='deepgram-td-tts-one-confirmation-v1', max_calls=1,
                    cost_ceiling_usd='0.02')
    plan['request_sha256'] = hashlib.sha256(json.dumps(
        plan, sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    return plan



class SpeakScopeViolation(RuntimeError):
    """Keep a fixed rejection reason without disclosing changed text or provider details."""

    def __init__(self, reason: Literal[
        'text_scope_mismatch', 'speak_budget_exhausted', 'protocol_scope_mismatch',
    ]) -> None:
        """Expose only an enumerated guard stage, never the attempted text."""
        super().__init__(reason)
        self.reason = reason

def speak_guard(original: Any, text: str) -> Any:
    """Allow one exact Speak before transport invocation; never refund a failed attempt."""
    claimed = False

    async def send(message: dict[str, Any]) -> Any:
        """Bound chargeable text independently of connection and protocol control frames."""
        nonlocal claimed
        if message.get('type') == 'Speak':
            if message.get('text') != text:
                raise SpeakScopeViolation('text_scope_mismatch')
            if claimed:
                raise SpeakScopeViolation('speak_budget_exhausted')
            claimed = True
        elif message.get('type') not in {'Configure', 'Flush', 'Interrupt'}:
            raise SpeakScopeViolation('protocol_scope_mismatch')
        return await original(message)

    return send


async def run_case(row: dict[str, Any], key: str, output: Path, *, timeout: float = 15) -> Any:
    """Use the actual SDK registry/unit synthesis; save only validated returned PCM.

    Args:
        row: One immutable authorized text record.
        key: Already authorized local credential, never logged or returned.
        output: Exclusive batch-owned directory for non-customer audio evidence.
        timeout: Production unit synthesis lifecycle deadline in seconds.

    Returns:
        A whitelisted result record; failures stop the caller's entire batch.
    """
    from src.asr.factory import _configure_provider_tls
    from src.config import TTSConfig
    from src.tts.factory import create_default_tts_registry
    from src.tts.unit_synthesis import synthesize_unit

    _configure_provider_tls()
    registry: Any = create_default_tts_registry()
    create = registry.create
    budget = ConnectionBudget()
    protocol: dict[str, Any] = {'outgoing': [], 'incoming': [], 'audio_bytes': 0}

    def guarded_create(**kwargs: Any) -> Any:
        """Wrap only the exact actual provider's socket and chargeable text entry points."""
        processor = create(**kwargs)
        connect = budget.async_connector(processor._websocket_connect)
        send = speak_guard(processor._transport_send_json, row['text'])
        receive = processor._handle_message
        receive_audio = processor._handle_audio

        async def observed_connect(*args: Any, **kwargs: Any) -> Any:
            """Retain an HTTP status/category only, never URLs, headers or exception text."""
            try:
                connection = await connect(*args, **kwargs)
                protocol['connection_opened'] = True
                return connection
            except Exception as exc:
                kind = type(exc).__name__
                safe: dict[str, Any] = {'type': kind if kind in {
                    'InvalidStatus', 'TimeoutError', 'SSLCertVerificationError',
                    'ConnectionRefusedError', 'ConnectionResetError', 'RuntimeError',
                } else 'OtherError'}
                status = getattr(getattr(exc, 'response', None), 'status_code', None)
                if type(status) is int and 100 <= status <= 599:
                    safe['http_status'] = status
                protocol.setdefault('connection_failure', safe)
                protocol.setdefault('failure_stage', 'connection')
                raise

        async def observed_send(message: dict[str, Any]) -> Any:
            """Enforce exact Speak scope before recording a bounded protocol kind."""
            if message.get('type') == 'Speak':
                protocol['speak_attempts'] = protocol.get('speak_attempts', 0) + 1
            try:
                result = await send(message)
            except SpeakScopeViolation as exc:
                protocol['scope_rejection'] = exc.reason
                protocol.setdefault('failure_stage', 'request_guard')
                raise
            except Exception:
                protocol.setdefault('failure_stage', 'transport_send')
                raise
            if message.get('type') == 'Speak':
                protocol['completed_speak_sends'] = protocol.get('completed_speak_sends', 0) + 1
            if len(protocol['outgoing']) < 32:
                protocol['outgoing'].append(message['type'])
            return result

        async def observed_receive(message: dict[str, Any]) -> None:
            """Persist only known control kinds and numeric usage, not provider payloads."""
            kind = message.get('type')
            if kind in {'Connected', 'SpeechStarted', 'Flushed', 'SpeechMetadata',
                        'SpeechInterrupted', 'ConfigureSuccess', 'ConfigureFailure',
                        'SessionMetadata', 'Warning', 'Error'}:
                if len(protocol['incoming']) < 32:
                    protocol['incoming'].append(kind)
                if kind == 'SpeechMetadata':
                    value = message.get('billable_character_count')
                    if type(value) is int and 0 <= value <= 10000:
                        protocol['billable_characters'] = value
            if kind in {'Error', 'ConfigureFailure'}:
                protocol.setdefault('failure_stage', 'provider_control_error')
            await receive(message)

        async def observed_audio(audio: bytes) -> None:
            """Count audio without duplicating its contents or inferring playback."""
            protocol['audio_bytes'] += len(audio)
            await receive_audio(audio)

        processor._websocket_connect = observed_connect
        processor._transport_send_json = observed_send
        processor._handle_message = observed_receive
        processor._handle_audio = observed_audio
        return processor

    registry.create = guarded_create
    config = TTSConfig(voice='flux-alexis-en', provider='deepgram_flux', speed=1.0,
                       expressivity=0, text_aggregation='sentence', dynamic_speed_enabled=False)
    started = time.monotonic()
    result: dict[str, Any] = {'case': row['id'], 'text': row['text'], 'status': 'ok'}
    try:
        pcm = await synthesize_unit(registry, key, row['text'], config, 24000, timeout=timeout)
        path = output / f'case-{row["id"]}.wav'
        with wave.open(str(path), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(24000)
            stream.writeframes(pcm)
        result.update(samples=len(pcm) // 2, sample_rate=24000, channels=1,
                      duration_seconds=len(pcm) / 48000,
                      wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      audio_path=str(path.relative_to(ROOT)))
    except TimeoutError:
        result['status'] = 'timeout'
        protocol.setdefault('failure_stage', 'deadline')
    except Exception:
        result['status'] = 'synthesis_or_format_error'
        protocol.setdefault('failure_stage', 'unit_pipeline_or_artifact')
    result.update(connections=budget.attempts, elapsed_ms=(time.monotonic() - started) * 1000,
                  protocol=protocol)
    return result


def main(argv: list[str] | None = None) -> int:
    """Never load a credential or synthesize without this batch's exact human grant."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--single-unit-confirmation', action='store_true')
    parser.add_argument('--authorization-decision', default='')
    args = parser.parse_args(argv)
    plan = build_plan(single_unit=args.single_unit_confirmation)
    if not args.execute:
        LOGGER.info('Dry TTS plan: calls=%s characters=%s ceiling=USD%s sha256=%s',
                    plan['max_calls'], plan['characters'], plan['cost_ceiling_usd'],
                    plan['request_sha256'])
        return 0
    try:
        verify_authorization(plan, args.authorization_decision)
        key = local_key()
        from loguru import logger
        logger.remove()
        logging.getLogger().setLevel(logging.CRITICAL)
        logs = ROOT / 'scripts/vendor/deepgram/logs'
        logs.mkdir(exist_ok=True)
        name = f'{plan["batch_id"]}-{args.authorization_decision}'
        with (logs / f'{name}.log').open('x') as stream:
            stream.write(json.dumps({'batch_id': plan['batch_id'],
                                     'sha256': plan['request_sha256'],
                                     'status': 'claimed_no_automatic_replay'}) + '\n')
            stream.flush()
            audio_dir = logs / name
            audio_dir.mkdir()
            for row in plan['cases']:
                result = asyncio.run(run_case(row, key, audio_dir))
                stream.write(json.dumps(result) + '\n')
                stream.flush()
                if result['status'] != 'ok':
                    return 1
        return 0
    except (ValueError, OSError, subprocess.SubprocessError):
        LOGGER.error('Stopped: TTS authorization/local configuration not ready')
        return 2


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
