/* Keep RTP audio and report actual Worklet playback through modern or legacy transforms. */
import {RTPCandidatePlayback} from './td-rtp-candidate-playback.js';
import {RenderClockSampler} from './td-render-clock.js';
import {RTPCaptureUploader} from './td-rtp-capture.js';
import {PlaybackReceiptSender} from './td-playback-receipts.js';

export function loadPlaybackWorker(worker,onRuntimeFailure,timeoutMs=10000) {
  let ready=false,closed=false,timer,rejectReady,failure;
  const fail=()=>{
    if(closed || failure)return;
    clearTimeout(timer);
    const error=new Error('Audio player could not load. Reload this page before trying again.');
    error.code='playback_failed';error.playbackReason='playback_worker_unavailable';
    failure=error;
    if(ready) {onRuntimeFailure('playback_worker_unavailable');return;}
    rejectReady(error);
  };
  const promise=new Promise((resolve,reject)=>{
    rejectReady=reject;
    worker.onmessage=({data})=>{
      if(closed || data?.event!=='worker_ready')return;
      ready=true;clearTimeout(timer);worker.onmessage=null;resolve();
    };
    worker.onerror=event=>{event.preventDefault?.();fail();};
    worker.onmessageerror=fail;
    timer=setTimeout(fail,timeoutMs);
  });
  return {ready:promise,assertHealthy(){if(failure)throw failure;},close(){closed=true;clearTimeout(timer);worker.onerror=null;worker.onmessageerror=null;}};
}

export function playbackReceipt(data) {
  const receipt={event:data.event,playback_id:data.playback_id,rendered_samples:data.rendered_samples,
    elapsed_ms:data.elapsed_ms,evidence_source:'audio_worklet_render',render_clock_id:data.render_clock_id};
  for(const field of ['request_id','render_frame','render_sample_rate']) if(data[field]!==undefined) receipt[field]=data[field];
  if(data.reason) receipt.failure_reason=data.reason;
  return receipt;
}

export function rtcTransformMode(scope=globalThis) {
  if(typeof scope.RTCRtpScriptTransform==='function') return 'script';
  if(typeof scope.RTCRtpReceiver?.prototype?.createEncodedStreams==='function') return 'legacy';
  return null;
}

export function observeReceiveStats(peer) {
  let closed=false,busy=false,snapshot={},observedAt=null;
  const fields={packetsReceived:'native_received',packetsLost:'native_lost',packetsDiscarded:'native_discarded'};
  async function sample() {
    if(closed || busy) return;
    busy=true;
    const requestedAt=performance.now();
    try {
      const reports=await peer.getStats();
      const audio=[...reports.values()].filter(item=>item.type==='inbound-rtp' && item.kind==='audio');
      if(closed || audio.length!==1) return;
      const next={};
      for(const [field,key] of Object.entries(fields)) {
        const value=audio[0][field];
        // Missing native counters remain unknown; never turn unavailable evidence into zero loss.
        if(Number.isSafeInteger(value) && value>=0 && value<=10000000) next[key]=value;
      }
      // Include collection latency so a slow native call cannot make old evidence look fresh.
      snapshot=next;observedAt=requestedAt;
    } catch { /* Diagnostics must not affect playback or cleanup. */ }
    finally {busy=false;}
  }
  const timer=typeof peer.getStats==='function'?setInterval(()=>void sample(),500):null;
  if(timer!==null) void sample();
  return {
    read:()=>observedAt===null?{}:{...snapshot,native_stats_age_ms:Math.min(7200000,Math.max(0,Math.round(performance.now()-observedAt)))},
    close(){closed=true;if(timer!==null)clearInterval(timer);},
  };
}

function bindEncodedStream(endpoint,worker,Transform) {
  if(Transform) {endpoint.transform=new Transform(worker);return;}
  const {readable,writable}=endpoint.createEncodedStreams();
  worker.postMessage({event:'legacy_transform',readable,writable},[readable,writable]);
}

