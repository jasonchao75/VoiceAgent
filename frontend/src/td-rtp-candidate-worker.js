import {RTPPacketDecoder} from './td-rtp-decode-job.js';
/* Modern and legacy RTP transforms share strict packet identity and one decoder. */
const mappings = new Map(), packets = new Map();
const packetOrder = [];
let failed = false, decoder, draining = false, nextSource = null;
const counts={packets:0,mappings:0,decoded:0};
const emit = data => self.postMessage(data);
function fail(reason,details) {
  if (failed) return;
  failed = true;
  emit({event:'mapping_failed',reason,details,counts:{...counts}});
  if (decoder && decoder.state !== 'closed') decoder.close();
}
function key(ssrc, timestamp) { return `${ssrc}:${timestamp}`; }
async function deliver(id) {
  if (draining || failed) return;
  draining = true;
  try {
    while (packetOrder.length && !failed) {
      id = packetOrder[0];
      if (!mappings.has(id)) break;
      await decodePacket(id);
      packetOrder.shift();
    }
  } finally { draining = false; }
}
async function decodePacket(id) {
  const map = mappings.get(id), packet = packets.get(id);
  mappings.delete(id); packets.delete(id);
  const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256',packet.data))]
    .map(value=>value.toString(16).padStart(2,'0')).join('');
  if (hash !== map.payload_sha256) return fail('payload_identity_mismatch');
  if ((nextSource === null && map.source_start > 0) || (nextSource !== null && map.source_start !== nextSource)) return fail('decode_sequence_gap');
  nextSource = map.source_start + map.samples;
  const timestamp = 1000000 + Math.round(map.source_start * 1000000 / 48000);
  const bindingWait=performance.now()-packet.receivedAt;
  const decodeStarted=performance.now();
  const timer=setTimeout(()=>fail('decode_deadline'),1000);
  try {
    const output=await decoder.decodePacket(packet.data,map.samples,timestamp);
    if(failed) return;
    emit({event:'packet_bound',rtp_timestamp:map.rtp_timestamp,ssrc:map.ssrc,
      payload_sha256:hash,source_start:map.source_start,spans:map.spans,
      mapping_wait_ms:bindingWait,decode_job_ms:performance.now()-decodeStarted,
      input_timestamp:timestamp,output_timestamp:output.timestamp,binding:'single_packet_flush'});
    for(const span of map.spans) {
      if(span.task===null) continue;
      const offset=span.start-map.source_start,length=span.end-span.start;
      if(offset<0 || length<=0 || offset+length>output.values.length) return fail('invalid_decode_slice');
      const pcm=new Int16Array(length);
      for(let n=0;n<length;n++) pcm[n]=Math.max(-32768,Math.min(32767,Math.round(output.values[offset+n]*32768)));
      emit({event:'task_pcm',task:span.task,start:span.start,end:span.end,
        decode_timestamp:output.timestamp,rtp_timestamp:map.rtp_timestamp,buffer:pcm});
    }
    counts.decoded++;
    emit({event:'decoded',source_start:map.source_start,samples:output.samples,
      sample_rate:output.sample_rate,decode_timestamp:output.timestamp,binding:'single_packet_flush'});
  } catch { fail('decode_job_unproven'); }
  finally { clearTimeout(timer); }
}
self.onmessage = async ({data}) => {
  if (data.event === 'legacy_transform') { attachEncodedStream(data);return; }
  if (data.event === 'mapping') {
    counts.mappings++;
    const map = data.mapping;
    if (map?.version !== 1 || !Number.isInteger(map.rtp_timestamp) || !Number.isInteger(map.ssrc)) return fail('invalid_mapping');
    const id = key(map.ssrc,map.rtp_timestamp);
    if (mappings.has(id)) return fail('duplicate_mapping');
    if (mappings.size >= 100) return fail('mapping_queue_limit');
    mappings.set(id,map);
    setTimeout(()=>{if(mappings.has(id)) fail('packet_deadline');},1000);
    await deliver(id);
  }
};
function attachEncodedStream(transformer) {
  if (decoder) return fail('multiple_receiver_transform');
  try {
    decoder = new RTPPacketDecoder({Decoder:AudioDecoder,Chunk:EncodedAudioChunk,onFailure:reason=>fail(reason)});
    transformer.readable.pipeThrough(new TransformStream({
      async transform(frame, controller) {
        if (failed) return;
        counts.packets++;
        const metadata = frame.getMetadata();
        if (!Number.isInteger(metadata.synchronizationSource)) return fail('missing_ssrc');
        const id = key(metadata.synchronizationSource,frame.timestamp);
        if (packets.has(id) || packets.size >= 100) return fail('packet_queue_limit');
        packets.set(id,{data:frame.data.slice(0),receivedAt:performance.now()});
        packetOrder.push(id);
        setTimeout(()=>{if(packets.has(id)) fail('mapping_deadline');},1000);
        await deliver(id);
        // The native receiver stays pulling through a muted sink, never double plays.
        controller.enqueue(frame);
      },
    })).pipeTo(transformer.writable).catch(()=>fail('transform_stream_error'));
    emit({event:'decoder_configured'});
  } catch { fail('decoder_unavailable'); }
}
self.onrtctransform = ({transformer}) => attachEncodedStream(transformer);
