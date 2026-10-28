import {test} from 'node:test';
import assert from 'node:assert/strict';
import {playbackReceipt} from '../../src/td-rtc-entry.js';
import {observeReceiveStats} from '../../src/td-rtc-entry.js';
import {loadPlaybackWorker} from '../../src/td-rtc-entry.js';

test('worker module load failure rejects startup instead of silently connecting',async()=>{
 const worker={},load=loadPlaybackWorker(worker,()=>assert.fail('not ready'));
 worker.onerror({preventDefault(){}});
 await assert.rejects(load.ready,error=>error.playbackReason==='playback_worker_unavailable');
 load.close();
});

test('worker ready has a bounded wait and does not imply playback',async()=>{
 const load=loadPlaybackWorker({},()=>{},5);
 await assert.rejects(load.ready,/Audio player could not load/);load.close();
});

test('worker runtime errors are surfaced and late errors after close are ignored',async()=>{
 const worker={},failures=[],load=loadPlaybackWorker(worker,reason=>failures.push(reason));
 worker.onmessage({data:{event:'worker_ready'}});await load.ready;
 const late=worker.onmessageerror;late();
 assert.deepEqual(failures,['playback_worker_unavailable']);
 load.close();late();assert.equal(failures.length,1);
});

test('worker failure after ready is latched even before its runtime consumer exists',async()=>{
 const worker={},load=loadPlaybackWorker(worker,()=>{});
 worker.onmessage({data:{event:'worker_ready'}});await load.ready;
 worker.onerror({preventDefault(){}});
 assert.throws(()=>load.assertHealthy(),/Audio player could not load/);
 load.close();
});

test('receiver diagnostics whitelist native counters and preserve unknown values',async()=>{
 const stats=observeReceiveStats({getStats:async()=>new Map([['audio',{
  type:'inbound-rtp',kind:'audio',packetsReceived:110,packetsLost:3,
  packetsDiscarded:undefined,trackIdentifier:'private',ssrc:123,
 }]])});
 try {
  await new Promise(resolve=>setImmediate(resolve));
  const result=stats.read();
  assert.equal(result.native_received,110);assert.equal(result.native_lost,3);
  assert.equal('native_discarded' in result,false);assert.equal('ssrc' in result,false);
  assert.ok(Number.isInteger(result.native_stats_age_ms));
 } finally {stats.close();}
});

test('closing diagnostics never waits for a hung native stats request or accepts late results',async()=>{
 let resolve;const stats=observeReceiveStats({getStats:()=>new Promise(done=>{resolve=done;})});
 stats.close();
 resolve(new Map([['a',{type:'inbound-rtp',kind:'audio',packetsReceived:1}]]));
 await new Promise(done=>setImmediate(done));
 assert.deepEqual(stats.read(),{});
});

test('failed or unavailable native counters are not fabricated',async()=>{
 const stats=observeReceiveStats({getStats:async()=>{throw Error('fixture');}});
 try {await new Promise(resolve=>setImmediate(resolve));assert.deepEqual(stats.read(),{});}
 finally {stats.close();}
});
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
  globalThis.Worker=class {constructor(){queueMicrotask(()=>this.onmessage?.({data:{event:'worker_ready'}}));}postMessage(){}terminate(){}};
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

for (const failure of ['module','worker','resume']) {
 test(`RTC preparation releases acquired resources when ${failure} fails`,async()=>{
  const names=['AudioContext','AudioWorkletNode','Worker','RTCRtpScriptTransform','AudioDecoder'];
  const saved=Object.fromEntries(names.map(name=>[name,globalThis[name]]));
  let closed=0,disconnected=0,created=0,terminated=0;
  try {
   globalThis.RTCRtpScriptTransform=class {};globalThis.AudioDecoder=class {};
   globalThis.AudioContext=class {
    constructor(){this.sampleRate=48000;this.audioWorklet={addModule:async()=>{if(failure==='module')throw Error('fixture');}};}
    async resume(){if(failure==='resume')throw Error('fixture');}
    async close(){closed++;}
   };
   globalThis.AudioWorkletNode=class {constructor(){this.port={postMessage(){}};}connect(){}disconnect(){disconnected++;}};
   globalThis.Worker=class {constructor(){if(failure==='worker' && created===1)throw Error('fixture');created++;queueMicrotask(()=>this.onmessage?.({data:{event:'worker_ready'}}));}postMessage(){}terminate(){terminated++;}};
   const {prepareRTCPlayback}=await import('../../src/td-rtc-entry.js');
   await assert.rejects(prepareRTCPlayback({}, {sessionId:'fixture',token:'inert',onFailure(){}}),/fixture/);
   assert.equal(closed,1);assert.equal(terminated,created);
   assert.equal(disconnected,failure==='module'?0:1);
  } finally {for(const name of names)globalThis[name]=saved[name];}
 });
}

