import { test, expect } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || "../test-results/td-runtime-evidence";
mkdirSync(evidence,{recursive:true});

const enabled=process.env.VOICE_AGENT_TD_LOCAL_RUNTIME==="1";
test.skip(!enabled,"Requires the explicit loopback-only TD fixture app and disposable database");
test.use({permissions:["microphone"],launchOptions:{args:["--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream"]}});
test.beforeEach(async({page},info)=>{
  if(!info.title.includes("defaults to Chinese")) await page.addInitScript(()=>localStorage.setItem("voiceagent-td-locale","en"));
});

const td={minimum_ms:600,maximum_ms:2500,final_wait_ms:200,alpha:.5,conflict_threshold:.8,
  vad:{confidence:.7,start_secs:.2,stop_secs:.2,min_volume:.6},
  jev:{endpoint:"https://api.typesafe.ai/v1/systemone",model:"jev-latest",timeout_seconds:2,
    noul_instructions:"Has the user yielded the floor?",choice_instructions:"Classify the utterance.",
    options:[{id:"complete",meaning:"Complete",wait_ms:700},{id:"incomplete",meaning:"Incomplete",wait_ms:1500}]},
};
const botPayload={name:"Local TD network fixture",asr_provider:"deepgram",asr_model:"flux-general-en",
  tts_provider:"deepgram_flux",tts_voice:"flux-alexis-en",llm_provider:"openai",llm_base_url:"https://api.openai.com/v1",llm_model:"gpt-4.1-mini",
  system_prompt:"Local offline fixture only.",opening_script:"Local fixture opening.",
  turn_detection_source:"self_developed",td_config:td,
  save_asr_key:true,save_tts_key:true,save_llm_key:true,save_jev_key:true,
  asr_api_key:"local-inert-asr-000000",tts_api_key:"local-inert-tts-000000",llm_api_key:"local-inert-llm-000000",jev_api_key:"local-inert-jev-000000"};

async function verifyFixture(request,baseURL) {
  expect(["localhost","127.0.0.1"]).toContain(new URL(baseURL).hostname);
  const health=await request.get("/health");
  expect(health.headers()["x-voiceagent-test-fixture"]).toBe("td-local-offline");
}

