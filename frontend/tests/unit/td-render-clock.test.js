import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RenderClockSampler} from '../../src/td-render-clock.js';
const flush=()=>new Promise(resolve=>setImmediate(resolve));

test('only a matching actual Worklet observation can acknowledge an authenticated challenge',async()=>{
 const requests=[],messages=[],timers=new Map();let timer=0;
 const sampler=new RenderClockSampler({sessionId:'s',token:'inert',clockId:'a'.repeat(32),sampleRate:48000,
  port:{postMessage:data=>messages.push(data)},schedule:fn=>{timers.set(++timer,fn);return timer;},cancel:id=>timers.delete(id),
  fetcher:async(url,options)=>{requests.push({url,...options});return {ok:true,json:async()=>({sample_id:'b'.repeat(32)})};}});
 sampler.start();sampler.start();await flush();
 assert.equal(requests.length,1);assert.equal(messages.length,1);
 sampler.observe({event:'clock_sample',sample_id:'c'.repeat(32),render_frame:100,render_sample_rate:48000});
 await flush();assert.equal(requests.length,1);
 sampler.observe({event:'clock_sample',sample_id:'b'.repeat(32),render_frame:1024,render_sample_rate:48000});
 await flush();assert.equal(requests.length,2);
 assert.deepEqual(JSON.parse(requests[1].body),{render_clock_id:'a'.repeat(32),render_sample_rate:48000,render_frame:1024});
 assert.equal(requests[1].headers.Authorization,'Bearer inert');
 sampler.close();assert.equal(timers.size,0);
});

test('closing during a delayed probe never writes to a replaced renderer',async()=>{
 let finish;const messages=[];
 const sampler=new RenderClockSampler({sessionId:'s',token:'inert',clockId:'a'.repeat(32),sampleRate:48000,
  port:{postMessage:data=>messages.push(data)},fetcher:()=>new Promise(resolve=>{finish=resolve;})});
 sampler.start();sampler.close();finish({ok:true,json:async()=>({sample_id:'b'.repeat(32)})});
 await flush();assert.equal(messages.length,0);assert.equal(sampler.pending,null);
});
