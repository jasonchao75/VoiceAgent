"""D-060 isolated source/codec/RTP/decode coordinates; never playback receipts."""

import asyncio
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
from aiortc import RTCRtpSender
from aiortc.codecs.opus import OpusDecoder, OpusEncoder
from aiortc.jitterbuffer import JitterFrame
from aiortc.rtp import RtpPacket
from aiortc.rtcrtpparameters import RTCRtpCodecParameters
from pipecat.transports.smallwebrtc.transport import RawAudioTrack, SmallWebRTCClient

from src.pipeline.audio_identity import audio_frame_type, decode_audio_identity


async def main():
    """Instrument one native encoder without changing PCM, codec settings or production."""
    sources, resampled, encoded, received = [], [], [], []
    complete = asyncio.Event()
    decoder = OpusDecoder()

    class Encoder(OpusEncoder):
        """Keep native resampling/encoding, retaining PTS before aiortc rebases it."""

        def encode(self, frame, force_keyframe=False):
            packets = []
            for output in self.resampler.resample(frame):
                resampled.append({'pts': output.pts, 'samples': output.samples,
                                  'rate': output.sample_rate})
                packets.extend(self.codec.encode(output))
            if self.first_packet_pts is None and packets:
                self.first_packet_pts = packets[0].pts
            for packet in packets:
                encoded.append({'raw_pts': packet.pts, 'duration': packet.duration,
                                'sha256': hashlib.sha256(bytes(packet)).hexdigest()})
            return ([bytes(packet) for packet in packets],
                    packets[0].pts - self.first_packet_pts if packets else None)

    encoder = Encoder()

    class Client(SmallWebRTCClient):
        """Capture actual task names before the existing SDK removes them."""

        async def write_audio_frame(self, frame):
            identity = decode_audio_identity(frame.name)
            start = sum(row['samples_24k'] for row in sources)
            sources.append({'identity': identity, 'start_24k': start,
                            'samples_24k': len(frame.audio) // 2})
            return await super().write_audio_frame(frame)

    class Transport:
        """Serialize native RTP, then decode its exact payload with the native decoder."""

        state = 'connected'

        async def _send_rtp(self, data):
            packet = RtpPacket.parse(data)
            source_packet = encoded[len(received)]
            assert hashlib.sha256(packet.payload).hexdigest() == source_packet['sha256']
            origin = received[0]['rtp_timestamp'] if received else packet.timestamp
            relative = (packet.timestamp - origin) % 2**32
            # This offset is measured from actual encoder PTS, never a fixed 6.5ms guess.
            source_pts = relative + encoder.first_packet_pts
            frames = decoder.decode(JitterFrame(data=packet.payload, timestamp=source_pts))
            decoded = []
            for frame in frames:
                spans = []
                for source in sources:
                    start = max(frame.pts, source['start_24k'] * 2)
                    end = min(frame.pts + frame.samples,
                              (source['start_24k'] + source['samples_24k']) * 2)
                    if end > start:
                        spans.append({'task': source['identity']['playback_id'],
                                      'coordinate_start_48k': start,
                                      'coordinate_end_48k': end})
                decoded.append({'pts': frame.pts, 'samples': frame.samples,
                                'rate': frame.sample_rate, 'coordinate_spans': spans})
            received.append({'rtp_timestamp': packet.timestamp, 'relative_rtp': relative,
                             'source_pts': source_pts, 'encoder': source_packet,
                             'decoded': decoded})
            if len(received) == 5:
                complete.set()

    track = RawAudioTrack(24000)
    client = Client.__new__(Client)
    client._audio_output_track = track
    client._can_send = lambda: True
    writes = []
    for task, frequency in [('partial-A', 1000), ('final-B', 3000)]:
        cls = audio_frame_type(playback_id=task, kind='normal', response_id=task)
        pcm = (np.sin(np.arange(720) * 2 * np.pi * frequency / 24000) * 10000)
        writes.append(asyncio.create_task(client.write_audio_frame(
            cls(pcm.astype(np.int16).tobytes(), 24000, 1))))
    await asyncio.sleep(0)
    sender = RTCRtpSender(track, Transport())
    sender._RTCRtpSender__encoder = encoder
    codec = RTCRtpCodecParameters(mimeType='audio/opus', clockRate=48000,
                                  channels=2, payloadType=111)
    sending = asyncio.create_task(sender._run_rtp(codec))
    try:
        await asyncio.wait_for(complete.wait(), timeout=3)
    finally:
        sending.cancel()
        await asyncio.gather(sending, *writes, return_exceptions=True)
        track.stop()
    assert all(row['source_pts'] == row['encoder']['raw_pts'] for row in received)
    mixed = [frame for row in received for frame in row['decoded']
             if len(frame['coordinate_spans']) > 1]
    result = {'evidence_level': 'local-real native SDK/Opus/RTP serialization/native decode',
              'network_browser_hardware': False, 'sources': sources, 'resampled': resampled,
              'first_actual_encoder_pts': encoder.first_packet_pts, 'packets': received,
              'coordinate_bridge_proven': True, 'mixed_task_decoded_frames': len(mixed),
              'exclusive_decoded_sample_ownership_proven': False,
              'gate': 'STOP_RENDER_TASK_OWNERSHIP_NOT_PROVEN',
              'reason': 'PTS sidecar traces coordinates and shared packet spans, but does not '
                        'prove codec/resampler boundary sample attribution or browser render '
                        'identity. No fixed offset, packet-trigger task, or receipt was invented.',
              'later_cases': {'Final_cancel': 'NOT_RUN', 'identifier_arbitration': 'NOT_RUN',
                              'latency_mobile': 'NOT_RUN'},
              'production_changes': False}
    Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    logging.info('%s; coordinate bridge captured, full playback contract not proven', result['gate'])


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