test("formal browser microphone uplink, Final cancellation and actual render receipts reach persisted history",async({page,request,baseURL})=>{
  test.skip(Boolean(process.env.VOICE_AGENT_TD_LOCAL_SCENARIO) && process.env.VOICE_AGENT_TD_LOCAL_SCENARIO!=="ordinary","Requires the ordinary offline source scenario");
  test.setTimeout(45000);
  await verifyFixture(request,baseURL);
  const created=await request.post("/api/bots",{headers:{Origin:baseURL},data:{...botPayload,name:`${botPayload.name} ${Date.now()}`}});
  expect(created.status(),await created.text()).toBe(201);
  const bot=await created.json();
  let session;
  const receipts=[],errors=[];
  const inputPackets=[];
  if(process.env.VOICE_AGENT_TD_INPUT_SOURCE_PROBE==='1') {
    page.on('websocket',socket=>socket.on('framesent',({payload})=>{
      if(Buffer.isBuffer(payload) && inputPackets.length<8) inputPackets.push(payload.toString('base64'));
    }));
  }
  page.on("pageerror",error=>errors.push(error.message));
  page.on("response",async response=>{
    if(response.url().endsWith("/api/sessions") && response.request().method()==="POST" && response.status()===201) session=await response.json();
    if(response.url().endsWith("/playback-events")) receipts.push({...response.request().postDataJSON(),http_status:response.status()});
  });
  await page.goto("/");
  await page.locator(".bot-card").filter({hasText:bot.name}).click();
  await page.locator(".test-menu summary").click();
  await page.locator('[data-test-mode="web"]').click();
  await page.locator("#start-button").click();
  await expect.poll(()=>session?.session_id,{timeout:15000}).toBeTruthy();
  await expect.poll(()=>receipts.filter(r=>r.event==="task_stopped" && r.rendered_samples>0).length,{timeout:20000}).toBeGreaterThanOrEqual(1);
  await expect.poll(()=>receipts.filter(r=>r.event==="task_finished").length,{timeout:10000}).toBeGreaterThanOrEqual(2);
  if(process.env.VOICE_AGENT_TD_RENDER_CLOCK_PROBE==='1') {
    await expect.poll(async()=>{
      const result=await request.get(`/api/sessions/${session.session_id}/metrics`,{
        headers:{Authorization:`Bearer ${session.session_token}`}});
      expect(result.status()).toBe(200);
      return (await result.json()).metrics?.some(metric=>process.env.VOICE_AGENT_TD_E2E_PROBE==='1'
        ? metric.timing_ranges?.e2e : metric.timing_ranges?.playback);
    },{timeout:5000}).toBe(true);
  }
  await page.locator("#end-button").click();
  let history;
  await expect.poll(async()=>{
    const response=await request.get(`/api/history/${session.session_id}`);
    if(!response.ok()) return null;
    history=await response.json();return history.ended_at;
  },{timeout:10000}).toBeTruthy();
  const events=history.td_events;
  expect(events.filter(e=>e.event==="td_commit")).toHaveLength(1);
  expect(events.filter(e=>e.event==="response_restart")).toHaveLength(1);
  const prepared=events.filter(e=>e.event==="playback_task_prepared");
  const old=prepared.find(e=>e.response_id==="1:1"), fresh=prepared.find(e=>e.response_id==="1:2");
  expect(old).toBeTruthy();expect(fresh).toBeTruthy();
  const rendered=events.filter(e=>e.event==="playback_renderer_receipt");
  const stopped=rendered.find(e=>e.playback_id===old.playback_id && e.renderer_event==="task_stopped");
  const newStart=rendered.find(e=>e.playback_id===fresh.playback_id && e.renderer_event==="task_started");
  expect(stopped.rendered_samples).toBeGreaterThan(0);
  expect(stopped.rendered_samples).toBeLessThan(120000);
  expect(newStart.created_ms).toBeGreaterThanOrEqual(stopped.created_ms);
  expect(rendered.some(e=>e.playback_id===fresh.playback_id && e.renderer_event==="task_finished")).toBe(true);
  expect(receipts.every(r=>r.http_status===204)).toBe(true);
  expect(errors).toEqual([]);
  if(process.env.VOICE_AGENT_TD_INPUT_SOURCE_PROBE==='1') {
    expect(inputPackets.length).toBeGreaterThan(0);
    writeFileSync(`${evidence}/input-source-packets.json`,JSON.stringify(inputPackets));
  }
  expect(history.metrics).toHaveLength(1);
  expect(history.metrics[0].turn_to_playback_ms).toBeNull();
  expect(history.metrics[0].incomplete_reason).toBe(history.metrics[0].timing_ranges?.e2e
    ? "bounded_timing_only" : history.metrics[0].timing_ranges?.playback
    ? "source_end_clock_unavailable" : "render_clock_uncorrelated");
  if(process.env.VOICE_AGENT_TD_RENDER_CLOCK_PROBE==='1') {
    expect(history.metrics[0].timing_ranges.playback).toBeTruthy();
    writeFileSync(`${evidence}/ws-timing-history.json`,JSON.stringify(history,null,2));
  }
  await page.reload();
  await page.getByRole("button",{name:"Sessions",exact:true}).click();
  await page.locator(".history-row").filter({hasText:session.session_id}).click();
  await expect(page.locator("#history-dialog .sample-turn")).toHaveCount(1);
  if(process.env.VOICE_AGENT_TD_E2E_PROBE==='1') {
    await expect(page.locator('#history-dialog .e2e-timing-range')).toHaveCount(2);
    await expect(page.locator('#history-dialog .e2e-timing-range').first()).toContainText('VAD speech-end source sample');
  }
  await expect(page.locator("#history-dialog")).toContainText("Response to local partial.");
  await expect(page.locator("#history-dialog")).toContainText("Response to local final.");
});

