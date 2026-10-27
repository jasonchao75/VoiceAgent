"""Bounded local codec/RTP identity gate; never a browser playback proof."""
import asyncio
import json
import logging
from pathlib import Path

import numpy as np
from aiortc import RTCRtpSender
from aiortc.rtp import RtpPacket
from aiortc.rtcrtpparameters import RTCRtpCodecParameters
from pipecat.transports.smallwebrtc.transport import RawAudioTrack, SmallWebRTCClient

from src.pipeline.audio_identity import audio_frame_type

OUTPUT = Path('openspec/changes/add-jev-semantic-turn-detection/verification/development-20261022-r39')


async def main():
    """Capture only serialized packets and sender-side task oracle, with no sockets."""
    trace = []
    packets = []
    enough = asyncio.Event()

    class Track(RawAudioTrack):
        """Observe native input sample positions without changing its queue or encoder."""
        async def recv(self):
            frame = await super().recv()
            source = 'partial-A' if frame.pts < 720 else 'final-B' if frame.pts < 1440 else None
            trace.append({'source_pts_24k': frame.pts, 'oracle_task': source})
            return frame

    class Transport:
        """Replace only network transmission; use native encoding and RTP serialization."""
        state = 'connected'

        async def _send_rtp(self, data):
            packet = RtpPacket.parse(data)
            packets.append({'timestamp': packet.timestamp,
                            'sequence': packet.sequence_number,
                            'payload_bytes': len(packet.payload),
                            'trigger_source_pts_24k': trace[-1]['source_pts_24k'],
                            'trigger_oracle_task': trace[-1]['oracle_task']})
            if len(packets) >= 5:
                enough.set()

    track = Track(24000)
    client = SmallWebRTCClient.__new__(SmallWebRTCClient)
    client._audio_output_track = track
    client._can_send = lambda: True
    tasks = []
    for identity, value in [('partial-A', 1000), ('final-B', -1000)]:
        cls = audio_frame_type(playback_id=identity, kind='normal', response_id=identity)
        tasks.append(asyncio.create_task(client.write_audio_frame(
            cls(np.full(720, value, dtype=np.int16).tobytes(), 24000, 1))))
    await asyncio.sleep(0)
    sender = RTCRtpSender(track, Transport())
    codec = RTCRtpCodecParameters(mimeType='audio/opus', clockRate=48000,
                                  channels=2, payloadType=111)
    sending = asyncio.create_task(sender._run_rtp(codec))
    try:
        await asyncio.wait_for(enough.wait(), 3)
    finally:
        sending.cancel()
        await asyncio.gather(sending, *tasks, return_exceptions=True)
        track.stop()
    origin = packets[0]['timestamp']
    for packet in packets:
        start = (packet['timestamp'] - origin) % 2**32
        end = start + 960
        owners = []
        for low, high, owner in [(0, 1440, 'partial-A'), (1440, 2880, 'final-B')]:
            overlap = min(high, end) - max(low, start)
            if overlap > 0:
                owners.append({'task': owner, 'nominal_input_overlap_48k': overlap})
        packet.update(relative_rtp_48k=start, nominal_input_spans=owners)
    result = {'level': 'local-real SDK/codec/serialized RTP, no network/browser playback',
              'native_queue_has_task_identity': False,
              'input_tasks': [{'id': 'partial-A', 'samples_24k': 720},
                              {'id': 'final-B', 'samples_24k': 720}],
              'source_trace': trace, 'packets': packets,
              'critical_limit': 'Native path discards identity; encoder buffers across tasks. '
                                'One task per emitted packet / last input trigger is unproven. '
                                'Nominal overlaps are oracle input coordinates, NOT decoded '
                                'sample ownership: codec delay/resampling remain unresolved.',
              'gate': 'NO_GO_TASK_MAPPING_NOT_PROVEN',
              'later_cases': {'Final_cancel_with_task_receipt': 'NOT_RUN',
                              'identifier_arbitration': 'NOT_RUN',
                              'browser_latency_and_compatibility': 'NOT_RUN'}}
    (OUTPUT / 'rtp-task-map.json').write_text(json.dumps(result, indent=2) + '\n')
    logging.info('Gate=%s packets=%s; stop before browser/combination/adoption',
                 result['gate'], len(packets))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
