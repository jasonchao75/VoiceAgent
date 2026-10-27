import {test} from 'node:test';
import assert from 'node:assert/strict';
import {playbackReceipt} from '../../src/td-rtc-entry.js';
test('renderer-only state does not escape strict API receipt schema',()=>{
 const result=playbackReceipt({event:'task_stopped',playback_id:'a'.repeat(32),started:true,rendered_samples:128,elapsed_ms:10,render_clock_id:'b'.repeat(32),render_frame:200,render_sample_rate:48000});
 assert.equal('started' in result,false);
 assert.equal(result.rendered_samples,128);
 assert.equal(result.evidence_source,'audio_worklet_render');
});

test('receiver transform is installed with initial transceivers before SDP or track consumers',async()=>{
 const {bindRTCTransform}=await import('../../src/td-rtc-entry.js');
 const receiver={transform:null,track:{kind:"audio"}};
 const transport={pc:{getTransceivers:()=>[{receiver,sender:{track:{kind:'audio'}}}]},
   addInitialTransceivers(){this.created=true;}};
 const worker={};
 class Transform {constructor(value){this.worker=value;}}
 bindRTCTransform(transport,worker,Transform);
 transport.addInitialTransceivers();
 assert.equal(transport.created,true);
 assert.equal(receiver.transform.worker,worker);
});

test('capture metadata observation binds the sender without changing the receiver worker',()=>{
 const receiver={track:{kind:'audio'}},sender={};
 const transport={pc:{getTransceivers:()=>[{receiver,sender}]},addInitialTransceivers(){}};
 const renderWorker={},sourceWorker={};
 class Transform {constructor(worker){this.worker=worker;}}
 bindRTCTransformForTest(transport,renderWorker,Transform,sourceWorker);
 transport.addInitialTransceivers();
 assert.equal(receiver.transform.worker,renderWorker);
 assert.equal(sender.transform.worker,sourceWorker);
});
import {bindRTCTransform as bindRTCTransformForTest} from '../../src/td-rtc-entry.js';

test('optional sender timing capability cannot disable existing RTP playback',()=>{
 const receiver={track:{kind:'audio'}},sender={set transform(value){throw new Error('unsupported');}};
 const transport={pc:{getTransceivers:()=>[{receiver,sender}]},addInitialTransceivers(){}};
 const messages=[],inputWorker={postMessage:data=>messages.push(data)};
 class Transform {constructor(worker){this.worker=worker;}}
 assert.doesNotThrow(()=>{
  bindRTCTransformForTest(transport,{},Transform,inputWorker);transport.addInitialTransceivers();
 });
 assert.ok(receiver.transform);
 assert.deepEqual(messages,[{event:'capture_install_failed'}]);
});

test('formal RTC entry fails and interrupts on a hung receipt instead of stalling the stop queue',async()=>{
 const names=['AudioContext','AudioWorkletNode','Worker','RTCRtpScriptTransform','AudioDecoder','fetch','setTimeout','clearTimeout'];
 const saved=Object.fromEntries(names.map(name=>[name,globalThis[name]]));
 let player,request,failures=0,nextTimer=0,playback;
 const timers=new Map(),messages=[];
 try {
  globalThis.AudioContext=class {constructor(){this.sampleRate=48000;this.audioWorklet={addModule:async()=>{}};}async resume(){}async close(){}};
  globalThis.AudioWorkletNode=class {constructor(){this.port={postMessage:data=>messages.push(data)};player=this;}connect(){}disconnect(){}};
  globalThis.Worker=class {postMessage(){}terminate(){}};
  globalThis.RTCRtpScriptTransform=class {};globalThis.AudioDecoder=class {};
  globalThis.setTimeout=fn=>{timers.set(++nextTimer,fn);return nextTimer;};
  globalThis.clearTimeout=id=>timers.delete(id);
  globalThis.fetch=(url,options)=>{request=options;return new Promise(()=>{});};
  const {prepareRTCPlayback}=await import('../../src/td-rtc-entry.js');
  playback=await prepareRTCPlayback({addInitialTransceivers(){},createPeerConnection(){}},
   {sessionId:'s',token:'inert',onFailure:()=>failures++});
  player.port.onmessage({data:{event:'task_started',playback_id:'old',rendered_samples:128}});
  await new Promise(resolve=>setImmediate(resolve));
  player.port.onmessage({data:{event:'task_stopped',playback_id:'old',rendered_samples:128}});
  assert.equal(timers.size,1);[...timers.values()][0]();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(request.signal.aborted,true);assert.equal(failures,1);
  assert.ok(messages.some(item=>item.event==='interrupt' && item.requestId==='candidate-failed'));
  await playback.close();assert.equal(timers.size,0);
 } finally {
  await playback?.close();for(const name of names)globalThis[name]=saved[name];
 }
});
