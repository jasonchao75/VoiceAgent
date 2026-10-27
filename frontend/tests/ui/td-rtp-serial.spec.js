import {test,expect} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-rtp-serial';
mkdirSync(evidence,{recursive:true});
test.describe.configure({mode:'serial'});
test.use({launchOptions:{args:['--autoplay-policy=no-user-gesture-required']}});

for(const scenario of ['final','identifier']) test(`D-064 RTP serial ${scenario} waits for actual stop`,async({page})=>{
  test.skip(process.env.VOICE_AGENT_TD_RTP_CANDIDATE!=='1','Finite candidate only');
  await page.route('**/api/**',route=>route.fulfill({status:503,body:'{}'}));
  await page.goto('/');
  const result=await page.evaluate(async scenario=>{
    const {RTPCandidatePlayback}=await import('/src/td-rtp-candidate-playback.js');
    const pc=new RTCPeerConnection({iceServers:[]});
    const context=new AudioContext({sampleRate:48000});
    await context.audioWorklet.addModule('/src/td-audio-worklet.js');
    const player=new AudioWorkletNode(context,'stream_processor');
    player.connect(context.destination);
    const worker=new Worker('/src/td-rtp-candidate-worker.js',{type:'module'});
    const events=[],errors=[];
    const channel=pc.createDataChannel('task-ranges');
    const bridge=new RTPCandidatePlayback({worker,player,
      send:message=>channel.send(JSON.stringify(message)),evidence:event=>events.push(event)});
    channel.onopen=()=>channel.send('ready');
    channel.onmessage=({data})=>bridge.control(JSON.parse(data));
    worker.onerror=event=>errors.push(event.message);
    const sink=document.createElement('audio');sink.muted=true;sink.autoplay=true;
    document.body.append(sink);
    pc.ontrack=({track})=>{sink.srcObject=new MediaStream([track]);void sink.play().catch(e=>errors.push(e.message));};
    pc.addTransceiver('audio',{direction:'recvonly'}).receiver.transform=new RTCRtpScriptTransform(worker);
    let server={};
    try {
      await context.resume();
      await pc.setLocalDescription(await pc.createOffer());
      if(pc.iceGatheringState!=='complete') await new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>reject(new Error('ICE deadline')),3000);
        pc.onicegatheringstatechange=()=>{if(pc.iceGatheringState==='complete'){clearTimeout(timer);resolve();}};
      });
      const response=await fetch(`http://127.0.0.1:8791/serial-offer/${scenario}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(pc.localDescription)});
      await pc.setRemoteDescription(await response.json());
      const deadline=performance.now()+6000;
      const target=scenario==='final'?'final-B':'question-Q';
      while(performance.now()<deadline) {
        await new Promise(resolve=>setTimeout(resolve,30));
        if(events.some(e=>e.event==='candidate_failed')) break;
        if(events.some(e=>e.side==='render' && e.event==='task_finished' && e.playback_id===target)) {
          server=await (await fetch('http://127.0.0.1:8791/serial-result',{method:'POST'})).json();
          if(server.tasks?.[target]?.status==='finished') break;
        }
      }
      if(!server.tasks) server=await (await fetch('http://127.0.0.1:8791/serial-result',{method:'POST'})).json();
      return {events,errors,server,connection:pc.connectionState};
    } finally {
      await pc.close();worker.terminate();player.disconnect();sink.remove();await context.close();
      await fetch('http://127.0.0.1:8791/close',{method:'POST'});
    }
  },scenario);
  writeFileSync(`${evidence}/serial-${scenario}.json`,JSON.stringify(result,null,2));
  expect(result.errors).toEqual([]);
  expect(result.server.job_errors).toEqual([]);
  expect(result.events.filter(e=>e.event==='candidate_failed')).toEqual([]);
  const receipts=result.server.receipts;
  expect(receipts.every(e=>e.accepted)).toBe(true);
  const oldStarted=receipts.find(e=>e.event==='task_started');
  const stopped=receipts.find(e=>e.event==='task_stopped' && e.playback_id===oldStarted?.playback_id);
  const target=scenario==='final'?'final-B':'question-Q';
  const nextStarted=receipts.find(e=>e.event==='task_started' && e.playback_id===target);
  const finished=receipts.find(e=>e.event==='task_finished' && e.playback_id===target);
  expect(stopped?.rendered_samples).toBeGreaterThan(0);
  expect(nextStarted?.render_frame).toBeGreaterThanOrEqual(stopped?.render_frame);
  expect(finished?.rendered_samples).toBe(14880);
  expect(result.server.tasks[target].status).toBe('finished');
  const transitions=result.server.td_events;
  const stopIndex=transitions.findIndex(e=>e.event==='playback_renderer_receipt' && e.renderer_event==='task_stopped');
  expect(transitions.findIndex(e=>e.event==='playback_dispatched' && e.playback_id===target)).toBeGreaterThan(stopIndex);
  if(scenario==='final') {
    expect(result.server.user_submissions).toBe(1);
    expect(stopped.rendered_samples).toBeLessThan(14880);
    expect(result.server.actions.find(e=>e.event==='final_replaced')).toMatchObject({duplicate_restart:false,tool_replayed:false});
  } else {
    expect(result.server.actions.find(e=>e.event==='continuation_and_question')).toMatchObject({active_kind:'echo',active_status:'playing',question_status:'queued',stop_requests:[]});
    expect(result.server.actions.find(e=>e.event==='clear_result')).toMatchObject({generation:1,result:{status:'cleared'}});
  }
});