test("missing source evidence closes the formal call with explicit error and failed history",async({page,request,baseURL})=>{
  test.skip(process.env.VOICE_AGENT_TD_LOCAL_SCENARIO!=="source_missing","Requires the source-missing offline scenario");
  test.setTimeout(30000);
  await verifyFixture(request,baseURL);
  expect((await request.get('/health')).headers()['x-voiceagent-test-scenario']).toBe('source_missing');
  const created=await request.post('/api/bots',{headers:{Origin:baseURL},data:{...botPayload,name:`Source failure ${Date.now()}`}});
  expect(created.status(),await created.text()).toBe(201);
  const bot=await created.json();
  let session;
  page.on('response',async response=>{
    if(response.url().endsWith('/api/sessions') && response.status()===201) session=await response.json();
  });
  await page.goto('/');
  await page.locator('.bot-card').filter({hasText:bot.name}).click();
  await page.locator('.test-menu summary').click();
  await page.locator('[data-test-mode="web"]').click();
  await page.locator('#start-button').click();
  await expect.poll(()=>session?.session_id,{timeout:10000}).toBeTruthy();
  await expect(page.locator('#error-banner')).toContainText('Speech recognition timing was unavailable',{timeout:15000});
  let history;
  await expect.poll(async()=>{
    const response=await request.get(`/api/history/${session.session_id}`);
    if(!response.ok()) return null;
    history=await response.json();return history.ended_at;
  },{timeout:10000}).toBeTruthy();
  expect(history.status).toBe('failed');
  expect(history.error_category).toBe('asr_source_evidence_unavailable');
  expect(history.turns.some(turn=>turn.role==='user')).toBe(false);
  expect(history.td_events.filter(event=>event.event==='td_commit')).toEqual([]);
  expect(history.td_events.filter(event=>event.event==='asr_source_evidence_failed')).toHaveLength(1);
  expect(history.td_events.find(event=>event.event==='asr_source_evidence_failed').turn_id).toBeNull();
  expect(history.td_events.some(event=>event.event==='unranged_transcript' && event.text==='local input without source evidence')).toBe(true);
  await expect(page.locator('#start-button')).toBeEnabled();
  await page.reload();
  await page.getByRole('button',{name:'Sessions',exact:true}).click();
  await page.locator('.history-row').filter({hasText:session.session_id}).click();
  await expect(page.locator('#history-dialog')).toContainText('Session evidence without turn attribution');
  await page.locator('#history-dialog summary').filter({hasText:'Session evidence without turn attribution'}).click();
  await expect(page.locator('#history-dialog')).toContainText('local input without source evidence');
  await expect(page.locator('#history-dialog')).toContainText('ASR source evidence unavailable');
  expect(await page.locator('#history-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
  writeFileSync(`${evidence}/source-failure-network.json`,JSON.stringify({session_id:session.session_id,status:history.status,error_category:history.error_category,td_events:history.td_events},null,2));
});

test("formal WS identifier echo survives continuation and clear stops only its old generation",async({page,request,baseURL})=>{
  const recovery=process.env.VOICE_AGENT_TD_LOCAL_SCENARIO==="identifier_cache_repair";
  test.skip(!recovery && process.env.VOICE_AGENT_TD_LOCAL_SCENARIO!=="identifier","Requires the explicit offline identifier scenario");
  test.setTimeout(40000);
  await verifyFixture(request,baseURL);
  expect((await request.get('/health')).headers()['x-voiceagent-test-scenario']).toBe(recovery?'identifier_cache_repair':'identifier');
  const payload=structuredClone(botPayload);
  payload.name=`Local identifier network ${Date.now()}`;
  payload.opening_script='Please say your identifier.';
  payload.td_config.priority_rule={enabled:true,keywords:['identifier'],
    vocabulary:[{value:'1',aliases:['one']},{value:'2',aliases:['two']}],
    wpm_threshold:90,pause_ms:100,unit_gap_ms:50,
    collection:{target_length:4,timeout_ms:15000,overflow_pause_ms:100,
      incomplete_text:'Please complete the identifier.',overflow_text:'Please check the identifier.'}};
  const created=await request.post('/api/bots',{headers:{Origin:baseURL},data:payload});
  expect(created.status(),await created.text()).toBe(201);
  const bot=await created.json();
  const cache=await (await request.get(`/api/bots/${bot.id}/echo-audio`)).json();
  const generated=await request.post(`/api/bots/${bot.id}/echo-audio/generate`,{
    headers:{Origin:baseURL},data:{expected_fingerprint:cache.fingerprint}});
  expect(generated.status(),await generated.text()).toBe(200);
  const resources=await generated.json();
  if(recovery) {
    const published=await request.post(`/api/bots/${bot.id}/publish`,{headers:{Origin:baseURL},data:{public_title:"Offline recovery fixture"}});
    expect(published.status(),await published.text()).toBe(200);
  }
  const receipts=[];
  let session;
  page.on('response',async response=>{
    if(response.url().endsWith('/api/sessions') && response.status()===201) session=await response.json();
    if(response.url().endsWith('/playback-events')) receipts.push({...response.request().postDataJSON(),http_status:response.status()});
  });
  await page.goto('/');
  await page.locator('.bot-card').filter({hasText:bot.name}).click();
  await page.locator('.test-menu summary').click();
  await page.locator('[data-test-mode="web"]').click();
  await page.locator('#start-button').click();
  await expect.poll(()=>Boolean(session)).toBe(true);
  await expect.poll(()=>receipts.filter(row=>row.event==='task_stopped' && row.rendered_samples>0).length,{timeout:25000}).toBeGreaterThan(0);
  await expect.poll(()=>receipts.filter(row=>row.event==='task_finished').length,{timeout:5000}).toBeGreaterThanOrEqual(2);
  await page.locator('#end-button').click();
  let history;
  await expect.poll(async()=>{
    history=await (await request.get(`/api/history/${session.session_id}`)).json();
    return history.ended_at;
  }).toBeTruthy();
  const events=history.td_events;
  writeFileSync(`${evidence}/ws-identifier-combination.json`,JSON.stringify({receipts,events},null,2));
  const local=events.filter(event=>event.event==='identifier_local_processed');
  expect(local.map(event=>event.collected)).toEqual(['1','12']);
  const cleared=events.filter(event=>event.event==='identifier_tool_result' && event.operation==='clear');
  expect(cleared).toHaveLength(1);
  expect(cleared[0]).toMatchObject({status:'cleared',value:'',count:0});
  const echoes=events.filter(event=>event.event==='playback_task_prepared' && event.kind==='echo');
  expect(echoes.length).toBeGreaterThanOrEqual(2);
  const first=echoes[0];
  const start=receipts.find(row=>row.playback_id===first.playback_id && row.event==='task_started');
  const stopped=receipts.find(row=>row.playback_id===first.playback_id && row.event==='task_stopped');
  expect(start).toBeTruthy();expect(stopped).toBeTruthy();
  expect(stopped.rendered_samples).toBeGreaterThan(0);
  expect(stopped.rendered_samples).toBeLessThan(240000);
  expect(stopped.render_clock_id).toBe(start.render_clock_id);
  expect(stopped.render_frame-start.render_frame).toBeGreaterThanOrEqual(stopped.rendered_samples);
  expect(receipts.some(row=>row.playback_id===echoes[1].playback_id && row.event==='task_started')).toBe(false);
  expect(receipts.every(row=>row.http_status===204)).toBe(true);
  expect(events.filter(event=>event.event==='td_commit')).toHaveLength(2);
  expect(history.turns.some(turn=>turn.text.includes('The identifier was cleared.'))).toBe(true);
  if(recovery) {
    const started=events.filter(event=>event.event==='identifier_echo_synthesis_started');
    expect(started).toHaveLength(1);
    expect(started[0].unit).toBe('1');
    expect(started[0].fingerprint).toBe(resources.fingerprint);
    const repaired=events.filter(event=>event.event==='identifier_echo_resource_ready' && event.recovery_path);
    expect(repaired).toHaveLength(1);
    expect(repaired[0]).toMatchObject({unit:'1',fingerprint:resources.fingerprint});
    expect(repaired[0].elapsed_ms).toBeGreaterThan(0);
    expect(events.some(event=>event.event==='identifier_echo_resource_failed')).toBe(false);
    await page.reload();
    await page.getByRole('button',{name:'Sessions',exact:true}).click();
    await page.locator('.history-row').filter({hasText:session.session_id}).click();
    const details=page.locator('#history-dialog .turn-td');
    await details.evaluateAll(nodes=>nodes.forEach(node=>{node.open=true;}));
    const record=page.locator('#history-dialog .td-record:has(> h4:text-is("Audio resource ready"))').filter({hasText:'true'});
    await expect(record).toHaveCount(1);
    await expect(record).toContainText('Resource duration (ms)');
    await expect(record).not.toContainText('Elapsed silence (ms)');
    await expect(record).toContainText(resources.fingerprint);
    await expect(record).toContainText('Published resource versionNot available');
    await page.locator('#td-history-language').selectOption('zh');
    const translated=page.locator('#history-dialog .td-record:has(> h4:text-is("音频资源就绪"))').filter({hasText:'true'});
    await expect(translated).toContainText('资源处理耗时（ms）');
    await expect(translated).toContainText(resources.fingerprint);
  }
});

async function createRuleBot(request,baseURL,suffix) {
  await verifyFixture(request,baseURL);
  const payload=structuredClone(botPayload);
  payload.name=`Local TD cache ${suffix} ${Date.now()}`;
  payload.td_config.priority_rule={enabled:true,keywords:["identifier"],
    vocabulary:[{value:"11",aliases:["double one","11"]},{value:"2",aliases:["two","2"]}],
    wpm_threshold:90,pause_ms:350,unit_gap_ms:50,
    collection:{target_length:3,timeout_ms:8000,overflow_pause_ms:350,incomplete_text:"Please complete the identifier.",overflow_text:"Please check its length."}};
  const response=await request.post("/api/bots",{headers:{Origin:baseURL},data:payload});
  expect(response.status(),await response.text()).toBe(201);
  return response.json();
}
async function openRules(page,bot) {
  await page.locator(".bot-card").filter({hasText:bot.name}).click();
  await page.getByRole("button",{name:"Advanced",exact:true}).click();
  await page.locator("#td-entry").click();
  await page.locator('[data-td="rules"]').click();
}

test("formal cache UI blocks incomplete publication, generates and listens, then saves and refreshes actual API state",async({page,request,baseURL})=>{
  const bot=await createRuleBot(request,baseURL,"resources");
  const generations=[];
  page.on("request",r=>{if(r.method()==="POST" && r.url().endsWith("/echo-audio/generate")) generations.push(r.url());});
  await page.addInitScript(()=>{
    window.__tdAudioStarts=[];
    const original=AudioBufferSourceNode.prototype.start;
    AudioBufferSourceNode.prototype.start=function(when,...args){window.__tdAudioStarts.push({when,duration:this.buffer?.duration});return original.call(this,when,...args);};
  });
  await page.goto("/");
  await openRules(page,bot);
  await expect(page.locator(".td-audio-status").first()).toContainText("Missing");
  await page.locator(".publish-button").click();
  await expect(page.locator("#error-banner")).toContainText("audio missing");
  expect(generations).toHaveLength(0);
  await page.locator("#cache-generate").click();
  await expect(page.locator("#cache-action-status")).toHaveText("Audio ready · stored permanently");
  expect(generations).toHaveLength(1);
  await expect(page.locator(".td-audio-status span")).toHaveText(["Ready","Ready"]);
  const ready=await (await request.get(`/api/bots/${bot.id}/echo-audio`)).json();
  expect(ready.assets.map(a=>a.unit).sort()).toEqual(["1","2"]);
  const versions=ready.assets.map(a=>a.version).sort();
  expect(versions.every(version=>/^[a-f0-9]{64}$/.test(version))).toBe(true);
  await page.locator(".td-audio-status").first().getByRole("button",{name:"Listen",exact:true}).click();
  await expect.poll(()=>page.evaluate(()=>window.__tdAudioStarts.length)).toBe(2);
  const audio=await page.evaluate(()=>window.__tdAudioStarts);
  expect(audio[0].duration).toBeCloseTo(.1,3);
  expect(audio[1].when-audio[0].when).toBeCloseTo(.15,3);
  await page.locator("#echo-gap").fill("60");
  await page.getByRole("button",{name:"Save TD settings",exact:true}).click();
  await expect(page.locator("#save-state")).toHaveText("Saved");
  await page.reload();await openRules(page,bot);
  await expect(page.locator("#echo-gap")).toHaveValue("60");
  await expect(page.locator(".td-audio-status span")).toHaveText(["Ready","Ready"]);
  const restored=await (await request.get(`/api/bots/${bot.id}/echo-audio`)).json();
  expect(restored.assets.map(a=>a.version).sort()).toEqual(versions);
  expect(generations).toHaveLength(1);
  await page.locator(".publish-button").click();
  await expect.poll(async()=> (await (await request.get(`/api/bots/${bot.id}/share`)).json()).published).toBe(true);
  expect(generations).toHaveLength(1);
  const other=await createRuleBot(request,baseURL,"isolation");
  await page.reload();await openRules(page,other);
  await expect(page.locator("#echo-gap")).toHaveValue("50");
  await expect(page.locator(".td-audio-status").first()).toContainText("Missing");
});

test("deleting a vocabulary row during a real slow save retains newer unsaved edits",async({page,request,baseURL})=>{
  const bot=await createRuleBot(request,baseURL,"save-race");
  await page.goto("/");await openRules(page,bot);
  let waiting=false,release;
  await page.route(`**/api/bots/${bot.id}`,async route=>{
    if(route.request().method()!=="PUT") return route.continue();
    const response=await route.fetch();waiting=true;
    await new Promise(resolve=>{release=resolve;});
    await route.fulfill({response});
  });
  await page.locator("#echo-gap").fill("60");
  await page.getByRole("button",{name:"Save TD settings",exact:true}).click();
  await expect.poll(()=>waiting).toBe(true);
  await page.locator(".td-vocab-row").last().getByRole("button",{name:"Delete mapping"}).click();
  release();
  await expect(page.locator("#save-state")).toContainText("newer edits unsaved");
  await expect(page.locator(".td-vocab-row")).toHaveCount(1);
  await page.unroute(`**/api/bots/${bot.id}`);
  await page.getByRole("button",{name:"Save TD settings",exact:true}).click();
  await expect(page.locator("#save-state")).toHaveText("Saved");
  const restored=await (await request.get(`/api/bots/${bot.id}`)).json();
  expect(restored.td_config.priority_rule.vocabulary).toHaveLength(1);
  expect(restored.has_asr_key).toBe(true);
  expect(restored.has_tts_key).toBe(true);
  expect(restored.has_llm_key).toBe(true);
  expect(restored.has_jev_key).toBe(true);
  expect(restored.system_prompt).toBe(bot.system_prompt);
  expect(restored.tts_voice).toBe(bot.tts_voice);
});

test("failed TD save retains draft and retries against the actual API",async({page,request,baseURL})=>{
  const bot=await createRuleBot(request,baseURL,"save-recovery");
  await page.goto("/");await openRules(page,bot);
  await page.locator("#echo-gap").fill("70");
  await page.route(`**/api/bots/${bot.id}`,route=>route.request().method()==="PUT"
    ? route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"Temporary local test failure"})})
    : route.continue());
  await page.getByRole("button",{name:"Save TD settings",exact:true}).click();
  await expect(page.locator("#form-error")).toHaveText("Temporary local test failure");
  await expect(page.locator("#echo-gap")).toHaveValue("70");
  await expect(page.locator("#save-state")).toHaveText("Unsaved changes");
  expect((await (await request.get(`/api/bots/${bot.id}`)).json()).td_config.priority_rule.unit_gap_ms).toBe(50);
  await page.unroute(`**/api/bots/${bot.id}`);
  await page.getByRole("button",{name:"Save TD settings",exact:true}).click();
  await expect(page.locator("#save-state")).toHaveText("Saved");
  await expect(page.locator("#form-error")).toBeHidden();
  await expect(page.locator("#jev-error")).toHaveJSProperty("hidden",true);
  await page.reload();await openRules(page,bot);
  await expect(page.locator("#echo-gap")).toHaveValue("70");
});

