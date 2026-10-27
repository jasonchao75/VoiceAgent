import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RTPCaptureUploader} from '../../src/td-rtp-capture.js';
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const record={clock_id:'a'.repeat(32),ssrc:7,rtp_timestamp:10,payload_sha256:'b'.repeat(64),
 capture_time_ms:201,capture_clock:'worker_performance'};

test('native metadata waits for server epoch and uses a separate authenticated capture sampler',async()=>{
 const messages=[],requests=[],clocks=[],timers=new Map();let id=0;
 const upload=new RTPCaptureUploader({sessionId:'s',token:'inert',worker:{postMessage:x=>messages.push(x)},
  clockFactory:config=>{clocks.push(config);return {start(){},close(){},observe(){}};},
  schedule:fn=>{timers.set(++id,fn);return id;},cancel:n=>timers.delete(n),
  fetcher:async(url,options)=>{requests.push({url,options});return {ok:true};}});
 upload.observe({event:'input_capture_packet',id:1,record});
 await flush();assert.equal(requests.length,0);
 assert.equal(clocks[0].clockKind,'capture');assert.equal(clocks[0].sampleRate,16000);
 assert.deepEqual(messages,[{event:'input_capture_observed',id:1}]);
 upload.setEpoch('c'.repeat(32));await upload.flush();
 assert.equal(requests.length,1);
 assert.deepEqual(JSON.parse(requests[0].options.body),{connection_id:'c'.repeat(32),records:[record]});
 assert.equal(requests[0].options.headers.Authorization,'Bearer inert');
 upload.setEpoch('d'.repeat(32));upload.observe({event:'input_capture_packet',id:2,record});
 await upload.flush();assert.equal(requests.length,1);
 upload.close();assert.equal(timers.size,0);
});

test('closing aborts metadata work without retrying a batch or touching native audio',async()=>{
 let resolve;const calls=[];
 const upload=new RTPCaptureUploader({sessionId:'s',token:'inert',worker:{postMessage(){}},
  clockFactory:()=>({start(){},close(){},observe(){}}),fetcher:(url,options)=>{
   calls.push(options);return new Promise(done=>{resolve=done;});}});
 upload.setEpoch('c'.repeat(32));upload.observe({event:'input_capture_packet',id:1,record});
 const pending=upload.flush();upload.close();assert.equal(calls[0].signal.aborted,true);
 resolve({ok:true});await pending;await flush();assert.equal(calls.length,1);
});
