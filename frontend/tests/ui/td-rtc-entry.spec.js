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

test("formal mobile route records task-specific RTP renderer receipts through authenticated API",async({page,request,baseURL},info)=>{
  test.setTimeout(process.env.VOICE_AGENT_TD_RTC_SOURCE_DIAGNOSTIC==='1'?15000:45000);
  expect(["localhost","127.0.0.1"]).toContain(new URL(baseURL).hostname);
  expect((await request.get("/health")).headers()["x-voiceagent-test-fixture"]).toBe("td-local-offline");
  if(process.env.VOICE_AGENT_TD_ASSERT_RTP_INPUT==='1') {
    const initial=await request.get('/api/_test/td-rtp-input');
    expect(initial.headers()['x-voiceagent-test-fixture']).toBe('td-local-offline');
    expect((await initial.json()).proofs).toHaveLength(0);
  }
  const response=await request.post("/api/bots",{headers:{Origin:baseURL},data:{
    name:`Local RTC cancellation ${Date.now()}`,asr_provider:"deepgram",asr_model:"flux-general-en",
    tts_provider:"deepgram_flux",tts_voice:"flux-alexis-en",llm_provider:"openai",llm_base_url:"https://api.openai.com/v1",llm_model:"gpt-4.1-mini",
    system_prompt:"Local offline fixture only.",opening_script:"Local fixture opening.",turn_detection_source:"self_developed",
    td_config:{minimum_ms:600,maximum_ms:2500,final_wait_ms:200,alpha:.5,conflict_threshold:.8,
      vad:{confidence:.7,start_secs:.2,stop_secs:.2,min_volume:.6},
      jev:{endpoint:"https://api.typesafe.ai/v1/systemone",model:"jev-latest",timeout_seconds:2,noul_instructions:"Yield?",choice_instructions:"State?",options:[{id:"complete",meaning:"Done",wait_ms:700},{id:"incomplete",meaning:"Continue",wait_ms:1500}]}},
    save_asr_key:true,save_tts_key:true,save_llm_key:true,save_jev_key:true,
    asr_api_key:"local-inert-asr-000000",tts_api_key:"local-inert-tts-000000",llm_api_key:"local-inert-llm-000000",jev_api_key:"local-inert-jev-000000",
  }});
  expect(response.status(),await response.text()).toBe(201);
  const bot=await response.json();
  const published=await request.post(`/api/bots/${bot.id}/publish`,{headers:{Origin:baseURL},data:{public_title:bot.name}});
  expect(published.status(),await published.text()).toBe(200);
  const share=await published.json();
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
  const receiptFailure=process.env.VOICE_AGENT_TD_RTC_RECEIPT_HANG==='1';
  let heldReceipt,releaseReceipt,releaseTelemetry,startedRequests=0;
  if(receiptFailure) {
    await page.route('**/playback-events',async route=>{
      const receipt=route.request().postDataJSON();
      if(receipt.event==='task_started' && ++startedRequests===2) {
        const response=await route.fetch();
        expect(response.status()).toBe(204);
        heldReceipt=receipt;
        await new Promise(resolve=>{releaseReceipt=resolve;});
        await route.fulfill({response}).catch(()=>{});
      } else await route.continue();
    });
    await page.route('**/events',async route=>{
      if(route.request().postDataJSON()?.event==='mobile_call_error') {
        await new Promise(resolve=>{releaseTelemetry=resolve;});
        await route.abort().catch(()=>{});
      } else await route.continue();
    });
  }
  page.on("response",async response=>{
    if(response.url().endsWith("/playback-events")) receipts.push({status:response.status(),receipt:response.request().postDataJSON()});
  });
  page.on("response",async r=>{if(r.url().endsWith(`/api/public/demos/${publicId}/sessions`) && r.status()===201) session=await r.json();});
  await page.goto(`/demo/${publicId}`);
  await page.locator("#start-call").click();
  await expect.poll(()=>Boolean(session),{timeout:10000}).toBe(true);
  await expect(page.locator('[data-screen="live"]')).toBeVisible({timeout:20000});
  if(receiptFailure) {
    try {
      await expect.poll(()=>Boolean(heldReceipt),{timeout:10000}).toBe(true);
      await expect(page.locator('[data-screen="error"]')).toHaveAttribute('aria-hidden','false',{timeout:7000});
      await expect(page.locator('audio')).toHaveJSProperty('paused',true);
      await expect(page.locator('audio')).toHaveJSProperty('srcObject',null);
      await expect.poll(async()=>{
        const history=await (await request.get(`/api/history/${session.session_id}`)).json();
        return Boolean(history.ended_at);
      },{timeout:10000}).toBe(true);
      const history=await (await request.get(`/api/history/${session.session_id}`)).json();
      const renderer=history.td_events.filter(event=>event.event==='playback_renderer_receipt');
      expect(renderer.some(event=>event.playback_id===heldReceipt.playback_id && event.renderer_event==='task_started')).toBe(true);
      expect(history.td_events.some(event=>event.event==='response_restart')).toBe(true);
      expect(Boolean(releaseTelemetry)).toBe(true);
      expect(renderer.some(event=>event.playback_id===heldReceipt.playback_id && event.renderer_event==='task_stopped')).toBe(false);
      expect(renderer.some(event=>event.response_id==='1:2' && event.renderer_event==='task_started')).toBe(false);
      writeFileSync(`${evidence}/receipt-response-lost-history.json`,JSON.stringify({
        heldReceipt,telemetryAlsoHeld:Boolean(releaseTelemetry),history},null,2));
    } finally {releaseReceipt?.();releaseTelemetry?.();}
    return;
  }
  if(process.env.VOICE_AGENT_TD_ASSERT_RTP_INPUT==='1') {
    await expect.poll(async()=> (await (await request.get('/api/_test/td-rtp-input')).json())
      .proofs.length,{timeout:2000}).toBeGreaterThan(0);
    const {proofs}=await (await request.get('/api/_test/td-rtp-input')).json();
    for(const proof of proofs) {
      expect(proof.sample_rate).toBe(16000);expect(proof.source_rate).toBe(48000);
      expect(proof.processed_end-proof.processed_start).toBe(proof.samples*3);
      expect(proof.packets[0].segment_start).toBe(proof.processed_start);
      expect(proof.packets.at(-1).segment_end).toBe(proof.processed_end);
      for(const packet of proof.packets)expect(packet.payload_sha256).toMatch(/^[a-f0-9]{64}$/);
    }
    writeFileSync(`${evidence}/native-rtp-input-proof.json`,JSON.stringify({
      evidenceLevel:'local-real',boundary:'server RTP/decoder/resampler only; browser capture clock unproven',proofs},null,2));
    if(process.env.VOICE_AGENT_TD_ASSERT_RTC_CAPTURE==='1') {
      await expect.poll(()=>page.evaluate(()=>window.__rtcWorkerEvents.some(event=>
        event.event==='input_capture_packet' || event.event==='input_capture_unavailable')),
        {timeout:2000}).toBe(true);
      const observed=await page.evaluate(()=>window.__rtcWorkerEvents.filter(event=>
        event.event==='input_capture_packet' || event.event==='input_capture_unavailable'));
      writeFileSync(`${evidence}/browser-capture-observation.json`,JSON.stringify({observed,proofs},null,2));
      const missing=observed.find(event=>event.event==='input_capture_unavailable');
      expect(missing,missing?.reason || 'native capture metadata required').toBeUndefined();
      const joined=proofs.flatMap(proof=>proof.packets.map(packet=>{
        const observation=observed.find(event=>event.record?.ssrc===packet.ssrc
          && event.record?.rtp_timestamp===packet.rtp_timestamp
          && event.record?.payload_sha256===packet.payload_sha256);
        return observation?{packet,record:observation.record}:null;
      })).filter(Boolean);
      expect(joined.length,'sender metadata must match actual received codec payload').toBeGreaterThan(0);
      writeFileSync(`${evidence}/joined-browser-native-source.json`,JSON.stringify({
        evidenceLevel:'local-real',joined,
        boundary:'reported browser captureTime and actual RTP/decoder/PCM join; server clock anchors not yet joined'},null,2));
    }
  }
  await expect.poll(()=>receipts.filter(item=>item.status===204 && item.receipt.event==='task_started' && item.receipt.rendered_samples>0).length,{timeout:15000}).toBeGreaterThanOrEqual(3);
  await expect.poll(()=>receipts.filter(item=>item.status===204 && item.receipt.event==='task_stopped' && item.receipt.rendered_samples>0).length,{timeout:10000}).toBeGreaterThan(0);
  await expect.poll(()=>receipts.filter(item=>item.status===204 && item.receipt.event==='task_finished').length,{timeout:10000}).toBeGreaterThanOrEqual(2);
  await expect(page.locator('[data-screen="error"]')).toHaveAttribute("aria-hidden","true");
  await expect(page.locator('[data-screen="live"]')).toHaveClass(/active/);
  await expect(page.locator("audio")).toHaveJSProperty("muted",true);
  if(process.env.VOICE_AGENT_TD_RTC_SOURCE_DIAGNOSTIC==='1') {
    const response=await request.get('/api/_test/td-source-diagnostic');
    expect(response.headers()['x-voiceagent-test-fixture']).toBe('td-local-offline');
    const diagnostic=await response.json();
    expect(diagnostic.snapshots.length).toBeGreaterThan(0);
    writeFileSync(`${evidence}/source-join-diagnostic.json`,JSON.stringify(diagnostic,null,2));
    await page.locator('#end').click();
    await expect(page.locator('audio')).toHaveJSProperty('srcObject',null);
    return;
  }
  const manifests=await page.evaluate(()=>window.__rtcManifests);
  for(const item of receipts.filter(item=>item.receipt.event==='task_finished')) {
    expect(item.status).toBe(204);
    expect(item.receipt.rendered_samples).toBe(manifests.find(m=>m.playback_id===item.receipt.playback_id)?.expected_samples);
  }
  if(process.env.VOICE_AGENT_TD_RENDER_CLOCK_PROBE==='1') {
    await expect.poll(async()=>{
      const result=await request.get(`/api/sessions/${session.session_id}/metrics`,{
        headers:{Authorization:`Bearer ${decodeURIComponent(session.connection_url.split('/').at(-1))}`}});
      expect(result.status()).toBe(200);
      return (await result.json()).metrics?.some(metric=>metric.timing_ranges?.playback);
    },{timeout:5000}).toBe(true);
  }
  if(process.env.VOICE_AGENT_TD_RTC_E2E==='1') {
    await expect.poll(async()=>{
      // History is persisted at call end; live timing belongs to the authenticated metrics API.
      const result=await request.get(`/api/sessions/${session.session_id}/metrics`,{
        headers:{Authorization:`Bearer ${decodeURIComponent(session.connection_url.split('/').at(-1))}`}});
      expect(result.status()).toBe(200);
      return (await result.json()).metrics?.filter(metric=>metric.timing_ranges?.e2e).length;
    },{timeout:5000}).toBeGreaterThan(0);
  }
  writeFileSync(`${evidence}/formal-authenticated-receipts.json`,JSON.stringify({receipts,manifests},null,2));
  await page.locator("#end").click();
  await expect(page.locator("audio")).toHaveJSProperty("paused",true);
  await expect(page.locator("audio")).toHaveJSProperty("srcObject",null);
  await expect.poll(async()=>{
    const history=await (await request.get(`/api/history/${session.session_id}`)).json();
    return history.td_events?.filter(event=>event.event==="response_restart").length;
  },{timeout:15000}).toBe(1);
  const history=await (await request.get(`/api/history/${session.session_id}`)).json();
  if(process.env.VOICE_AGENT_TD_RENDER_CLOCK_PROBE==='1') {
    const ranges=history.td_events.filter(event=>event.event==='playback_timing_bounds');
    expect(ranges.length).toBeGreaterThan(0);
    for(const event of ranges) {
      expect(event.playback_range.lower_ms).toBeGreaterThanOrEqual(0);
      expect(event.playback_range.upper_ms).toBeGreaterThanOrEqual(event.playback_range.lower_ms);
      expect(event.anchors.map(anchor=>anchor.sample_id)).toEqual(event.playback_range.anchor_ids);
      const hasSourceRange=history.td_events.some(source=>source.event==='e2e_timing_bounds'
        && source.playback_id===event.playback_id);
      expect(event.e2e_missing_reason).toBe(hasSourceRange?null:'source_end_clock_unavailable');
    }
  }
  if(process.env.VOICE_AGENT_TD_RTC_E2E==='1') {
    const ranges=history.td_events.filter(event=>event.event==='e2e_timing_bounds');
    expect(ranges.map(event=>event.response_id).sort()).toEqual(['1:1','1:2']);
    for(const event of ranges) {
      expect(event.e2e_range.lower_ms).toBeGreaterThanOrEqual(0);
      expect(event.e2e_range.upper_ms).toBeGreaterThanOrEqual(event.e2e_range.lower_ms);
      expect(event.source_coordinates.coordinate_kind).toBe('browser_reported_rtp_capture_time');
      expect(event.source_anchors).toHaveLength(2);expect(event.render_anchors).toHaveLength(2);
      expect(event.source_coordinates.mapping_spans.length).toBeGreaterThan(0);
      const sourceIds=new Set(event.source_anchors.map(anchor=>anchor.render_clock_id));
      for(const span of event.source_coordinates.mapping_spans) {
        expect(sourceIds.has(span.capture_clock_id)).toBe(true);
        expect(span.payload_sha256).toMatch(/^[a-f0-9]{64}$/);
      }
    }
    expect(history.metrics.some(metric=>metric.timing_ranges?.e2e)).toBe(true);
  }
  writeFileSync(`${evidence}/formal-final-history.json`,JSON.stringify(history,null,2));
  const stopped=receipts.find(item=>item.receipt.event==='task_stopped' && item.receipt.rendered_samples>0)?.receipt;
  const restarted=receipts.filter(item=>item.receipt.event==='task_started').at(-1)?.receipt;
  expect(stopped.render_clock_id).toBe(restarted.render_clock_id);
  expect(restarted.render_frame).toBeGreaterThanOrEqual(stopped.render_frame);
});
