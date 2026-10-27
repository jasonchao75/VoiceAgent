import {RenderClockSampler} from './td-render-clock.js';
/* Metadata never delays audio; a missing batch remains a missing source interval. */
export class RTPCaptureUploader {
  constructor({sessionId,token,worker,evidence=()=>{},
    fetcher=(...args)=>globalThis.fetch(...args),
    schedule=(...args)=>globalThis.setTimeout(...args),cancel=(...args)=>globalThis.clearTimeout(...args),
    clockFactory=config=>new RenderClockSampler(config)}) {
    Object.assign(this,{sessionId,token,worker,evidence,fetcher,schedule,cancel,clockFactory});
    this.queue=[];this.epoch=null;this.timer=null;this.controller=null;this.closed=false;
    this.clock=null;this.sampler=null;this.disabled=false;
  }
  setEpoch(epoch) {
    if(this.closed || !/^[a-f0-9]{32}$/.test(epoch)) return;
    if(this.epoch && this.epoch!==epoch) {
      // A live worker cannot attest which old-peer callbacks raced a new peer epoch.
      this.disabled=true;this.queue=[];this.sampler?.close();
      this.evidence({event:'input_capture_upload_unavailable',reason:'source_epoch_changed'});
      return;
    }
    this.epoch=epoch;this.scheduleFlush();
  }
  observe(message) {
    if(this.closed) return;
    if(message.event==='clock_sample') {this.sampler?.observe(message);return;}
    if(message.event!=='input_capture_packet') return;
    this.worker.postMessage({event:'input_capture_observed',id:message.id});
    if(this.disabled) return;
    const record=message.record;
    if(!record || !/^[a-f0-9]{32}$/.test(record.clock_id)) return;
    if(this.clock && this.clock!==record.clock_id) {
      this.disabled=true;this.queue=[];this.sampler?.close();return;
    }
    if(!this.sampler) {
      this.clock=record.clock_id;
      this.sampler=this.clockFactory({sessionId:this.sessionId,token:this.token,clockId:this.clock,
        sampleRate:16000,clockKind:'capture',port:this.worker,fetcher:this.fetcher,
        schedule:this.schedule,cancel:this.cancel,
        onError:reason=>this.evidence({event:'capture_clock_unavailable',reason})});
      this.sampler.start();
    }
    if(this.queue.length>=64) {
      this.evidence({event:'input_capture_upload_unavailable',reason:'source_queue_limit'});return;
    }
    const {clock_id,ssrc,rtp_timestamp,payload_sha256,capture_time_ms,capture_clock}=record;
    this.queue.push({clock_id,ssrc,rtp_timestamp,payload_sha256,capture_time_ms,capture_clock});
    this.scheduleFlush();
  }
  scheduleFlush() {
    if(this.closed || this.disabled || !this.epoch || !this.queue.length
      || this.timer!==null || this.controller) return;
    this.timer=this.schedule(()=>{this.timer=null;void this.flush();},100);
  }
  async flush() {
    if(this.closed || this.disabled || !this.epoch || !this.queue.length || this.controller) return;
    if(this.timer!==null) this.cancel(this.timer);this.timer=null;
    const records=this.queue.splice(0,16),controller=new AbortController();this.controller=controller;
    const deadline=this.schedule(()=>controller.abort(),1000);
    try {
      const response=await this.fetcher(`/api/sessions/${encodeURIComponent(this.sessionId)}/rtp-input`,{
        method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${this.token}`},
        body:JSON.stringify({connection_id:this.epoch,records}),signal:controller.signal});
      if(!response.ok) throw new Error('source_report_rejected');
    } catch {
      if(!this.closed)this.evidence({event:'input_capture_upload_unavailable',reason:'source_report_unavailable'});
    } finally {
      this.cancel(deadline);if(this.controller===controller)this.controller=null;
      this.scheduleFlush();
    }
  }
  close() {
    this.closed=true;this.queue=[];this.sampler?.close();this.controller?.abort();
    if(this.timer!==null)this.cancel(this.timer);this.timer=null;
  }
}