export function bindRTCTransform(transport,worker,Transform=globalThis.RTCRtpScriptTransform,inputWorker) {
  const original=transport.addInitialTransceivers.bind(transport);
  transport.addInitialTransceivers=()=>{
    original();
    const audio=transport.pc.getTransceivers().filter(item=>item.receiver.track.kind==='audio');
    if(audio.length!==1) throw new Error('Audio receiver ownership is unproven');
    bindEncodedStream(audio[0].receiver,worker,Transform);
    if(inputWorker) {
      try {bindEncodedStream(audio[0].sender,inputWorker,Transform);}
      catch {inputWorker.postMessage({event:'capture_install_failed'});}
    }
  };
}

export async function prepareRTCPlayback(transport,{sessionId,token,onFailure,evidence=()=>{}}) {
  if(!rtcTransformMode() || !globalThis.AudioDecoder) {
    const error=new Error('This browser cannot play identifier echoes. Open this link in an up-to-date browser.');
    error.code='playback_unsupported';
    throw error;
  }
  const context=new AudioContext({sampleRate:48000});
  let player,worker,inputWorker,sourceUploader,workerLifecycle,bridge;
  try {
  await context.audioWorklet.addModule(new URL('./td-audio-worklet.js',import.meta.url));
  player=new AudioWorkletNode(context,'stream_processor');
  worker=new Worker(new URL('./td-rtp-candidate-worker.js',import.meta.url),{type:'module'});
  workerLifecycle=loadPlaybackWorker(worker,reason=>bridge?.fail(reason));
  // A constructed Worker is not proof its script loaded; do not mute native audio and connect blind.
  await workerLifecycle.ready;
  inputWorker=new Worker(new URL('./td-rtp-input-worker.js',import.meta.url),{type:'module'});
  sourceUploader=new RTPCaptureUploader({sessionId,token,worker:inputWorker,evidence});
  inputWorker.onmessage=({data})=>{
    evidence({side:'input',...data});
    sourceUploader.observe(data);
  };
  player.connect(context.destination);
  await context.resume();
  workerLifecycle.assertHealthy();
  let clockSampler,receiveStats,closed=false;
  const receipts=new PlaybackReceiptSender({sessionId,token,
    onFailure:reason=>bridge.fail(reason)});
  bridge=new RTPCandidatePlayback({worker,player,evidence,
    onClockSample:data=>clockSampler?.observe(data),send(message){
    if(message.event==='candidate_failed') { onFailure(message.reason,{...message.details,...receiveStats?.read(),client_build:new URL(import.meta.url).pathname.split('/').pop()});return; }
    if(message.event!=='receipt') return;
    if(message.receipt.event==='task_started') clockSampler?.pulse();
    void receipts.enqueue(playbackReceipt(message.receipt));
  }});
  clockSampler=new RenderClockSampler({sessionId,token,clockId:bridge.clock,
    sampleRate:context.sampleRate,port:player.port,
    onError:reason=>evidence({side:'clock',event:'clock_sample_unavailable',reason})});
  const control=message=>{
    if(closed) return;
    if(message.event==='input_source_epoch') {sourceUploader.setEpoch(message.connection_id);return;}
    clockSampler.start();bridge.control(message);
  };
  bindRTCTransform(transport,worker,globalThis.RTCRtpScriptTransform,inputWorker);
  const original=transport.createPeerConnection.bind(transport);
  transport.createPeerConnection=()=>{
    if(closed) throw new Error('Playback is closed');
    const peer=original();
    receiveStats?.close();receiveStats=observeReceiveStats(peer);
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
  return {async close(){if(closed)return;closed=true;receiveStats?.close();workerLifecycle.close();receipts.close();clockSampler.close();sourceUploader.close();worker.terminate();inputWorker.terminate();player.disconnect();await context.close();}};
  } catch(error) {
    workerLifecycle?.close();
    sourceUploader?.close();
    worker?.terminate();
    inputWorker?.terminate();
    player?.disconnect();
    await context.close().catch(()=>{});
    throw error;
  }
}
