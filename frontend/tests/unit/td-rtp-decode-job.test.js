import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {webcrypto} from 'node:crypto';
import vm from 'node:vm';

const workerPath=new URL('../../src/td-rtp-candidate-worker.js',import.meta.url);

async function replay({badExtent=false}={}) {
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
    async flush() { await Promise.resolve(); }
    close() { this.state='closed'; }
  }
  const context=vm.createContext({RTPPacketDecoder:PacketDecoder,
    AudioDecoder:FakeDecoder,EncodedAudioChunk:class {constructor(data){Object.assign(this,data);}},
    self:{postMessage:data=>{
      events.push(data);
      if(data.event==='decoded') count++;
      if(data.event==='mapping_failed' || count===14) resolve();
    }},crypto:webcrypto,performance,TransformStream,ReadableStream,WritableStream,
    setTimeout:(...args)=>{const timer=setTimeout(...args);timer.unref();return timer;},clearTimeout,
  });
  vm.runInContext(source.replace(/^import .*;\n/gm,''),context);
  const packets=[];
  for(let index=0;index<14;index++) {
    const data=new Uint8Array([index,123]).buffer;
    const digest=Buffer.from(await webcrypto.subtle.digest('SHA-256',data)).toString('hex');
    const start=-312+index*960;
    await context.self.onmessage({data:{event:'mapping',mapping:{version:1,ssrc:12,
      rtp_timestamp:100000+index*960,payload_sha256:digest,source_start:start,samples:960,
      spans:[{start:Math.max(0,start),end:start+960,task:'A'}]}}});
    packets.push({data,timestamp:100000+index*960,getMetadata:()=>({synchronizationSource:12})});
  }
  context.self.onrtctransform({transformer:{
    readable:new ReadableStream({start(controller){for(const packet of packets)controller.enqueue(packet);controller.close();}}),
    writable:new WritableStream({write(){}}),
  }});
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
