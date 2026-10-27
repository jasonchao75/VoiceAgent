import {test, expect} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
const evidence = process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-rtp-candidate';
mkdirSync(evidence,{recursive:true});
test.use({launchOptions:{args:['--autoplay-policy=no-user-gesture-required']}});

for (const corrupt of [false,true]) test(`D-064 actual RTP mixed-task mapping ${corrupt ? 'rejects forged identity' : 'reaches existing Worklet'}`, async ({page}) => {
  test.skip(process.env.VOICE_AGENT_TD_RTP_CANDIDATE !== '1','Finite isolated candidate only');
  await page.route('**/api/**',route=>route.fulfill({status:503,body:'{}'}));
  await page.goto('/');
  const result = await page.evaluate(async corrupt => {
    const events = [], receipts = [], totals = {}, failures = [];
    const pc = new RTCPeerConnection({iceServers:[]});
    const context = new AudioContext({sampleRate:48000});
    const worker = new Worker('/src/td-rtp-candidate-worker.js',{type:'module'});
    await context.audioWorklet.addModule('/src/td-audio-worklet.js');
    const player = new AudioWorkletNode(context,'stream_processor');
    player.connect(context.destination);
    player.port.onmessage = ({data}) => receipts.push(data);
    const channel = pc.createDataChannel('task-ranges');
    channel.onopen = () => channel.send('ready');
    channel.onmessage = ({data}) => {
      const message=JSON.parse(data);
      if(corrupt) message.mapping.payload_sha256='0'.repeat(64);
      worker.postMessage(message);
    };
    worker.onmessage = ({data}) => {
      if (data.event === 'task_pcm') {
        events.push({...data,buffer:undefined,samples:data.buffer.length});
        totals[data.task] = (totals[data.task] || 0)+data.buffer.length;
        player.port.postMessage({event:'write',trackId:data.task,buffer:data.buffer});
        if (totals[data.task] === 1440) player.port.postMessage({event:'task_end',playback_id:data.task});
      } else {
        events.push(data);
        if(data.event==='mapping_failed') player.port.postMessage({event:'interrupt',requestId:'mapping-failed'});
      }
    };
    worker.onerror = event => failures.push(event.message);
    const sink = document.createElement('audio');
    sink.muted = true; sink.autoplay = true; sink.hidden = true;
    document.body.append(sink);
    pc.ontrack = ({track}) => {
      sink.srcObject = new MediaStream([track]);
      void sink.play().catch(error=>failures.push(error.message));
    };
    const transceiver = pc.addTransceiver('audio',{direction:'recvonly'});
    transceiver.receiver.transform = new RTCRtpScriptTransform(worker);
    try {
      await context.resume();
      await pc.setLocalDescription(await pc.createOffer());
      if (pc.iceGatheringState !== 'complete') await new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>reject(new Error('ICE deadline')),3000);
        pc.onicegatheringstatechange=()=>{if(pc.iceGatheringState==='complete'){clearTimeout(timer);resolve();}};
      });
      const response = await fetch('http://127.0.0.1:8791/offer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pc.localDescription)});
      await pc.setRemoteDescription(await response.json());
      const deadline = performance.now()+5000;
      while (performance.now()<deadline && !events.some(e=>e.event==='mapping_failed') && receipts.filter(e=>e.event==='task_finished').length<2) await new Promise(resolve=>setTimeout(resolve,20));
      return {events,receipts,totals,failures,connection:pc.connectionState,sample_rate:context.sampleRate};
    } finally {
      await pc.close();worker.terminate();player.disconnect();sink.remove();await context.close();
      await fetch('http://127.0.0.1:8791/close',{method:'POST'});
    }
  },corrupt);
  writeFileSync(`${evidence}/browser-${corrupt ? 'rejected' : 'mapping'}.json`,JSON.stringify(result,null,2));
  expect(result.failures).toEqual([]);
  if(corrupt) {
    expect(result.events.filter(e=>e.event==='mapping_failed').map(e=>e.reason)).toEqual(['payload_identity_mismatch']);
    expect(result.receipts.filter(e=>e.event==='task_started' || e.event==='task_finished')).toEqual([]);
    expect(result.totals).toEqual({});
    return;
  }
  expect(result.events.filter(e=>e.event==='mapping_failed')).toEqual([]);
  expect(result.totals).toEqual({'partial-A':1440,'final-B':1440});
  expect(result.events.some(e=>e.event==='packet_bound' && new Set(e.spans.map(s=>s.task).filter(Boolean)).size===2)).toBe(true);
  expect(result.receipts.filter(e=>e.event==='task_finished').map(e=>({task:e.playback_id,samples:e.rendered_samples}))).toEqual([
    {task:'partial-A',samples:1440},{task:'final-B',samples:1440},
  ]);
});
