import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {webcrypto} from 'node:crypto';
import vm from 'node:vm';

const workerPath=new URL('../../src/td-rtp-candidate-worker.js',import.meta.url);

async function replay({badExtent=false,drop=0,silent=false,reorder=false,packetsFirst=false,decodeDelay=0,omitMappings=false,missingSilentIndex=-1,liveQueue=false,oldIntake=false}={}) {
  const events=[];
  const source=await readFile(workerPath,'utf8');
  let PacketDecoder;
  try { ({RTPPacketDecoder:PacketDecoder}=await import('../../src/td-rtp-decode-job.js')); }
  catch(error) { if(error.code!=='ERR_MODULE_NOT_FOUND') throw error; }
  let count=0, resolve;
  const complete=new Promise(done=>{resolve=done;});
  class FakeDecoder {
    constructor(callbacks) { this.callbacks=callbacks;this.state='configured';this.output=0; }
    configure() {}
    decode(chunk) {
      const index=this.output++;
      queueMicrotask(()=>this.callbacks.output({
        timestamp:chunk.timestamp-(index===13?1:0),sampleRate:48000,
        numberOfFrames:badExtent && index===13?959:960,
        copyTo:array=>array.fill(.1),close:()=>{},
      }));
    }
    async flush() { if(decodeDelay) await new Promise(done=>setTimeout(done,decodeDelay)); else await Promise.resolve(); }
    close() { this.state='closed'; }
  }
  const context=vm.createContext({RTPPacketDecoder:PacketDecoder,
    AudioDecoder:FakeDecoder,EncodedAudioChunk:class {constructor(data){Object.assign(this,data);}},
    self:{postMessage:data=>{
      events.push(data);
      if(data.event==='decoded') count++;
      if(data.event==='mapping_failed' || count===14-drop-(missingSilentIndex>=0?1:0)) resolve();
    }},crypto:webcrypto,performance,TransformStream,ReadableStream,WritableStream,
    setTimeout:(...args)=>{const timer=setTimeout(...args);timer.unref();return timer;},clearTimeout,
  });
  let workerSource=source.replace(/^import .*;\n/gm,'');
  if(oldIntake) workerSource=workerSource.replace('void deliver();\n        // The native','await deliver();\n        // The native');
  vm.runInContext(workerSource,context);
  const packets=[],mappingMessages=[];
  for(let index=0;index<14;index++) {
    const data=new Uint8Array([index,123]).buffer;
    const digest=Buffer.from(await webcrypto.subtle.digest('SHA-256',data)).toString('hex');
    const start=-312+index*960;
    mappingMessages.push({data:{event:'mapping',mapping:{version:1,ssrc:12,
      rtp_timestamp:100000+index*960,payload_sha256:digest,source_start:start,samples:960,
      spans:[{start:Math.max(0,start),end:start+960,task:(silent && index<drop) || index===missingSilentIndex?null:'A'}]}}});
    packets.push({data,timestamp:100000+index*960,getMetadata:()=>({synchronizationSource:12})});
  }
  if(!packetsFirst && !omitMappings) for(const message of mappingMessages) await context.self.onmessage(message);
  context.self.onrtctransform({transformer:{
    readable:new ReadableStream({start(controller){
      const input=reorder?[packets[1],packets[0],...packets.slice(2)]:packets.slice(drop).filter((_,i)=>i+drop!==missingSilentIndex);
      if(!liveQueue) {for(const packet of input)controller.enqueue(packet);controller.close();return;}
      // A bounded live producer models receiver discard under backpressure; it is not a browser implementation.
      let index=0;
      const tick=()=>{
        if(index===input.length){controller.close();return;}
        const packet=input[index++];
        if(controller.desiredSize>0) controller.enqueue(packet);
        else events.push({event:'fixture_receiver_discard',rtp_timestamp:packet.timestamp});
        setTimeout(tick,20);
      };
      tick();
    }}, {highWaterMark:2}),
    writable:new WritableStream({write(){}}),
  }});
  if(packetsFirst && !omitMappings) {
    await new Promise(done=>setTimeout(done,30));
    for(const message of mappingMessages) void context.self.onmessage(message);
  }
  await Promise.race([complete,new Promise((_,reject)=>setTimeout(()=>reject(new Error('Offline replay deadline')),2000))]);
  return events;
}