test("formal configuration and audio survive an explicitly coordinated process restart",async({page,request,baseURL})=>{
  const stage=process.env.VOICE_AGENT_TD_RESTART_STAGE;
  test.skip(!["before","after"].includes(stage),"Requires a controlled restart of the disposable fixture process");
  await verifyFixture(request,baseURL);
  const snapshotPath=process.env.VOICE_AGENT_TD_RESTART_SNAPSHOT || "/tmp/voiceagent-td-r15/restart-snapshot.json";
  if(stage==="before") {
    const bots=await (await request.get("/api/bots")).json();
    const bot=bots.find(item=>item.name.startsWith("Local TD cache resources") && item.td_config.priority_rule.unit_gap_ms===60);
    expect(bot).toBeTruthy();
    const audio=await (await request.get(`/api/bots/${bot.id}/echo-audio`)).json();
    expect(audio.assets.every(item=>item.status==="ready")).toBe(true);
    expect(audio.assets).toHaveLength(2);
    writeFileSync(snapshotPath,JSON.stringify({id:bot.id,name:bot.name,config:bot.td_config,assets:audio.assets}));
    return;
  }
  const previous=JSON.parse(readFileSync(snapshotPath,"utf8"));
  const bot=await (await request.get(`/api/bots/${previous.id}`)).json();
  expect(bot.td_config).toEqual(previous.config);
  expect([bot.has_asr_key,bot.has_tts_key,bot.has_llm_key,bot.has_jev_key]).toEqual([true,true,true,true]);
  const audio=await (await request.get(`/api/bots/${bot.id}/echo-audio`)).json();
  expect(audio.assets).toEqual(previous.assets);
  for(const asset of audio.assets) {
    const response=await request.get(asset.url);
    expect(response.status()).toBe(200);
    expect((await response.body()).length).toBeGreaterThan(44);
  }
  await page.goto("/");await openRules(page,bot);
  await expect(page.locator("#echo-gap")).toHaveValue("60");
  await expect(page.locator(".td-audio-status span")).toHaveText(["Ready","Ready"]);
});

