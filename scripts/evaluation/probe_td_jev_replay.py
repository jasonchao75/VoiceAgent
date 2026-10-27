"""Run an exact-scope real-Jev replay; never open a new ASR or media connection."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluation.probe_td_compatibility import verify_authorization  # noqa: E402
from scripts.vendor.typesafe.test_jev import local_key  # noqa: E402
from src.asr.td_config import CustomTDSettings  # noqa: E402
from src.pipeline.jev import JevClient, JevResult  # noqa: E402

CHANGE = ROOT / 'openspec/changes/archive/2026-10-27-add-jev-semantic-turn-detection'
SOURCE = CHANGE / 'verification/development-20261026-r91/deepgram-D081.jsonl'
BATCH = 'jev-d080-recorded-asr-replay-r92-v1'
LOGGER = logging.getLogger(__name__)


def settings() -> CustomTDSettings:
    """Return explicit probe inputs, without changing any Bot or production default."""
    return CustomTDSettings.model_validate({
        'minimum_ms': 600, 'maximum_ms': 2500, 'final_wait_ms': 200,
        'alpha': .5, 'conflict_threshold': .8,
        'vad': {'confidence': .7, 'start_secs': .2, 'stop_secs': .2, 'min_volume': .6},
        'jev': {'endpoint': 'https://api.typesafe.ai/v1/systemone', 'model': 'jev-1.14.0',
                'timeout_seconds': 3,
                'noul_instructions': 'Has the user finished their utterance and yielded the turn?',
                'choice_instructions': 'Classify the current user utterance.',
                'options': [
                    {'id': 'complete', 'meaning': 'The request is complete.', 'wait_ms': 700},
                    {'id': 'incomplete', 'meaning': 'The user is still forming a request.',
                     'wait_ms': 1500}]},
    })


def source_events() -> list[dict[str, Any]]:
    """Read two already captured synthetic ASR partials; no provider is contacted."""
    events = json.loads(SOURCE.read_text().splitlines()[-1])['events']
    selected = [events[4], events[14]]
    expected = ['please do not cancel my booking.',
                'please do not cancel my booking. I would like to']
    if [event['text'] for event in selected] != expected or any(
        event['missing_reason'] or not event['segments'] for event in selected
    ):
        raise ValueError('Pinned replay input changed')
    return selected


def build_plan() -> dict[str, Any]:
    """Freeze payloads and a worst-context price envelope before authorization."""
    config = settings()
    plan = {
        'batch_id': BATCH, 'endpoint': config.jev.endpoint, 'model': config.jev.model,
        'source_evidence': str(SOURCE.relative_to(ROOT)),
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'requests': [{'model': config.jev.model,
                      'state': {'assistant': 'How can I help you?', 'user': event['text'],
                                'transcript_status': 'Partial'},
                      'questions': config.jev.questions()} for event in source_events()],
        'max_calls': 2, 'timeout_seconds': 3, 'cost_ceiling_usd': '0.01',
        'maximum_public_price_usd': '0.005376', 'default_context_tokens_per_request': 64000,
        'input_usd_per_million': '0.042', 'pricing_source': 'https://docs.typesafe.ai/models',
        'price_verified': '2026-10-26', 'asr_calls': 0, 'llm_tts_calls': 0,
        'retries': 0, 'long_context': False,
        'clock_scope': 'controlled audio clock; not live ASR arrival or measured media latency',
        'stop': 'first error, unexpected payload, missing usage/model/range, or budget violation',
        'acceptance': 'record actual fused targets; D080 only triggered if second target exceeds '
                      'old Final deadline; no resampling or repeat until triggered',
    }
    plan['request_sha256'] = hashlib.sha256(json.dumps(
        plan, sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    return plan


async def run_replay(
    api_key: str, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 3,
) -> dict[str, Any]:
    """Exercise production coordinator/normalizer with bounded real or mocked HTTP.

    Args:
        api_key: Authorized local credential, never returned.
        transport: Explicit offline HTTP replacement for safety and scenario checks.
        timeout: Whole HTTP operation deadline for each of the two requests.

    Returns:
        Whitelisted decisions and controlled-clock submission facts, not media facts.
    """
    from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame

    from src.asr.factory import ASRService
    from src.asr.turn_events import SourceNormalizer
    from src.pipeline.custom_td import CustomTDCoordinator

    plan, config = build_plan(), settings()
    events, outputs, decisions, usage = [], [], [], {}
    attempts = 0
    stopped = None

    async def metadata(response: httpx.Response) -> None:
        """Allow only expected model and bounded token counts into billing evidence."""
        usage.clear()
        if response.status_code != 200:
            return
        await response.aread()
        try:
            payload = response.json()
            if payload.get('model') != config.jev.model:
                return
            counts = payload['usage']
            if all(type(counts[k]) is int and 0 <= counts[k] <= 64000
                   for k in ('input_tokens', 'output_tokens')):
                usage.update(model=payload['model'], input_tokens=counts['input_tokens'],
                             output_tokens=counts['output_tokens'])
        except (ValueError, KeyError, TypeError):
            return

    async with httpx.AsyncClient(transport=transport, timeout=timeout, trust_env=False,
                                 follow_redirects=False,
                                 event_hooks={'response': [metadata]}) as client:
        service = JevClient(
            endpoint=config.jev.endpoint, api_key=api_key, client=client, max_calls=2)

        async def decide(**kwargs: Any) -> JevResult:
            """Reject anything outside the frozen payload before opening a paid request."""
            nonlocal attempts, stopped
            payload = {key: kwargs[key] for key in ('model', 'state', 'questions')}
            if stopped or attempts >= 2 or payload != plan['requests'][attempts]:
                stopped = stopped or 'unexpected_payload_or_budget'
                return JevResult(stopped)
            attempts += 1
            result = await service.decide(**kwargs)
            if result.status != 'ok':
                stopped = result.status
            elif transport is None and not usage:
                stopped = 'invalid_usage_or_model'
                result = JevResult(stopped)
            decisions.append({'attempt': attempts, 'status': result.status, 'noul': result.noul,
                              'probabilities': result.probabilities, **usage})
            return result

        td = CustomTDCoordinator(
            asr=ASRService(processor=None, source_normalizer=SourceNormalizer(
                'deepgram', 'flux-general-en')), settings=config, decide=decide,
            evidence_sink=events.append,
        )

        async def push(frame: Any, *args: Any, **kwargs: Any) -> None:
            """Observe submission without invoking LLM, tools, TTS or playback."""
            outputs.append(frame)

        td.push_frame = push
        td.assistant_context('How can I help you?')
        frames = [InterimTranscriptionFrame(event['text'], '', '', result={
            **event['source_evidence'], 'transcript': event['text'],
        }) for event in source_events()]
        old_commits = maximum_commits = 0
        first_target = second_target = None
        try:
            await td.speech_started()
            await td.receive_transcript(frames[0])
            await td.speech_stopped(6000)
            await asyncio.wait_for(td._decision, timeout=timeout + 1)
            if not stopped:
                first_target = td.clock._target_ms
                if first_target is None:
                    raise ValueError('Missing first target')
                await td.advance(6000 + first_target)
                old_deadline = td.clock._final_deadline
                if old_deadline is None:
                    stopped = 'scenario_not_triggered:first_target_maximum'
                    maximum_commits = sum(
                        isinstance(frame, TranscriptionFrame) for frame in outputs)
                else:
                    await td.receive_transcript(frames[1])
                    await asyncio.wait_for(td._decision, timeout=timeout + 1)
                    if not stopped:
                        second_target = td.clock._target_ms
                        if old_deadline is not None:
                            await td.advance(old_deadline)
                        old_commits = sum(
                            isinstance(frame, TranscriptionFrame) for frame in outputs)
                        await td.advance(8500)
                        maximum_commits = sum(
                            isinstance(frame, TranscriptionFrame) for frame in outputs)
        finally:
            await td.cleanup()
    return {'status': f'stopped:{stopped}' if stopped else 'ok', 'calls': attempts,
            'decisions': decisions, 'first_target_ms': first_target,
            'second_target_ms': second_target,
            'd080_longer_wait_observed': first_target is not None and second_target is not None
            and second_target > first_target + config.final_wait_ms,
            'old_deadline_commits': old_commits, 'maximum_deadline_commits': maximum_commits,
            'events': events, 'scope': plan['clock_scope'],
            'asr_llm_tts_media_calls': 0}


def main(argv: list[str] | None = None) -> int:
    """Default to dry-run; atomically exclusive result creation prevents grant replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization-decision', default='')
    args = parser.parse_args(argv)
    try:
        plan = build_plan()
        if not args.execute:
            LOGGER.info('Dry plan sha256=%s', plan['request_sha256'])
            return 0
        verify_authorization(plan, args.authorization_decision)
        result_path = ROOT / 'scripts/vendor/typesafe/logs' / (
            BATCH + '-' + args.authorization_decision + '.log')
        result_path.parent.mkdir(parents=True, exist_ok=True)
        with result_path.open('x') as output:
            manifest = CHANGE / 'verification/delivery-status.json'
            data = json.loads(manifest.read_text())
            grant = next(row for row in data['external_calls'] if row['batch_id'] == BATCH)
            grant['execution_status'] = 'started_no_replay'
            manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
            output.write(json.dumps({'status': 'claimed_no_replay',
                                     'request_sha256': plan['request_sha256']}) + '\n')
            output.flush()
            result = asyncio.run(run_replay(local_key()))
            output.write(json.dumps(result) + '\n')
            return 0 if result['status'] == 'ok' else 1
    except (ValueError, OSError):
        LOGGER.error('Stopped before authorized execution or fixed replay validation')
        return 2


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
