/* D-073: sample causal render anchors without delaying or changing audio. */
export class RenderClockSampler {
  constructor({sessionId,token,clockId,sampleRate,port,clockKind='render',fetcher=(...args)=>globalThis.fetch(...args),
    schedule=(...args)=>globalThis.setTimeout(...args),
    cancel=(...args)=>globalThis.clearTimeout(...args),onError=()=>{}}) {
    Object.assign(this,{sessionId,token,clockId,sampleRate,port,clockKind,fetcher,schedule,cancel,onError});
    this.active=false;this.pending=null;this.next=null;this.controller=null;
    this.urgent=false;
  }
  start() {
    if(this.active) return;
    this.active=true;void this.sample();
  }
  observe(data) {
    if(data.event!=='clock_sample' || data.sample_id!==this.pending?.id
      || data.render_sample_rate!==this.sampleRate || !Number.isSafeInteger(data.render_frame)
      || data.render_frame<0) return;
    this.pending.resolve(data.render_frame);
  }
  pulse() {
    if(!this.active) return;
    if(this.controller) {this.urgent=true;return;}
    if(this.next!==null) this.cancel(this.next);
    this.next=null;void this.sample();
  }
  async sample() {
    if(!this.active) return;
    const controller=new AbortController();this.controller=controller;
    const deadline=this.schedule(()=>{
      controller.abort();this.pending?.reject(new Error('clock_sample_timeout'));
    },2000);
    const url=`/api/sessions/${encodeURIComponent(this.sessionId)}/playback-clock`;
    const headers={'Content-Type':'application/json',Authorization:`Bearer ${this.token}`};
    const clock={render_clock_id:this.clockId,render_sample_rate:this.sampleRate,
      ...(this.clockKind==='capture'?{clock_kind:'capture'}:{})};
    try {
      const issued=await this.fetcher(url,{method:'POST',headers,body:JSON.stringify(clock),signal:controller.signal});
      if(!issued.ok) throw new Error('clock_probe_rejected');
      const {sample_id}=await issued.json();
      if(!this.active || controller.signal.aborted) return;
      if(typeof sample_id!=='string' || !/^[a-f0-9]{32}$/.test(sample_id)) throw new Error('clock_probe_invalid');
      const frame=await new Promise((resolve,reject)=>{
        this.pending={id:sample_id,resolve,reject};
        this.port.postMessage({event:'clock_sample',sample_id});
      });
      if(!this.active || controller.signal.aborted) return;
      const ack=await this.fetcher(`${url}/${sample_id}`,{method:'POST',headers,
        body:JSON.stringify({...clock,render_frame:frame}),signal:controller.signal});
      if(!ack.ok) throw new Error('clock_ack_rejected');
    } catch {
      if(this.active) this.onError('render_clock_sample_unavailable');
    } finally {
      this.cancel(deadline);this.pending=null;
      if(this.controller===controller) this.controller=null;
      const delay=this.urgent?0:500;this.urgent=false;
      if(this.active) this.next=this.schedule(()=>{this.next=null;void this.sample();},delay);
    }
  }
  close() {
    this.active=false;
    if(this.next!==null) this.cancel(this.next);
    this.next=null;this.controller?.abort();
    this.pending?.reject(new Error('clock_sampler_closed'));
  }
}
