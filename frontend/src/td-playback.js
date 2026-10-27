import { ProtobufFrameSerializer, WavMediaManager } from "@pipecat-ai/websocket-transport";
import {installInputSourceRecorder,annotateInputPacket} from "./td-input-source.js";
import workletURL from "./td-audio-worklet.js?url";

const PREFIX = "voice-agent-audio-v1:";
const KINDS = new Set(["normal","echo","correction","overflow","incomplete"]);

function field(bytes, wanted) {
  let offset = 0;
  const integer = () => {
    let value = 0, factor = 1;
    for (let index=0;index<10 && offset<bytes.length;index++) {
      const byte=bytes[offset++]; value += (byte & 127)*factor;
      if (!(byte&128)) return value;
      factor *= 128;
    }
    throw new Error("Invalid protobuf varint");
  };
  while (offset < bytes.length) {
    const tag=integer(), type=tag%8, number=Math.floor(tag/8);
    if (!number) throw new Error("Invalid protobuf field");
    if (type===2) {
      const size=integer(), end=offset+size;
      if (!Number.isSafeInteger(end) || end>bytes.length) throw new Error("Invalid protobuf length");
      if (number===wanted) return bytes.subarray(offset,end);
      offset=end;
    } else if (type===0) integer();
    else if (type===1 || type===5) offset += type===1 ? 8 : 4;
    else throw new Error("Unsupported protobuf field");
    if (offset>bytes.length) throw new Error("Invalid protobuf boundary");
  }
  return null;
}

export function readTaskIdentity(buffer) {
  const audio=field(new Uint8Array(buffer),2), name=audio && field(audio,2);
  if (!name || name.length>1024) return null;
  const text=new TextDecoder("utf-8",{fatal:true}).decode(name);
  if (!text.startsWith(PREFIX)) return null;
  const identity=JSON.parse(text.slice(PREFIX.length));
  if (!identity || Object.keys(identity).sort().join(",")!=="kind,playback_id,response_id" ||
      typeof identity.playback_id!=="string" || !identity.playback_id || identity.playback_id.length>128 ||
      !KINDS.has(identity.kind) || (identity.response_id!==null && (typeof identity.response_id!=="string" || identity.response_id.length>256))) {
    throw new Error("Invalid audio task identity");
  }
  return Object.freeze(identity);
}

export class TaskWebSocketSerializer extends ProtobufFrameSerializer {
  constructor(manager) { super(); this.manager=manager; this.pending=Promise.resolve(); }
  serializeAudio(data,sampleRate,numChannels) {
    return annotateInputPacket(super.serializeAudio(data,sampleRate,numChannels),data,sampleRate,numChannels);
  }
  deserialize(data) {
    // Blob decoding must preserve websocket message order, including end/stop markers.
    const next=this.pending.then(async()=>{
      const buffer=await data.arrayBuffer();
      if (field(new Uint8Array(buffer),5)!==null) return {type:"raw",message:null};
      const result=await super.deserialize(data);
      if (result.type==="audio") this.manager.pendingIdentity=readTaskIdentity(buffer);
      else if (result.type==="message" && result.message.label==="voice-agent-playback") {
        this.manager.control(result.message); return {type:"raw",message:null};
      }
      return result;
    });
    this.pending=next.catch(()=>{});
    return next;
  }
}

export class TaskMediaManager extends WavMediaManager {
  constructor(recorderChunkSize, recorderSampleRate, evidence, clockFactory) {
    super(recorderChunkSize,recorderSampleRate);
    this.inputSource=installInputSourceRecorder(this._wavRecorder,clockFactory);
    this._wavStreamPlayer.scriptSrc=workletURL;
    this.evidence=evidence;
    this.clockFactory=clockFactory;
    this.clockSampler=null;
    this.identities=new Map();
    this.closedTasks=new Set();
    this.disposed=false;
    this.pendingIdentity=null;
    this.currentTask=null;
    this.ports=new WeakSet();
    this.offsetRequests=new Map();
    this._wavStreamPlayer.getTrackSampleOffset=interrupt=>this.offset(interrupt);
  }
  attach() {
    const stream=this._wavStreamPlayer.stream;
    if (!stream || this.ports.has(stream.port)) return;
    this.ports.add(stream.port);
    const original=stream.port.onmessage;
    const renderClockId=crypto.randomUUID().replaceAll("-", "");
    this.clockSampler?.close();
    const clockSampler=this.clockFactory?.({port:stream.port,clockId:renderClockId,
      sampleRate:this._wavStreamPlayer.context.sampleRate});
    this.clockSampler=clockSampler || null;
    stream.port.onmessage=event=>{
      const data=event.data;
      if(data.event==='clock_sample') {clockSampler?.observe(data);return;}
      original?.(event);
      if (data.event==="offset") {
        this.offsetRequests.get(data.requestId)?.resolve(data);
        return;
      }
      const identity=this.identities.get(data.playback_id);
      if (!identity || !["task_started","task_finished","task_stopped","task_failed"].includes(data.event)) return;
      if (data.event==="task_started") this.currentTask=identity;
      if (data.event==="task_started") clockSampler?.pulse();
      if (["task_finished","task_stopped","task_failed"].includes(data.event)) {
        this.closedTasks.add(identity.playback_id);
        if (this.currentTask?.playback_id===identity.playback_id) this.currentTask=null;
      }
      this.evidence?.({...data,...identity,evidence_source:"audio_worklet_render",
        ...(data.render_frame != null ? {render_clock_id:renderClockId} : {})});
    };
    clockSampler?.start();
  }
  bufferBotAudio(data) {
    const identity=this.pendingIdentity;
    this.pendingIdentity=null;
    if (this.disposed || (identity && this.closedTasks.has(identity.playback_id))) return new Int16Array(0);
    if (identity) this.identities.set(identity.playback_id,identity);
    const result=this._wavStreamPlayer.add16BitPCM(data,identity?.playback_id || "default");
    this.attach();
    return result;
  }
  control(message) {
    const id=message.playback_id;
    if (typeof id!=="string" || !id || id.length>128) return;
    if (message.event==="stop_task") this.closedTasks.add(id);
    if (!this.identities.has(id)) return;
    const stream=this._wavStreamPlayer.stream;
    if (!stream) return;
    if (message.event==="task_end") stream.port.postMessage({event:"task_end",playback_id:id});
    if (message.event==="stop_task") stream.port.postMessage({event:"stop_task",playback_id:id,requestId:message.request_id});
  }
  async offset(interrupt=false) {
    const stream=this._wavStreamPlayer.stream;
    if (!stream) return null;
    const requestId=crypto.randomUUID();
    let timer;
    try {
      return await new Promise((resolve,reject)=>{
        this.offsetRequests.set(requestId,{resolve,reject});
        timer=setTimeout(()=>reject(new Error("Audio renderer acknowledgement timed out")),1500);
        stream.port.postMessage({event:interrupt?"interrupt":"offset",requestId});
      });
    } finally { clearTimeout(timer); this.offsetRequests.delete(requestId); }
  }
  async userStartedSpeaking() {
    if (["echo","correction"].includes(this.currentTask?.kind)) return null;
    try { return await super.userStartedSpeaking(); }
    catch { return null; }
  }
  async disconnect() {
    this.disposed=true;
    this.clockSampler?.close();this.clockSampler=null;
    try { await super.disconnect(); }
    finally {
      this.inputSource.close();
      for (const request of this.offsetRequests.values()) request.reject(new Error("Audio renderer disconnected"));
      this.offsetRequests.clear(); this.identities.clear(); this.currentTask=null;
      this._initialized=false;
    }
  }
}
