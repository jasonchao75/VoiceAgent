/* Isolated D-064 bridge; production routes do not opt into this candidate. */
export class RTPCandidatePlayback {
  constructor({worker,player,send,evidence=()=>{},onClockSample=()=>{}}) {
    this.worker=worker; this.player=player; this.send=send; this.evidence=evidence;
    this.samples=new Map(); this.ends=new Map(); this.closed=new Set();
    this.failed=false; this.clock=crypto.randomUUID().replaceAll('-','');
    worker.onmessage=({data})=>this.decoded(data);
    player.port.onmessage=({data})=>{
      if(data.event==='clock_sample') {onClockSample(data);return;}
      this.evidence({side:'render',...data});
      if(!['task_started','task_finished','task_stopped','task_failed'].includes(data.event)) return;
      if(data.event!=='task_started') this.closed.add(data.playback_id);
      this.send({event:'receipt',receipt:{...data,elapsed_ms:performance.now(),render_clock_id:this.clock}});
    };
  }
  control(message) {
    this.evidence({side:'control',...message});
    if(message.event==='mapping') this.worker.postMessage(message);
    else if(message.event==='task_end') {
      if(!Number.isSafeInteger(message.expected_samples) || message.expected_samples<0) return this.fail('invalid_task_extent');
      this.ends.set(message.playback_id,message.expected_samples);
      this.finish(message.playback_id);
    } else if(message.event==='stop_task') {
      this.closed.add(message.playback_id);
      this.player.port.postMessage({event:'stop_task',playback_id:message.playback_id,requestId:message.request_id});
    }
  }
  finish(id) {
    if(this.closed.has(id) || !this.ends.has(id)) return;
    const count=this.samples.get(id)||0, end=this.ends.get(id);
    if(count>end) return this.fail('decoded_extent_overflow');
    if(count===end) {
      this.ends.delete(id);
      this.player.port.postMessage({event:'task_end',playback_id:id});
    }
  }
  fail(reason,details) {
    if(this.failed) return;
    this.failed=true;
    this.evidence({side:'bridge',event:'candidate_failed',reason,details});
    this.player.port.postMessage({event:'interrupt',requestId:'candidate-failed'});
    this.send({event:'candidate_failed',reason});
  }
  decoded(data) {
    if(data.event==='mapping_failed') return this.fail(data.reason,data.details);
    if(data.event!=='task_pcm') { this.evidence({side:'decode',...data}); return; }
    this.evidence({side:'decode',...data,buffer:undefined,samples:data.buffer.length});
    if(this.failed || this.closed.has(data.task)) return;
    this.samples.set(data.task,(this.samples.get(data.task)||0)+data.buffer.length);
    this.player.port.postMessage({event:'write',trackId:data.task,buffer:data.buffer});
    this.finish(data.task);
  }
}
