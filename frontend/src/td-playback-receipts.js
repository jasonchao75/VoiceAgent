/* Receipt uncertainty ends the call; it never releases an unconfirmed playback slot. */
export class PlaybackReceiptSender {
  constructor({sessionId,token,onFailure,timeoutMs=3000,
    fetcher=(...args)=>globalThis.fetch(...args),
    schedule=(...args)=>globalThis.setTimeout(...args),cancel=(...args)=>globalThis.clearTimeout(...args)}) {
    Object.assign(this,{sessionId,token,onFailure,timeoutMs,fetcher,schedule,cancel});
    this.queue=Promise.resolve();this.closed=false;this.failed=false;this.controller=null;this.rejectPending=null;
  }
  enqueue(receipt) {
    this.queue=this.queue.then(()=>this.deliver(receipt)).catch(()=>{
      if(this.closed || this.failed) return;
      this.failed=true;this.onFailure('playback_receipt_unconfirmed');
    });
    return this.queue;
  }
  async deliver(receipt) {
    if(this.closed || this.failed) return;
    const controller=new AbortController();this.controller=controller;
    let deadline;
    const timeout=new Promise((resolve,reject)=>{
      this.rejectPending=reject;
      deadline=this.schedule(()=>{controller.abort();reject(new Error('receipt_timeout'));},this.timeoutMs);
    });
    try {
      const response=await Promise.race([this.fetcher(
        `/api/sessions/${encodeURIComponent(this.sessionId)}/playback-events`,{
          method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${this.token}`},
          body:JSON.stringify(receipt),signal:controller.signal,
        }),timeout]);
      if(!response.ok) throw new Error('receipt_rejected');
    } finally {
      this.cancel(deadline);this.rejectPending=null;
      if(this.controller===controller)this.controller=null;
    }
  }
  close() {
    this.closed=true;this.controller?.abort();this.rejectPending?.(new Error('receipt_sender_closed'));
  }
}
