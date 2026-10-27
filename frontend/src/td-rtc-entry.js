/* D-068 development opt-in: retain RTP and post actual Worklet facts to the session API. */
import {RTPCandidatePlayback} from './td-rtp-candidate-playback.js';
import {RenderClockSampler} from './td-render-clock.js';
import {RTPCaptureUploader} from './td-rtp-capture.js';
import {PlaybackReceiptSender} from './td-playback-receipts.js';

export function playbackReceipt(data) {
  const receipt={event:data.event,playback_id:data.playback_id,rendered_samples:data.rendered_samples,
    elapsed_ms:data.elapsed_ms,evidence_source:'audio_worklet_render',render_clock_id:data.render_clock_id};
  for(const field of ['request_id','render_frame','render_sample_rate']) if(data[field]!==undefined) receipt[field]=data[field];
  if(data.reason) receipt.failure_reason=data.reason;
  return receipt;
}

export function bindRTCTransform(transport,worker,Transform=globalThis.RTCRtpScriptTransform,inputWorker) {
  const original=transport.addInitialTransceivers.bind(transport);
  transport.addInitialTransceivers=()=>{
    original();
    const audio=transport.pc.getTransceivers().filter(item=>item.receiver.track.kind==='audio');
    if(audio.length!==1) throw new Error('Audio receiver ownership is unproven');
    audio[0].receiver.transform=new Transform(worker);
    if(inputWorker) {
      try {audio[0].sender.transform=new Transform(inputWorker);}
      catch {inputWorker.postMessage({event:'capture_install_failed'});}
    }
  };
}

export async function prepareRTCPlayback(transport,{sessionId,token,onFailure,evidence=()=>{}}) {
  if(!globalThis.RTCRtpScriptTransform || !globalThis.AudioDecoder) throw new Error('Task playback is unavailable in this browser.');
  const context=new AudioContext({sampleRate:48000});
  await context.audioWorklet.addModule(new URL('./td-audio-worklet.js',import.meta.url));
  const player=new AudioWorkletNode(context,'stream_processor');
  const worker=new Worker(new URL('./td-rtp-candidate-worker.js',import.meta.url),{type:'module'});
  const inputWorker=new Worker(new URL('./td-rtp-input-worker.js',import.meta.url),{type:'module'});
  const sourceUploader=new RTPCaptureUploader({sessionId,token,worker:inputWorker,evidence});
  inputWorker.onmessage=({data})=>{
    evidence({side:'input',...data});
    sourceUploader.observe(data);
  };
  player.connect(context.destination);
  await context.resume();
  let clockSampler;
  const receipts=new PlaybackReceiptSender({sessionId,token,
    onFailure:reason=>bridge.fail(reason)});
  const bridge=new RTPCandidatePlayback({worker,player,evidence,
    onClockSample:data=>clockSampler?.observe(data),send(message){
    if(message.event==='candidate_failed') { onFailure(message.reason);return; }
    if(message.event!=='receipt') return;
    if(message.receipt.event==='task_started') clockSampler?.pulse();
    void receipts.enqueue(playbackReceipt(message.receipt));
  }});
  clockSampler=new RenderClockSampler({sessionId,token,clockId:bridge.clock,
    sampleRate:context.sampleRate,port:player.port,
    onError:reason=>evidence({side:'clock',event:'clock_sample_unavailable',reason})});
  const control=message=>{
    if(message.event==='input_source_epoch') {sourceUploader.setEpoch(message.connection_id);return;}
    clockSampler.start();bridge.control(message);
  };
  bindRTCTransform(transport,worker,globalThis.RTCRtpScriptTransform,inputWorker);
  const original=transport.createPeerConnection.bind(transport);
  transport.createPeerConnection=()=>{
    const peer=original();
    peer.addEventListener('datachannel',event=>{
      event.channel.addEventListener('message',({data})=>{
        try { const message=JSON.parse(data);if(message.label==='voice-agent-playback') control(message); } catch { bridge.fail('invalid_playback_control'); }
      });
    });
    // The SDK creates the client-owned data channel locally.
    const createChannel=peer.createDataChannel.bind(peer);
    peer.createDataChannel=(...args)=>{
      const channel=createChannel(...args);
      channel.addEventListener('message',({data})=>{
        let message;try {message=JSON.parse(data);} catch {return;}
        if(message.label==='voice-agent-playback') control(message);
      });
      return channel;
    };
    return peer;
  };
  return {async close(){receipts.close();clockSampler.close();sourceUploader.close();worker.terminate();inputWorker.terminate();player.disconnect();await context.close();}};
}
