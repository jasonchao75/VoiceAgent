import {test,expect} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-rtp-repair-gate';
mkdirSync(evidence,{recursive:true});
test.use({launchOptions:{args:['--autoplay-policy=no-user-gesture-required']}});

test('fixed RTP decode job preserves actual provenance beyond the saved failure boundary',async({page})=>{
  test.skip(process.env.VOICE_AGENT_TD_RTP_REPAIR_CONFIRMATION!=='1','New explicit repair confirmation only');
  await page.route('**/api/**',route=>route.fulfill({status:503,body:'{}'}));
  await page.goto('/');
  const result=await page.evaluate(async()=>{
    const pc=new RTCPeerConnection({iceServers:[]}),events=[];
    const worker=new Worker('/src/td-rtp-candidate-worker.js',{type:'module'});
    const channel=pc.createDataChannel('task-ranges');
    channel.onopen=()=>channel.send('ready');
    channel.onmessage=({data})=>worker.postMessage(JSON.parse(data));
    let finish;
    const done=new Promise(resolve=>{finish=resolve;});
    worker.onmessage=({data})=>{
      events.push({...data,buffer:undefined});
      if(data.event==='mapping_failed') {pc.close();worker.terminate();finish('failed');}
      if(data.event==='decoded' && data.source_start>=42888) finish('bounded_coverage');
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
      const outcome=await Promise.race([done,new Promise(resolve=>{timer=setTimeout(()=>resolve('deadline'),1500);})]);
      return {outcome,events,connections:1,source_sample_cap:24000,source_sample_rate:24000};
    } finally {
      clearTimeout(timer);await pc.close();worker.terminate();sink.remove();
      await fetch('http://127.0.0.1:8791/close',{method:'POST'});
    }
  });
  writeFileSync(`${evidence}/repair-gate.json`,JSON.stringify(result,null,2));
  expect(result.outcome).toBe('bounded_coverage');
  expect(result.events.filter(e=>e.event==='mapping_failed')).toEqual([]);
  expect(result.events.some(e=>e.event==='decoded' && e.source_start===12168)).toBe(true);
  const totals={};
  for(const event of result.events.filter(e=>e.event==='task_pcm')) totals[event.task]=(totals[event.task]||0)+event.end-event.start;
  expect(totals).toEqual({'partial-A':1440,'final-B':1440});
});