test("late save failure stays with its original Bot after selection changes",async({page,request,baseURL})=>{
  const original=await createRuleBot(request,baseURL,"late-failure-original");
  const other=await createRuleBot(request,baseURL,"late-failure-other");
  await page.goto("/");await openRules(page,original);
  let waiting=false,release;
  await page.route(`**/api/bots/${original.id}`,async route=>{
    if(route.request().method()!=="PUT") return route.continue();
    waiting=true;await new Promise(resolve=>{release=resolve;});
    await route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"Old Bot save failed"})});
  });
  await page.locator("#echo-gap").fill("80");
  await page.getByRole("button",{name:"Save TD settings",exact:true}).click();
  await expect.poll(()=>waiting).toBe(true);
  await openRules(page,other);
  const response=page.waitForResponse(r=>r.url().endsWith(`/api/bots/${original.id}`) && r.request().method()==="PUT");
  release();await response;
  await expect(page.locator("#form-error")).toHaveJSProperty("hidden",true);
  await expect(page.locator("#jev-error")).toHaveJSProperty("hidden",true);
  await expect(page.locator("#echo-gap")).toHaveValue("50");
});

test("formal TD settings remain operable at 390px with actual saved configuration",async({page,request,baseURL})=>{
  const bot=await createRuleBot(request,baseURL,"narrow");
  await page.setViewportSize({width:390,height:844});
  await page.goto("/");await openRules(page,bot);
  await expect(page.locator("#echo-gap")).toHaveValue("50");
  const overflow=await page.evaluate(()=>[document.documentElement,...document.querySelectorAll('[role="dialog"],dialog,.td-content,#td')]
    .filter(node=>node.getClientRects().length && node.scrollWidth>node.clientWidth+1)
    .map(node=>({tag:node.tagName,id:node.id,scroll:node.scrollWidth,client:node.clientWidth})));
  expect(overflow).toEqual([]);
  const numberWidth=await page.locator("#echo-gap").evaluate(input=>{
    const style=getComputedStyle(input),canvas=document.createElement("canvas"),context=canvas.getContext("2d");
    context.font=style.font;
    return {available:input.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight),required:context.measureText("999").width+16};
  });
  expect(numberWidth.available).toBeGreaterThanOrEqual(numberWidth.required);
  await page.locator("#echo-gap").fill("90");
  await page.getByRole("button",{name:"Save TD settings",exact:true}).click();
  await expect(page.locator("#save-state")).toHaveText("Saved");
  await page.screenshot({path:`${evidence}/formal-rules-390.png`,fullPage:true});
});