test('saved 1253499us output remains bound to its own 1253500us decode job without a tolerance',async()=>{
  const events=await replay();
  assert.deepEqual(events.filter(e=>e.event==='mapping_failed'),[]);
  assert.equal(events.filter(e=>e.event==='decoded').length,14);
  assert.ok(events.some(e=>e.event==='task_pcm' && e.start===12168));
});

test('real output extent disagreement remains rejected instead of guessing ownership',async()=>{
  const events=await replay({badExtent:true});
  assert.equal(events.filter(e=>e.event==='mapping_failed').length,1);
  assert.equal(events.filter(e=>e.event==='task_pcm' && e.start===12168).length,0);
});


test('missing source-proven startup silence does not abort or claim rendered samples',async()=>{
  const events=await replay({drop:3,silent:true});
  assert.equal(events.filter(e=>e.event==='silent_packet_skipped').length,3);
  assert.equal(events.filter(e=>e.event==='mapping_failed').length,0);
  assert.equal(events.filter(e=>e.event==='decoded').length,11);
  assert.ok(events.filter(e=>e.event==='task_pcm').every(e=>e.start>=2568));
});

test('missing task audio still fails without a fabricated success',async()=>{
  const events=await replay({drop:3});
  assert.equal(events.find(e=>e.event==='mapping_failed')?.reason,'packet_deadline');
  assert.equal(events.filter(e=>e.event==='task_pcm').length,0);
});

test('out of order RTP is decoded in reliable source order',async()=>{
  const events=await replay({reorder:true});
  assert.equal(events.filter(e=>e.event==='mapping_failed').length,0);
  assert.deepEqual(events.filter(e=>e.event==='decoded').map(e=>e.source_start),Array.from({length:14},(_,i)=>-312+i*960));
});


test('already matched packets waiting for ordered decode are not missing mappings',async()=>{
  const events=await replay({packetsFirst:true,decodeDelay:90});
  assert.equal(events.filter(e=>e.event==='mapping_failed').length,0);
  assert.equal(events.filter(e=>e.event==='decoded').length,14);
});

test('mapping-first audio intake does not wait for earlier decode jobs',async()=>{
  const events=await replay({decodeDelay:90});
  assert.equal(events.find(e=>e.event==='mapping_failed')?.reason,undefined);
  assert.equal(events.filter(e=>e.event==='decoded').length,14);
});

test('bounded live receiver can discard task packets when old intake waits on decode',async()=>{
  const events=await replay({liveQueue:true,oldIntake:true,decodeDelay:90});
  assert.ok(events.some(e=>e.event==='fixture_receiver_discard'));
  const failure=events.find(e=>e.event==='mapping_failed');
  assert.equal(failure?.reason,'packet_deadline');
  assert.equal(failure.details.head_state,'missing_task');
  assert.equal(failure.details.decoding,false);
});

test('decoupled intake drains a bounded live receiver without discarding task packets',async()=>{
  const events=await replay({liveQueue:true,decodeDelay:90});
  assert.equal(events.filter(e=>e.event==='fixture_receiver_discard').length,0);
  assert.equal(events.filter(e=>e.event==='mapping_failed').length,0);
  assert.equal(events.filter(e=>e.event==='decoded').length,14);
});


test('a genuinely missing mapping still times out',async()=>{
  const events=await replay({packetsFirst:true,omitMappings:true});
  assert.equal(events.find(e=>e.event==='mapping_failed')?.reason,'mapping_deadline');
  assert.equal(events.filter(e=>e.event==='task_pcm').length,0);
});

test('an individual stalled decode still times out with matching evidence',async()=>{
  const events=await replay({packetsFirst:true,decodeDelay:1200});
  assert.equal(events.find(e=>e.event==='mapping_failed')?.reason,'decode_deadline');
  assert.equal(events.filter(e=>e.event==='task_pcm').length,0);
});


test('missing source-proven silence waiting behind slow matched jobs is not task loss',async()=>{
  const events=await replay({packetsFirst:true,decodeDelay:90,missingSilentIndex:12});
  assert.equal(events.filter(e=>e.event==='mapping_failed').length,0);
  assert.equal(events.filter(e=>e.event==='decoded').length,13);
  assert.equal(events.filter(e=>e.event==='silent_packet_skipped').length,1);
});
