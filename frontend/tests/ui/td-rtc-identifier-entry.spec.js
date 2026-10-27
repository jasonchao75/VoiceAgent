import {test,expect} from "@playwright/test";
import {mkdirSync,writeFileSync} from "node:fs";
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || "../test-results/td-webrtc-evidence";
mkdirSync(evidence,{recursive:true});
const enabled=process.env.VOICE_AGENT_TD_LOCAL_RUNTIME==="1";
test.skip(!enabled,"Requires the loopback-only disposable TD application");
test.use({permissions:["microphone"],launchOptions:{args:["--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream","--autoplay-policy=no-user-gesture-required"]}});
test.afterEach(async({page},info)=>{
  const diagnostics=await page.evaluate(async()=>({workerEvents:window.__rtcWorkerEvents,samples:window.__rtcSamples,tracks:window.__rtcTracks,
    stats:await Promise.all((window.__rtcConnections||[]).map(async pc=>[...(await pc.getStats()).values()]
      .filter(s=>s.type==="inbound-rtp" && s.kind==="audio")))})).catch(()=>({closed:true}));
  writeFileSync(`${evidence}/rtc-probe-diagnostics.${info.project.name}.json`,JSON.stringify(diagnostics,null,2));
});

test("formal mobile RTC identifier arbitration uses actual renderer receipts",async({page,request,baseURL},info)=>{
  test.setTimeout(45000);
  expect(["localhost","127.0.0.1"]).toContain(new URL(baseURL).hostname);
  expect((await request.get("/health")).headers()["x-voiceagent-test-fixture"]).toBe("td-local-offline");
  const response=await request.post("/api/bots",{headers:{Origin:baseURL},data:{
    name:`Local RTC cancellation ${Date.now()}`,asr_provider:"deepgram",asr_model:"flux-general-en",
    tts_provider:"deepgram_flux",tts_voice:"flux-alexis-en",llm_provider:"openai",llm_base_url:"https://api.openai.com/v1",llm_model:"gpt-4.1-mini",
    system_prompt:"Local offline fixture only.",opening_script:"Please say your identifier.",turn_detection_source:"self_developed",
    td_config:{priority_rule:{enabled:true,keywords:['identifier'],
      vocabulary:[{value:'1',aliases:['one']},{value:'2',aliases:['two']}],
      wpm_threshold:90,pause_ms:100,unit_gap_ms:50,
      collection:{target_length:4,timeout_ms:15000,overflow_pause_ms:100,incomplete_text:'Please complete the identifier.',overflow_text:'Please check the identifier.'}},minimum_ms:600,maximum_ms:2500,final_wait_ms:200,alpha:.5,conflict_threshold:.8,
      vad:{confidence:.7,start_secs:.2,stop_secs:.2,min_volume:.6},
      jev:{endpoint:"https://api.typesafe.ai/v1/systemone",model:"jev-latest",timeout_seconds:2,noul_instructions:"Yield?",choice_instructions:"State?",options:[{id:"complete",meaning:"Done",wait_ms:700},{id:"incomplete",meaning:"Continue",wait_ms:1500}]}},
    save_asr_key:true,save_tts_key:true,save_llm_key:true,save_jev_key:true,
    asr_api_key:"local-inert-asr-000000",tts_api_key:"local-inert-tts-000000",llm_api_key:"local-inert-llm-000000",jev_api_key:"local-inert-jev-000000",
  }});
  expect(response.status(),await response.text()).toBe(201);
  const bot=await response.json();
  const repair=process.env.VOICE_AGENT_TD_PUBLIC_CACHE_REPAIR==='1';
  const failure=process.env.VOICE_AGENT_TD_PUBLIC_CACHE_FAILURE==='1';
  if(repair || failure)expect((await request.get('/health')).headers()['x-voiceagent-test-scenario']).toBe(
    failure?'identifier_cache_failure':'identifier_cache_repair');
  const cache=await (await request.get(`/api/bots/${bot.id}/echo-audio`)).json();
  const generated=await request.post(`/api/bots/${bot.id}/echo-audio/generate`,{headers:{Origin:baseURL},data:{expected_fingerprint:cache.fingerprint}});
  expect(generated.status(),await generated.text()).toBe(200);
  const published=await request.post(`/api/bots/${bot.id}/publish`,{headers:{Origin:baseURL},data:{public_title:bot.name}});
  expect(published.status(),await published.text()).toBe(200);
  const share=await published.json();
  const generatedAssets=await generated.json();
  if(repair || failure) {
    const draft={...bot,tts_speed:1.2,save_asr_key:true,save_tts_key:true,save_llm_key:true,save_jev_key:true};
    for(const key of ['id','created_at','updated_at','has_saved_keys','has_asr_key','has_tts_key','has_llm_key','has_jev_key','asr_account_catalog'])delete draft[key];
    const changed=await request.put(`/api/bots/${bot.id}`,{headers:{Origin:baseURL},data:draft});
    expect(changed.status(),await changed.text()).toBe(200);
    const draftAssets=await (await request.get(`/api/bots/${bot.id}/echo-audio`)).json();
    expect(draftAssets.fingerprint).not.toBe(cache.fingerprint);
    expect((await (await request.get(`/api/bots/${bot.id}/share`)).json()).unpublished_changes).toBe(true);
  }
  const publicId=share.public_id;
  expect(publicId).toBeTruthy();
  // Vite serves the same production demo document at its public route; APIs stay real.
  const document=await request.get("/demo.html");
  await page.route(`**/demo/${publicId}`,route=>route.fulfill({response:document}));
  await page.addInitScript(()=>{
    window.__rtcWorkerEvents=[];
    const NativeWorker=window.Worker;
    window.Worker=class extends NativeWorker {
      constructor(...args){super(...args);this.addEventListener("message",({data})=>{
        if(data.event!=="task_pcm") window.__rtcWorkerEvents.push(data);
      });}
    };
    window.__rtcManifests=[];
    window.__rtcSamples=[];
    window.__rtcTracks=[];
    window.__rtcConnections=[];
    const Native=window.RTCPeerConnection;
    window.RTCPeerConnection=class extends Native {
      constructor(...args){
        super(...args);
        window.__rtcConnections.push(this);
        const createChannel=this.createDataChannel.bind(this);
        this.createDataChannel=(...args)=>{
          const channel=createChannel(...args);
          channel.addEventListener('message',({data})=>{
            let message;try{message=JSON.parse(data);}catch{return;}
            if(message.event==='task_end') window.__rtcManifests.push(message);
          });
          return channel;
        };
      }
    };
  });
  let session;
  const receipts=[];
  page.on("response",async response=>{
    if(response.url().endsWith("/playback-events")) receipts.push({status:response.status(),receipt:response.request().postDataJSON()});
  });
  page.on("response",async r=>{if(r.url().endsWith(`/api/public/demos/${publicId}/sessions`) && r.status()===201) session=await r.json();});
  await page.goto(`/demo/${publicId}`);
  await page.locator("#start-call").click();
  await expect.poll(()=>Boolean(session),{timeout:10000}).toBe(true);
  expect(session.ice_servers).toEqual([]);
  await expect(page.locator('[data-screen="live"]')).toBeVisible({timeout:20000});
  if(!failure)await expect.poll(()=>receipts.filter(item=>item.status===204 && item.receipt.event==='task_stopped' && item.receipt.rendered_samples>0).length,{timeout:25000}).toBeGreaterThan(0);
  await expect.poll(()=>receipts.filter(item=>item.status===204 && item.receipt.event==='task_finished').length,{timeout:25000}).toBeGreaterThanOrEqual(failure?4:2);
  await expect(page.locator('[data-screen="error"]')).toHaveAttribute("aria-hidden","true");
  await expect(page.locator('[data-screen="live"]')).toHaveClass(/active/);
  await expect(page.locator("audio")).toHaveJSProperty("muted",true);
  const manifests=await page.evaluate(()=>window.__rtcManifests);
  for(const item of receipts.filter(item=>item.receipt.event==='task_finished')) {
    expect(item.status).toBe(204);
    expect(item.receipt.rendered_samples).toBe(manifests.find(m=>m.playback_id===item.receipt.playback_id)?.expected_samples);
  }
  writeFileSync(`${evidence}/formal-identifier-receipts.json`,JSON.stringify({receipts,manifests},null,2));
  await page.locator("#end").click();
  await expect(page.locator("audio")).toHaveJSProperty("paused",true);
  await expect(page.locator("audio")).toHaveJSProperty("srcObject",null);
  let history;
  await expect.poll(async()=>{
    history=await (await request.get(`/api/history/${session.session_id}`)).json();
    return history.ended_at;
  },{timeout:15000}).toBeTruthy();
  writeFileSync(`${evidence}/formal-identifier-history.json`,JSON.stringify(history,null,2));
  const events=history.td_events;
  expect(events.filter(item=>item.event==='identifier_local_processed').map(item=>item.collected)).toEqual(['1','12']);
  expect(events.filter(item=>item.event==='identifier_tool_result' && item.operation==='clear')).toMatchObject([{status:'cleared',value:'',count:0}]);
  let stopped,old;
  if(!failure) {
  const echoes=events.filter(item=>item.event==='playback_task_prepared' && item.kind==='echo');
  expect(echoes.length).toBeGreaterThanOrEqual(2);
  old=echoes[0].playback_id;
  const start=receipts.find(item=>item.receipt.event==='task_started' && item.receipt.playback_id===old)?.receipt;
  stopped=receipts.find(item=>item.receipt.event==='task_stopped' && item.receipt.playback_id===old)?.receipt;
  expect(start.rendered_samples).toBeGreaterThan(0);
  expect(stopped.rendered_samples).toBeGreaterThan(0);
  expect(stopped.rendered_samples).toBeLessThan(480000);
  expect(start.render_clock_id).toBe(stopped.render_clock_id);
  expect(receipts.some(item=>item.receipt.event==='task_started' && item.receipt.playback_id===echoes[1].playback_id)).toBe(false);
  }
  expect(receipts.every(item=>item.status===204)).toBe(true);
  expect(events.filter(item=>item.event==='td_commit')).toHaveLength(2);
  expect(history.turns.some(item=>item.text.includes('The identifier was cleared.'))).toBe(true);
  if(failure) {
    const failed=events.filter(item=>item.event==='identifier_echo_resource_failed');
    expect(failed).toHaveLength(1);expect(failed[0].unit).toBe('1');
    expect(failed[0].fingerprint).toBe(cache.fingerprint);
    expect(failed[0].resource_version).toBe(generatedAssets.assets.find(item=>item.unit==='1').version);
    const failedId=failed[0].playback_id;
    expect(receipts.filter(item=>item.receipt.playback_id===failedId)).toHaveLength(0);
    expect(events.filter(item=>item.event==='identifier_echo_resource_ready' && item.playback_id===failedId)).toHaveLength(0);
    expect(events.filter(item=>item.event==='identifier_echo_job_failed' && item.playback_id===failedId)).toHaveLength(1);
    expect(events.filter(item=>item.event==='identifier_echo_synthesis_started' && item.playback_id===failedId)).toHaveLength(1);
    writeFileSync(`${evidence}/published-cache-failure.json`,JSON.stringify({evidenceLevel:'local-real',
      publishedFingerprint:cache.fingerprint,failed,failedTaskHasNoClientSuccess:true,
      collectionContinued:['1','12'],laterClearSucceeded:true,renderedOtherTasks:receipts.filter(item=>item.receipt.event==='task_finished').length,
      iceServers:session.ice_servers,providerCalls:'offline replacements only'},null,2));
  }
  if(repair) {
    const synthesis=events.filter(item=>item.event==='identifier_echo_synthesis_started');
    expect(synthesis).toHaveLength(1);expect(synthesis[0].unit).toBe('1');
    expect(synthesis[0].fingerprint).toBe(cache.fingerprint);
    const ready=events.filter(item=>item.event==='identifier_echo_resource_ready' && item.recovery_path===true);
    expect(ready).toHaveLength(1);
    expect(ready[0].fingerprint).toBe(cache.fingerprint);
    expect(ready[0].resource_version).toBe(generatedAssets.assets.find(item=>item.unit==='1').version);
    expect(events.filter(item=>item.event==='identifier_echo_resource_failed')).toHaveLength(0);
    writeFileSync(`${evidence}/published-cache-repair.json`,JSON.stringify({evidenceLevel:'local-real',
      publishedRevision:share.revision,publishedFingerprint:cache.fingerprint,repair:synthesis,ready,
      sourceVersion:generatedAssets.assets.find(item=>item.unit==='1').version,
      actualStopSamples:stopped.rendered_samples,oldTask:old,providerCalls:'offline replacements only'},null,2));
  }
});
