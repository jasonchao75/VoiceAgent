/* Observe native sender metadata without holding, rewriting or substituting audio. */
export class RTPInputTap {
  constructor({emit,clockId,hash=async data=>Array.from(new Uint8Array(
    await crypto.subtle.digest('SHA-256',data)),value=>value.toString(16).padStart(2,'0')).join('')}) {
    Object.assign(this,{emit,clockId,hash});
    this.pending=new Set();this.sequence=0;this.disabled=false;this.notified=new Set();
  }
  unavailable(reason) {
    if(this.notified.has(reason)) return;
    this.notified.add(reason);this.emit({event:'input_capture_unavailable',reason});
  }
  acknowledge(id) {this.pending.delete(id);}
  observe(frame) {
    if(this.disabled) return;
    if(this.pending.size>=8) {this.unavailable('capture_evidence_backpressure');return;}
    let metadata,timestamp,data;
    try {
      metadata=frame.getMetadata();timestamp=metadata.rtpTimestamp ?? frame.timestamp;
      if(!Number.isInteger(metadata.synchronizationSource) || metadata.synchronizationSource<0
        || metadata.synchronizationSource>=2**32 || !Number.isInteger(timestamp)
        || timestamp<0 || timestamp>=2**32
        || (metadata.rtpTimestamp!==undefined && frame.timestamp!==undefined
            && metadata.rtpTimestamp!==frame.timestamp)) throw new Error('rtp_identity_unavailable');
      if(typeof metadata.captureTime!=='number' || !Number.isFinite(metadata.captureTime))
        throw new Error('capture_time_unavailable');
      if(!(frame.data instanceof ArrayBuffer) || !frame.data.byteLength || frame.data.byteLength>65536)
        throw new Error('encoded_payload_unavailable');
      data=frame.data.slice(0);
    } catch(error) {
      this.disabled=true;this.unavailable(error.message || 'capture_metadata_unavailable');return;
    }
    const id=++this.sequence;this.pending.add(id);
    // Hashing is asynchronous and never becomes transform backpressure for native RTP.
    Promise.resolve().then(()=>this.hash(data)).then(digest=>{
      if(!/^[a-f0-9]{64}$/.test(digest)) throw new Error('payload_hash_unavailable');
      this.emit({event:'input_capture_packet',id,record:{clock_id:this.clockId,
        ssrc:metadata.synchronizationSource,rtp_timestamp:timestamp,payload_sha256:digest,
        capture_time_ms:metadata.captureTime,capture_clock:'worker_performance'}});
    }).catch(()=>{this.pending.delete(id);this.unavailable('payload_hash_unavailable');});
  }
}
