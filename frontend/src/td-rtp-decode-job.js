/* One verified Opus packet owns one completed decode job, not a rounded timestamp key. */
export class RTPPacketDecoder {
  constructor({Decoder,Chunk,onFailure}) {
    this.Chunk=Chunk; this.onFailure=onFailure; this.job=null;
    this.codec=new Decoder({
      output:frame=>{
        try {
          const job=this.job;
          if(!job) { this.onFailure('decode_job_unowned_output'); return; }
          if(job.output || frame.sampleRate!==48000 || frame.numberOfFrames!==job.samples) {
            job.error=new Error('decode_job_extent_mismatch');return;
          }
          const values=new Float32Array(frame.numberOfFrames);
          frame.copyTo(values,{planeIndex:0,format:'f32-planar'});
          job.output={values,timestamp:frame.timestamp,samples:frame.numberOfFrames,sample_rate:frame.sampleRate};
        } catch { if(this.job) this.job.error=new Error('decode_job_output_unproven'); }
        finally { frame.close(); }
      },
      error:()=>this.onFailure('decoder_error'),
    });
    this.codec.configure({codec:'opus',sampleRate:48000,numberOfChannels:2});
  }
  get state() { return this.codec.state; }
  close() { if(this.codec.state!=='closed') this.codec.close(); }
  async decodePacket(data,samples,timestamp) {
    if(this.job) throw new Error('decode_job_reentry');
    const job={samples,output:null,error:null};
    this.job=job;
    try {
      this.codec.decode(new this.Chunk({type:'key',timestamp,data}));
      // WebCodecs flush resolves after all queued decode outputs are emitted;
      // retaining this decoder preserves its codec state between packet jobs.
      await this.codec.flush();
      if(job.error) throw job.error;
      if(!job.output) throw new Error('decode_job_output_unproven');
      return job.output;
    } finally { this.job=null; }
  }
}
