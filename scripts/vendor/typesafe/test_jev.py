"""Prepare or execute one explicitly authorized, bounded synthetic Jev smoke batch."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.asr.td_config import JevSettings  # noqa: E402
from src.pipeline.jev import JevClient  # noqa: E402

CHANGE = ROOT / 'openspec/changes/add-jev-semantic-turn-detection'
BATCH_ID = 'jev-synthetic-smoke-v1'
ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
LOGGER = logging.getLogger(__name__)


def build_plan() -> dict[str, Any]:
    """Return the exact synthetic payloads and public-price safety bounds, without a key."""
    settings = JevSettings.model_validate({
        'endpoint': ENDPOINT, 'model': 'jev-latest', 'timeout_seconds': 3,
        'noul_instructions': 'Has the user finished their utterance and yielded the turn?',
        'choice_instructions': 'Classify the current user utterance.',
        'options': [
            {'id': 'complete', 'meaning': 'The request is complete.', 'wait_ms': 600},
            {'id': 'incomplete', 'meaning': 'The user is still forming a request.',
             'wait_ms': 1500},
        ],
    })
    cases = [('Please check my booking.', 'Final'), ('I would like to...', 'Partial')]
    requests = [{
        'model': settings.model,
        'state': {'assistant': 'How can I help you?', 'user': text, 'transcript_status': status},
        'questions': settings.questions(),
    } for text, status in cases]
    digest = hashlib.sha256(json.dumps(
        {'endpoint': ENDPOINT, 'requests': requests}, sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    return {'batch_id': BATCH_ID, 'endpoint': ENDPOINT, 'requests': requests,
            'request_sha256': digest, 'max_calls': 2, 'timeout_seconds': 3,
            'cost_ceiling_usd': '0.01', 'input_usd_per_million': '0.042',
            'default_context_tokens_per_request': 64000,
            'pricing_source': 'https://docs.typesafe.ai/models'}


def verify_authorization(manifest: Path, decisions: Path, decision_id: str) -> dict[str, Any]:
    """Reject absent, mismatched or unconfirmed batch authorization before credential loading.

    Args:
        manifest: Change delivery manifest containing a human-authorized batch record.
        decisions: Decision log with the matching confirmation and source.
        decision_id: Exact decision identifier, never inferred from Gate 1.

    Returns:
        The matching bounded grant.

    Raises:
        ValueError: If the scope, digest, budget or confirmation does not match.
    """
    plan = build_plan()
    if not re.fullmatch(r'D-\d+', decision_id):
        raise ValueError('An explicit batch decision is required')
    records = json.loads(manifest.read_text()).get('external_calls', [])
    grant = next((row for row in records if row.get('batch_id') == BATCH_ID
                  and row.get('authorization_decision_id') == decision_id), None)
    if not grant or any(grant.get(field) != plan[field] for field in (
        'request_sha256', 'max_calls', 'cost_ceiling_usd',
    )) or grant.get('authorization_status') != 'confirmed':
        raise ValueError('Matching batch authorization is absent')
    block = re.search(rf'(?ms)^### {re.escape(decision_id)}\b[^\n]*\n(.*?)(?=^### |\Z)',
                      decisions.read_text())
    if not block or '- Status: Confirmed' not in block[1] or not all(
        re.search(rf'(?m)^- {label}:[ \t]*\S[^\n]*$', block[1])
        for label in ('Confirmation quote', 'Source thread/message')
    ):
        raise ValueError('Human confirmation source is absent')
    return grant


async def run_batch(
    api_key: str, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 3,
) -> list[dict[str, Any]]:
    """Run only the reviewed payloads through the production client, stopping on any error.

    Args:
        api_key: Already authorized local credential, never included in returned data.
        transport: Injected MockTransport for offline tests; None uses verified HTTPS.
        timeout: Explicit per-call/whole-operation timeout in seconds.

    Returns:
        At most two whitelisted result records; no raw provider body or headers.
    """
    plan = build_plan()
    metadata: dict[str, Any] = {}

    async def response_metadata(response: httpx.Response) -> None:
        """Extract only bounded model/token fields; do not retain arbitrary provider errors."""
        metadata.clear()
        if response.status_code != 200:
            return
        await response.aread()
        try:
            body = response.json()
            usage = body['usage']
            if body.get('model') not in {'jev-latest', 'jev-1.13.0', 'jev-1.14.0'}:
                return
            if any(type(usage[key]) is not int or not 0 <= usage[key] <= 64000
                   for key in ('input_tokens', 'output_tokens')):
                return
            metadata.update(model=body['model'], input_tokens=usage['input_tokens'],
                            output_tokens=usage['output_tokens'])
        except (ValueError, KeyError, TypeError, AttributeError):
            return

    results = []
    async with httpx.AsyncClient(transport=transport, timeout=timeout, trust_env=False,
                                follow_redirects=False,
                                event_hooks={'response': [response_metadata]}) as client:
        service = JevClient(endpoint=ENDPOINT, api_key=api_key, client=client, max_calls=2)
        for index, payload in enumerate(plan['requests']):
            metadata.clear()
            started = time.monotonic()
            result = await service.decide(**payload, noul_id='yield',
                                          choice_id='speech_state', timeout=timeout)
            status = result.status
            if status == 'ok' and not metadata:
                status = 'invalid_usage_or_model'
            record = {'case': index + 1, 'status': status,
                      'duration_ms': round((time.monotonic() - started) * 1000, 3), **metadata}
            if status == 'ok':
                record.update(noul=result.noul, probabilities=result.probabilities,
                              estimated_cost_usd=str(Decimal(metadata['input_tokens'])
                                                     * Decimal('0.042') / 1_000_000))
            results.append(record)
            if status != 'ok':
                break
    return results


def local_key() -> str:
    """Load the local key only after authorization, refusing a tracked/unignored env file."""
    key = os.environ.get('TYPESAFE_API_KEY', '')
    if not key:
        subprocess.run(['git', 'check-ignore', '-q', '.env'], cwd=ROOT, check=True,
                       capture_output=True)
        from dotenv import dotenv_values

        key = dotenv_values(ROOT / '.env').get('TYPESAFE_API_KEY') or ''
    if not key.strip():
        raise ValueError('A local TypeSafe credential is required')
    return key.strip()


def main(argv: list[str] | None = None) -> int:
    """Default to a no-key/no-network plan; execute only one explicitly granted batch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization-decision', default='')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    plan = build_plan()
    if not args.execute:
        LOGGER.info('Dry run only: batch=%s calls=2 ceiling=USD0.01 sha256=%s',
                    BATCH_ID, plan['request_sha256'])
        return 0
    try:
        verify_authorization(CHANGE / 'verification/delivery-status.json',
                             CHANGE / 'decisions/decision-log.md', args.authorization_decision)
        key = local_key()
        logs = Path(__file__).parent / 'logs'
        logs.mkdir(exist_ok=True)
        # An exclusive claim prevents replay after a timeout or process crash.
        with (logs / f'{BATCH_ID}-{args.authorization_decision}.log').open('x') as stream:
            stream.write(json.dumps({'batch_id': BATCH_ID, 'request_sha256': plan['request_sha256'],
                                     'decision': args.authorization_decision,
                                     'status': 'claimed_no_automatic_replay'}) + '\n')
            stream.flush()
            results = asyncio.run(run_batch(key))
            stream.write(json.dumps({'results': results}) + '\n')
        LOGGER.info('Batch ended: calls=%s statuses=%s', len(results),
                    [row['status'] for row in results])
        return 0 if len(results) == 2 and all(row['status'] == 'ok' for row in results) else 1
    except (ValueError, OSError, subprocess.SubprocessError):
        LOGGER.error('Batch stopped before completion; check authorization/local configuration')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
