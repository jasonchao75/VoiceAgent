import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

function renderer() {
  const events = [];
  let Processor;
  const context = vm.createContext({
    AudioWorkletProcessor: class { constructor(){ this.port={postMessage:event=>events.push(event)}; } },
    registerProcessor: (_, cls) => { Processor = cls; }, Float32Array, Int16Array,
    currentFrame:0, sampleRate:24000,
  });
  vm.runInContext(readFileSync(new URL("../../src/td-audio-worklet.js", import.meta.url),"utf8"),context);
  const processor = new Processor();
  return {events, setFrame:frame=>{context.currentFrame=frame;}, write:(trackId, samples)=>processor.port.onmessage({data:{event:"write",trackId,buffer:new Int16Array(samples)}}),
    message:data=>processor.port.onmessage({data}), quantum:()=>{
      const output = new Float32Array(128); processor.process([],[[output]]); context.currentFrame+=128; return output;
    }};
}

test("rendered identity starts only in an actual quantum and finishes after end",()=>{
  const r=renderer();
  r.write("one",[16384,8192]);
  assert.equal(r.events.length,0);
  const output=r.quantum();
  assert.equal(output[0],.5); assert.equal(output[1],.25); assert.equal(output[2],0);
  const start=r.events.find(event=>event.event==="task_started");
  assert.equal(start.playback_id,"one");
  assert.equal(r.events.some(event=>event.event==="task_finished"),false);
  r.message({event:"task_end",playback_id:"one"}); r.quantum();
  const end=r.events.find(event=>event.event==="task_finished");
  assert.equal(end.rendered_samples,2);
  r.message({event:"task_end",playback_id:"one"}); r.quantum();
  assert.equal(r.events.filter(event=>event.event==="task_finished").length,1);
});

test("targeted clear removes future samples without claiming they rendered",()=>{
  const r=renderer();
  r.write("old",Array(200).fill(16384)); r.quantum();
  r.message({event:"stop_task",playback_id:"old",requestId:"stop-1"});
  const output=r.quantum(); assert.equal(output.some(value=>value!==0),false);
  const stopped=r.events.find(event=>event.event==="task_stopped");
  assert.equal(stopped.playback_id,"old"); assert.equal(stopped.rendered_samples,128);
  assert.equal(stopped.request_id,"stop-1");
  r.write("old",[32767]); assert.equal(r.quantum()[0],0);
  r.write("new",[8192]); assert.equal(r.quantum()[0],.25);
});


test("render coordinates identify first sample and preserve the last sample across late end markers",()=>{
  const r=renderer(); r.setFrame(1024);
  r.write("a",[100,100]); r.write("b",[200,200,200]); r.quantum();
  const starts=r.events.filter(event=>event.event==="task_started");
  assert.equal(starts[0].render_frame,1024);
  assert.equal(starts[1].render_frame,1026);
  assert.equal(starts[0].render_sample_rate,24000);
  r.message({event:"task_end",playback_id:"a"});
  r.message({event:"task_end",playback_id:"b"}); r.quantum();
  const ends=r.events.filter(event=>event.event==="task_finished");
  assert.equal(ends[0].render_frame,1026);
  assert.equal(ends[1].render_frame,1029);
  r.write("c",Array(200).fill(100)); r.quantum();
  r.message({event:"stop_task",playback_id:"c"}); r.quantum();
  assert.equal(r.events.find(event=>event.event==="task_stopped").render_frame,1408);
});


test('clock challenge is observed in an actual later quantum without changing audio',()=>{
  const r=renderer();
  r.message({event:'clock_sample',sample_id:'a'.repeat(32)});
  assert.equal(r.events.length,0);
  r.setFrame(1024);r.write('answer',[16384]);
  const output=r.quantum();
  const anchor=r.events.find(event=>event.event==='clock_sample');
  assert.ok(anchor);
  assert.equal(anchor.sample_id,'a'.repeat(32));
  assert.equal(anchor.render_frame,1024);
  assert.equal(anchor.render_sample_rate,24000);
  assert.equal(output[0],.5);
  assert.equal(r.events.filter(event=>event.event==='task_started').length,1);
  r.quantum();
  assert.equal(r.events.filter(event=>event.event==='clock_sample').length,1);
});
