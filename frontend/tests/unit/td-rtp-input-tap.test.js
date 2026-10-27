import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RTPInputTap} from '../../src/td-rtp-input-tap.js';
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const frame=()=>({timestamp:12,data:new Uint8Array([1,2,3]).buffer,
 getMetadata:()=>({synchronizationSource:7,rtpTimestamp:12,captureTime:-.5})});

test('missing native captureTime stays missing instead of using observation time',async()=>{
 const events=[];let hashed=false;
 const tap=new RTPInputTap({clockId:'a'.repeat(32),emit:e=>events.push(e),hash:async()=>{hashed=true;}});
 const input=frame();input.getMetadata=()=>({synchronizationSource:7,rtpTimestamp:12});
 assert.equal(tap.observe(input),undefined);await flush();
 assert.equal(hashed,false);assert.equal(tap.pending.size,0);
 assert.deepEqual(events,[{event:'input_capture_unavailable',reason:'capture_time_unavailable'}]);
});

test('native bytes are unchanged while async payload proof is bounded and acknowledged',async()=>{
 const events=[];let finish;
 const tap=new RTPInputTap({clockId:'a'.repeat(32),emit:e=>events.push(e),hash:data=>{
   assert.deepEqual([...new Uint8Array(data)],[1,2,3]);return new Promise(resolve=>{finish=resolve;});}});
 const input=frame(),buffer=input.data;
 assert.equal(tap.observe(input),undefined);assert.equal(input.data,buffer);
 await flush();
 finish('b'.repeat(64));await flush();
 assert.equal(events[0].record.capture_time_ms,-.5);
 assert.equal(events[0].record.rtp_timestamp,12);
 assert.equal(tap.pending.size,1);tap.acknowledge(events[0].id);assert.equal(tap.pending.size,0);
 for(let i=0;i<9;i++)tap.observe(frame());
 assert.equal(tap.pending.size,8);
 assert.equal(events.at(-1).reason,'capture_evidence_backpressure');
});