test("audio generation failure permits an explicit retry without publishing or losing settings",async({page,request,baseURL})=>{
  const bot=await createRuleBot(request,baseURL,"audio-recovery");
  await page.goto("/");await openRules(page,bot);
  const endpoint=`**/api/bots/${bot.id}/echo-audio/generate`;
  await page.route(endpoint,route=>route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"Temporary audio preparation failure"})}));
  await page.locator("#cache-generate").click();
  await expect(page.locator("#cache-action-status")).toHaveText("Temporary audio preparation failure");
  await expect(page.locator("#cache-generate")).toBeEnabled();
  await expect(page.locator("#echo-gap")).toHaveValue("50");
  const missing=await (await request.get(`/api/bots/${bot.id}/echo-audio`)).json();
  expect(missing.assets.some(asset=>asset.status!=="ready")).toBe(true);
  expect((await (await request.get(`/api/bots/${bot.id}/share`)).json()).published).toBe(false);
  await page.unroute(endpoint);
  await page.locator("#cache-generate").click();
  await expect(page.locator("#cache-action-status")).toHaveText("Audio ready · stored permanently");
  await expect(page.locator(".td-audio-status span")).toHaveText(["Ready","Ready"]);
  expect((await (await request.get(`/api/bots/${bot.id}/share`)).json()).published).toBe(false);
});

