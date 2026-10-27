import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {instrumentRecorderSource,InputSourceQueue,inputSources} from '../../src/td-input-source.js';

const sdk=readFileSync(new URL('../../node_modules/@pipecat-ai/websocket-transport/dist/index.js',import.meta.url),'utf8');
const raw=sdk.match(/AudioProcessorWorklet = `([\s\S]*?)`;\nconst/)[1];
const source=vm.runInNewContext('`'+raw+'`');
function processor(text) {
  let Type;const messages=[];
  const scope={sampleRate:16000,currentFrame:1000,
    AudioWorkletProcessor:class {constructor(){this.port={postMessage:msg=>messages.push(msg)};}},
    registerProcessor:(_name,cls)=>{Type=cls;}};
  vm.createContext(scope);vm.runInContext(text,scope);
  const instance=new Type();instance.receive({data:{event:'start',id:1}});
  return {instance,scope,messages};
}
const native=processor(source),instrumented=processor(instrumentRecorderSource(source));
for(const samples of [
  [0,0,0,0], [0,0,.2,-.3], [.5,-.4,0,1], [0,0,0,0],
]) {
  for(const item of [native,instrumented]) {
    item.instance.process([[Float32Array.from(samples)]],[],{});
    item.scope.currentFrame+=samples.length;
  }
}
const original=native.messages.filter(x=>x.event==='chunk');
const annotated=instrumented.messages.filter(x=>x.event==='chunk');
assert.equal(annotated.length,original.length);
for(let index=0;index<original.length;index++) {
  assert.deepEqual(new Uint8Array(annotated[index].data.mono),new Uint8Array(original[index].data.mono));
  assert.deepEqual(new Uint8Array(annotated[index].data.raw),new Uint8Array(original[index].data.raw));
}
assert.equal(annotated[0].source.start,1006);
assert.equal(annotated[0].source.count,2);
const queue=new InputSourceQueue();
for(const chunk of annotated) queue.push(chunk.source,chunk.data.mono.byteLength);
const buffer=new ArrayBuffer(original.reduce((sum,x)=>sum+x.data.mono.byteLength,0));
queue.take(buffer,'a'.repeat(32));
assert.deepEqual(inputSources.get(buffer),{clock_id:'a'.repeat(32),sample_rate:16000,offset:0,spans:[[1006,10]]});
queue.push(null,320);const missing=new ArrayBuffer(320);queue.take(missing,'a'.repeat(32));
assert.equal(inputSources.get(missing),undefined);
console.log('Locked SDK PCM parity, initial silence trim, contiguous merge and missing provenance passed');

const {ProtobufFrameSerializer}=await import('@pipecat-ai/websocket-transport');
const {annotateInputPacket}=await import('../../src/td-input-source.js');
const serializer=new ProtobufFrameSerializer();
const originalPacket=serializer.serializeAudio(buffer,16000,1);
const packet=annotateInputPacket(originalPacket,buffer,16000,1);
assert.notDeepEqual(packet,originalPacket);
const untagged=annotateInputPacket(originalPacket,new ArrayBuffer(20),16000,1);
assert.equal(untagged,originalPacket);
const decoded=await serializer.deserialize(new Blob([packet]));
const originalDecoded=await serializer.deserialize(new Blob([originalPacket]));
assert.deepEqual(decoded,originalDecoded);
console.log('Locked serializer accepts annotated protobuf; decoded PCM unchanged');
