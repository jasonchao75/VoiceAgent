import {test,expect} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-rtp-coordinate';
mkdirSync(evidence,{recursive:true});
test.use({launchOptions:{args:['--autoplay-policy=no-user-gesture-required']}});

test('D-066 one bounded local decoder coordinate diagnostic',async({page})=>{
  test.skip(process.env.VOICE_AGENT_TD_RTP_DIAGNOSTIC!=='D-066','Single explicit local diagnostic grant');
  await page.route('**/api/**',route=>route.fulfill({status:503,body:'{}'}));
  await page.goto('/');
  const result=await page.evaluate(async()=>{
    const pc=new RTCPeerConnection({iceServers:[]}), events=[];
    const worker=new Worker('/src/td-rtp-candidate-worker.js',{type:'module'});
    const channel=pc.createDataChannel('task-ranges');
    channel.onopen=()=>channel.send('ready');
    channel.onmessage=({data})=>worker.postMessage(JSON.parse(data));
    let finish;
    const stopped=new Promise(resolve=>{finish=resolve;});
    worker.onmessage=({data})=>{
      events.push({...data,buffer:undefined});
      if(data.event==='mapping_failed') {
        // Close immediately, not after an assertion or another scenario.
        pc.close();worker.terminate();finish('first_mismatch');
      }
    };
    worker.onerror=()=>{pc.close();worker.terminate();finish('worker_error');};
    const sink=document.createElement('audio');sink.muted=true;sink.autoplay=true;
    document.body.append(sink);
    pc.ontrack=({track})=>{sink.srcObject=new MediaStream([track]);void sink.play().catch(()=>finish('sink_error'));};
    pc.addTransceiver('audio',{direction:'recvonly'}).receiver.transform=new RTCRtpScriptTransform(worker);
    let timer;
    try {
      await pc.setLocalDescription(await pc.createOffer());
      if(pc.iceGatheringState!=='complete') await new Promise((resolve,reject)=>{
        const timeout=setTimeout(()=>reject(new Error('ICE deadline')),3000);
        pc.onicegatheringstatechange=()=>{if(pc.iceGatheringState==='complete'){clearTimeout(timeout);resolve();}};
      });
      const response=await fetch('http://127.0.0.1:8791/offer?candidate_diagnostic=true',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pc.localDescription)});
      if(!response.ok) throw new Error('Local offer failed');
      await pc.setRemoteDescription(await response.json());
      const outcome=await Promise.race([stopped,new Promise(resolve=>{timer=setTimeout(()=>resolve('bounded_deadline'),1500);})]);
      return {outcome,events,connections:1,server_source_sample_cap:24000,source_sample_rate:24000,
        audio_path:'native Opus/RTP only; muted native sink; no task playback or provider'};
    } finally {
      clearTimeout(timer);await pc.close();worker.terminate();sink.remove();
      await fetch('http://127.0.0.1:8791/close',{method:'POST'});
    }
  });
  writeFileSync(`${evidence}/decoder-diagnostic.json`,JSON.stringify(result,null,2));
  expect(result.outcome).toBe('first_mismatch');
  const failures=result.events.filter(e=>e.event==='mapping_failed');
  expect(failures).toHaveLength(1);
  expect(failures[0].reason).toBe('decode_coordinate_unproven');
  expect(failures[0].details.observed).toMatchObject({sample_rate:48000,samples:960});
  expect(failures[0].details.pending_timestamps.length).toBeGreaterThan(0);
});
