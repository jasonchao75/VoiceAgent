"""Expose the existing offline fixture only through a loopback-published container port."""
from pathlib import Path

import socket
import json
import asyncio
import time
import resource
import weakref
from contextlib import asynccontextmanager
import td_local_app

import uvicorn

from td_local_app import create_local_app

coordinators = weakref.WeakSet()
original_prepare = td_local_app.prepare_local_td
async def observed_prepare(**kwargs):
    result = await original_prepare(**kwargs)
    coordinators.add(result[1])
    return result
td_local_app.prepare_local_td = observed_prepare

app = create_local_app(Path('/tmp/td-resource-r93'), 'http://127.0.0.1:18993', 'ordinary')
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
    probe.settimeout(1)
    try:
        probe.connect(('203.0.113.1', 443))
    except RuntimeError:
        print(json.dumps({'outbound_guard': 'non-loopback rejected before connect'}), flush=True)
    else:
        raise RuntimeError('Offline fixture outbound guard absent')
async def sample_resources():
    previous = time.monotonic()
    with Path('/tmp/resource-samples.jsonl').open('w') as output:
        while True:
            await asyncio.sleep(.1)
            now = time.monotonic()
            output.write(json.dumps({
                'monotonic': now, 'loop_delay_ms': max(0, (now-previous-.1)*1000),
                'rss_max_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'live_coordinators': len(coordinators),
                'sampled_audio_pending': max((td._audio_pending for td in coordinators), default=0),
                'sampled_audio_processing': max((td._audio_processing for td in coordinators), default=0),
            })+'\n')
            output.flush()
            previous = now

original_lifespan = app.router.lifespan_context
@asynccontextmanager
async def measured_lifespan(instance):
    async with original_lifespan(instance) as state:
        sampler = asyncio.create_task(sample_resources())
        try:
            yield state
        finally:
            sampler.cancel()
            await asyncio.gather(sampler, return_exceptions=True)
app.router.lifespan_context = measured_lifespan

uvicorn.run(app, host='0.0.0.0', port=8000, access_log=False)
