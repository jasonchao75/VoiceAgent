/* Preserve the locked recorder's PCM conversion and batching; add provenance only. */
export const inputSources = new WeakMap();

export function instrumentRecorderSource(source) {
  return `const registerProcessor=(name,Base)=>globalThis.registerProcessor(name,class extends Base {
    constructor(){
      super();this.clockSamples=[];
      const post=this.port.postMessage.bind(this.port);
      this.port.postMessage=(message,...args)=>post(message.event==='chunk'
        ? {...message,source:this.sourceSpan}:message,...args);
    }
    receive(event){
      if(event.data.event==='clock_sample'){
        if(this.clockSamples.length<8 && /^[a-f0-9]{32}$/.test(event.data.sample_id))
          this.clockSamples.push(event.data.sample_id);
        return;
      }
      return super.receive(event);
    }
    process(inputs,outputs,parameters){
      for(const sample_id of this.clockSamples.splice(0)) this.port.postMessage({
        event:'clock_sample',sample_id,render_frame:currentFrame,render_sample_rate:sampleRate});
      this.inputFrame=currentFrame;
      this.inputLength=inputs[0]?.[0]?.length || 0;
      return super.process(inputs,outputs,parameters);
    }
    sendChunk(chunk){
      this.sourceSpan={start:this.inputFrame+this.inputLength-chunk[0].length,
        count:chunk[0].length,sampleRate};
      return super.sendChunk(chunk);
    }
  });\n${source}`;
}

export class InputSourceQueue {
  constructor() {this.offset=0;this.reset();}
  reset() {this.spans=[];this.proven=true;}
  push(source,bytes) {
    if(!source || !Number.isSafeInteger(source.start) || source.start<0
      || !Number.isSafeInteger(source.count) || source.count<=0
      || source.count*2!==bytes || source.sampleRate!==16000 || this.spans.length>=64) {
      this.proven=false;return;
    }
    const last=this.spans.at(-1);
    if(last && last[0]+last[1]===source.start) last[1]+=source.count;
    else this.spans.push([source.start,source.count]);
  }
  take(buffer,clockId) {
    const count=buffer.byteLength/2,offset=this.offset;this.offset+=count;
    const total=this.spans.reduce((sum,item)=>sum+item[1],0);
    if(this.proven && total===count && count>0 && Number.isSafeInteger(count)) {
      inputSources.set(buffer,{clock_id:clockId,sample_rate:16000,offset,
        spans:this.spans.map(item=>[...item])});
    }
    this.reset();
  }
}

export function installInputSourceRecorder(recorder,clockFactory) {
  const queue=new InputSourceQueue();
  const originalBegin=recorder.begin.bind(recorder),originalRecord=recorder.record.bind(recorder);
  let instrumentedURL=null,clockId=null,clockSampler=null;
  const originalScript=recorder.scriptSrc;
  recorder.begin=async(...args)=>{
    if(!instrumentedURL) {
      const original=recorder.scriptSrc;
      if(typeof original==='string' && original.startsWith('blob:')) {
        try {
          const response=await fetch(original,{signal:AbortSignal.timeout(2000)});
          if(!response.ok) throw new Error('Recorder source unavailable');
          instrumentedURL=URL.createObjectURL(new Blob([
            instrumentRecorderSource(await response.text())],{type:'application/javascript'}));
          recorder.scriptSrc=instrumentedURL;
        } catch { /* Missing provenance must not replace or delay microphone PCM. */ }
      }
    }
    const result=await originalBegin(...args);
    clockId=crypto.randomUUID().replaceAll('-','');queue.reset();
    clockSampler?.close();
    const port=recorder.processor?.port,original=port?.onmessage;
    clockSampler=instrumentedURL && port ? clockFactory?.({port,clockId,
      sampleRate:recorder.sampleRate,clockKind:'capture'}):null;
    if(port) port.onmessage=event=>{
      if(event.data.event==='clock_sample'){clockSampler?.observe(event.data);return;}
      if(event.data.event==='chunk') queue.push(event.data.source,event.data.data.mono.byteLength);
      original?.(event);
    };
    clockSampler?.start();
    return result;
  };
  recorder.record=(callback=()=>{},...args)=>{
    // The SDK clears its partial PCM buffer at exactly this boundary.
    queue.reset();
    return originalRecord(data=>{queue.take(data.mono,clockId);callback(data);},...args);
  };
  return {close:()=>{
    clockSampler?.close();clockSampler=null;
    if(instrumentedURL) URL.revokeObjectURL(instrumentedURL);
    instrumentedURL=null;recorder.scriptSrc=originalScript;
  }};
}

function encodeInteger(value) {
  const bytes=[];
  do {const byte=value%128;value=Math.floor(value/128);bytes.push(byte+(value?128:0));} while(value);
  return bytes;
}
function replaceBytes(bytes,wanted,replace) {
  let position=0,found=false;const parts=[];
  const integer=()=>{
    let value=0,factor=1;
    for(let index=0;index<10 && position<bytes.length;index++) {
      const byte=bytes[position++];value+=(byte&127)*factor;
      if(!(byte&128)) return value;
      factor*=128;
    }
    throw new Error('Invalid input envelope');
  };
  while(position<bytes.length) {
    const start=position,tag=integer(),kind=tag%8,number=Math.floor(tag/8);
    if(!number) throw new Error('Invalid input field');
    if(kind===2) {
      const size=integer(),payload=position;position+=size;
      if(!Number.isSafeInteger(position)||position>bytes.length) throw new Error('Invalid input length');
      if(number===wanted) {
        if(found) throw new Error('Duplicate input field');
        found=true;const replacement=replace(bytes.subarray(payload,position));
        parts.push(Uint8Array.from([...encodeInteger(tag),...encodeInteger(replacement.length)]),replacement);
        continue;
      }
    } else if(kind===0) integer();
    else if(kind===1) position+=8;
    else if(kind===5) position+=4;
    else throw new Error('Unsupported input field');
    if(position>bytes.length) throw new Error('Invalid input boundary');
    parts.push(bytes.subarray(start,position));
  }
  if(!found) throw new Error('Missing input field');
  const result=new Uint8Array(parts.reduce((sum,part)=>sum+part.length,0));let offset=0;
  for(const part of parts){result.set(part,offset);offset+=part.length;}
  return result;
}

export function annotateInputPacket(packet,pcm,sampleRate,channels) {
  const metadata=inputSources.get(pcm);
  if(!metadata || sampleRate!==16000 || channels!==1) return packet;
  try {
    const name=new TextEncoder().encode('voice-agent-input-v1:'+JSON.stringify(metadata));
    if(name.length>4096) return packet;
    return replaceBytes(new Uint8Array(packet),2,audio=>replaceBytes(audio,2,()=>name));
  } catch {return packet;}
}
