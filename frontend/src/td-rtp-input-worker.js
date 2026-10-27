import {RTPInputTap} from './td-rtp-input-tap.js';
/* Both supported RTP transform APIs use the same read-only sender evidence tap. */
const tap=new RTPInputTap({clockId:crypto.randomUUID().replaceAll('-',''),
  emit:message=>self.postMessage(message)});
let started=false;
self.onmessage=({data})=>{
  if(data?.event==='legacy_transform') {attachEncodedStream(data);return;}
  if(data?.event==='input_capture_observed') tap.acknowledge(data.id);
  if(data?.event==='capture_install_failed') tap.unavailable('capture_transform_unavailable');
  if(data?.event==='clock_sample' && /^[a-f0-9]{32}$/.test(data.sample_id)) {
    self.postMessage({event:'clock_sample',sample_id:data.sample_id,
      render_frame:Math.floor(performance.now()*16),render_sample_rate:16000});
  }
};
function attachEncodedStream(transformer) {
  if(started) {tap.unavailable('multiple_capture_transform');return;}
  started=true;
  transformer.readable.pipeThrough(new TransformStream({
    transform(frame,controller) {tap.observe(frame);controller.enqueue(frame);},
  })).pipeTo(transformer.writable).catch(()=>tap.unavailable('capture_transform_closed'));
}
self.onrtctransform=({transformer})=>attachEncodedStream(transformer);