for(const missing of ['RTCRtpScriptTransform','AudioDecoder']) {
 test(`missing ${missing} rejects before acquiring audio resources`,async()=>{
  const names=['RTCRtpScriptTransform','AudioDecoder','AudioContext'];
  const saved=Object.fromEntries(names.map(name=>[name,globalThis[name]]));
  try {
   globalThis.RTCRtpScriptTransform=class {};globalThis.AudioDecoder=class {};
   globalThis[missing]=undefined;
   globalThis.AudioContext=class {constructor(){throw Error('unexpected allocation');}};
   const {prepareRTCPlayback}=await import('../../src/td-rtc-entry.js');
   await assert.rejects(prepareRTCPlayback({},{}),error=>error.code==='playback_unsupported');
  } finally {for(const name of names)globalThis[name]=saved[name];}
 });
}

test('legacy receiver and sender streams are transferred without replacing RTP transport',()=>{
 const receiverStreams={readable:{kind:'rx-read'},writable:{kind:'rx-write'}};
 const senderStreams={readable:{kind:'tx-read'},writable:{kind:'tx-write'}};
 const receiver={track:{kind:'audio'},createEncodedStreams:()=>receiverStreams};
 const sender={createEncodedStreams:()=>senderStreams};
 const sent=[],worker={postMessage:(message,transfer)=>sent.push({message,transfer})};
 const transport={pc:{getTransceivers:()=>[{receiver,sender}]},addInitialTransceivers(){}};
 bindRTCTransformForTest(transport,worker,null,worker);
 transport.addInitialTransceivers();
 assert.equal(sent.length,2);
 assert.equal(sent[0].message.event,'legacy_transform');
 assert.deepEqual(sent[0].transfer,[receiverStreams.readable,receiverStreams.writable]);
 assert.deepEqual(sent[1].transfer,[senderStreams.readable,senderStreams.writable]);
 assert.equal(receiver.transform,undefined);
});

test('capability selection prefers modern transform and accepts a real legacy receiver',async()=>{
 const {rtcTransformMode}=await import('../../src/td-rtc-entry.js');
 assert.equal(rtcTransformMode({RTCRtpScriptTransform:class {}}),'script');
 assert.equal(rtcTransformMode({RTCRtpReceiver:class {createEncodedStreams(){}}}),'legacy');
 assert.equal(rtcTransformMode({}),null);
});

test('late datachannel messages after close cannot restart playback or clock requests',async()=>{
 const names=['AudioContext','AudioWorkletNode','Worker','RTCRtpScriptTransform','AudioDecoder','fetch'];
 const saved=Object.fromEntries(names.map(name=>[name,globalThis[name]]));
 let received,requests=0,posts=0;
 try {
  globalThis.AudioContext=class {constructor(){this.sampleRate=48000;this.audioWorklet={addModule:async()=>{}};}async resume(){}async close(){}};
  globalThis.AudioWorkletNode=class {constructor(){this.port={postMessage(){posts++;}};}connect(){}disconnect(){}};
  globalThis.Worker=class {constructor(){queueMicrotask(()=>this.onmessage?.({data:{event:'worker_ready'}}));}postMessage(){posts++;}terminate(){}};
  globalThis.RTCRtpScriptTransform=class {};globalThis.AudioDecoder=class {};
  globalThis.fetch=async()=>{requests++;return {ok:false};};
  const peer={addEventListener(){},createDataChannel(){return {addEventListener(type,listener){received=listener;}};}};
  const transport={addInitialTransceivers(){},createPeerConnection(){return peer;}};
  const {prepareRTCPlayback}=await import('../../src/td-rtc-entry.js');
  const playback=await prepareRTCPlayback(transport,{sessionId:'s',token:'inert',onFailure(){}});
  transport.createPeerConnection().createDataChannel();
  await playback.close();await playback.close();const before=posts;
  assert.throws(()=>transport.createPeerConnection(),/Playback is closed/);
  received({data:JSON.stringify({label:'voice-agent-playback',event:'mapping',mapping:{}})});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests,0);assert.equal(posts,before);
 } finally {for(const name of names)globalThis[name]=saved[name];}
});