test("formal language switch changes labels without changing TD request or user values",async({page,request,baseURL})=>{
  const bot=await createRuleBot(request,baseURL,"locale");
  await page.goto("/");await openRules(page,bot);
  await expect(page.locator("#td-language")).toBeVisible();
  await page.locator("#keywords").fill("General\n编号");
  const payloads=[];
  page.on("request",r=>{if(r.method()==="PUT" && r.url().endsWith(`/api/bots/${bot.id}`)) payloads.push(r.postDataJSON());});
  await page.locator('#td-form button[type="submit"]').click();
  await expect(page.locator("#save-state")).toHaveText("Saved");
  const values=()=>page.locator(".td-content input,.td-content textarea,.td-content select:not(#td-language)").evaluateAll(nodes=>nodes.map(node=>({id:node.id,value:node.value,checked:node.checked})));
  const before=await values();
  await page.locator("#td-language").selectOption("zh");
  await expect(page.locator('[data-td="rules"]')).toHaveText("优先规则");
  expect(await values()).toEqual(before);
  await page.locator('#td-form button[type="submit"]').click();
  await expect.poll(()=>payloads.length).toBe(2);
  expect(payloads[1]).toEqual(payloads[0]);
  await page.locator("#td-language").selectOption("en");
  await expect(page.locator('[data-td="rules"]')).toHaveText("Priority rules");
  expect(await values()).toEqual(before);
});

test("formal TD language defaults to Chinese without replacing user prompts",async({page,request,baseURL})=>{
  const bot=await createRuleBot(request,baseURL,"default-locale");
  await page.goto("/");await openRules(page,bot);
  await expect(page.locator("#td-language")).toHaveValue("zh");
  await expect(page.locator('[data-td="rules"]')).toHaveText("优先规则");
  await expect(page.locator("#keywords")).toHaveValue("identifier");
  await expect(page.locator("#jev-yield-instructions")).toHaveValue(td.jev.noul_instructions);
});
