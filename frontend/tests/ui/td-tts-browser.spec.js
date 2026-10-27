import { test, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || "../test-results/td-tts-browser";
test.skip(process.env.VOICE_AGENT_TD_TTS_BROWSER!=="1","Requires explicitly bounded mixed TTS fixture");
test.use({permissions:["microphone"],launchOptions:{args:["--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream"]}});
const td={minimum_ms:600,maximum_ms:2500,final_wait_ms:200,alpha:.5,conflict_threshold:.8,
  vad:{confidence:.7,start_secs:.2,stop_secs:.2,min_volume:.6},
  jev:{endpoint:"https://api.typesafe.ai/v1/systemone",model:"jev-latest",timeout_seconds:2,
    noul_instructions:"Has the user yielded the floor?",choice_instructions:"Classify the utterance.",
    options:[{id:"complete",meaning:"Complete",wait_ms:700},{id:"incomplete",meaning:"Incomplete",wait_ms:1500}]},
};
const botPayload={name:"Local TD network fixture",asr_provider:"deepgram",asr_model:"flux-general-en",
  tts_provider:"deepgram_flux",tts_voice:"flux-alexis-en",llm_provider:"openai",llm_base_url:"https://api.openai.com/v1",llm_model:"gpt-4.1-mini",
  system_prompt:"Local offline fixture only.",opening_script:"",
  turn_detection_source:"self_developed",td_config:td,
  save_asr_key:true,save_tts_key:true,save_llm_key:true,save_jev_key:true,
  asr_api_key:"local-inert-asr-000000",tts_api_key:"local-inert-tts-000000",llm_api_key:"local-inert-llm-000000",jev_api_key:"local-inert-jev-000000"};


test("formal page stops rendered old TTS before rendering Final replacement", async({page,request,baseURL})=>{
  test.setTimeout(45000);
  expect(new URL(baseURL).hostname).toBe("127.0.0.1");
  const health=await request.get('/health');
  expect(health.headers()['x-voiceagent-test-fixture']).toBe('td-local-mixed-tts');
  const mode=process.env.VOICE_AGENT_TD_TTS_MODE || 'wire-fixture';
  expect(health.headers()['x-voiceagent-tts-test-mode']).toBe(mode);
  const created=await request.post('/api/bots',{headers:{Origin:baseURL},data:{...botPayload,name:`Mixed TTS ${Date.now()}`}});
  expect(created.status(),await created.text()).toBe(201);
  const bot=await created.json();
  let session;
  const receipts=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',async response=>{
    if(response.url().endsWith('/api/sessions') && response.status()===201) session=await response.json();
    if(response.url().endsWith('/playback-events')) receipts.push({...response.request().postDataJSON(),http_status:response.status()});
  });
  await page.addInitScript(()=>localStorage.setItem('voiceagent-td-locale','en'));
  await page.goto('/');
  await page.locator('.bot-card').filter({hasText:bot.name}).click();
  await page.locator('.test-menu summary').click();
  await page.locator('[data-test-mode="web"]').click();
  let failure, cleanupFailure;
  try {
  await page.locator('#start-button').click();
  await expect.poll(()=>session?.session_id,{timeout:10000}).toBeTruthy();
  if(process.env.VOICE_AGENT_TD_TTS_FAIL_AFTER_RENDER==='1') {
    expect(mode).toBe('wire-fixture');
    await expect.poll(()=>receipts.some(r=>r.event==='task_started'),{timeout:10000}).toBe(true);
    throw new Error('intentional-local-failure');
  }
  await expect.poll(()=>receipts.some(r=>r.event==='task_stopped' && r.rendered_samples>0),{timeout:20000}).toBe(true);
  await expect.poll(()=>receipts.some(r=>r.event==='task_finished'),{timeout:10000}).toBe(true);
  await page.locator('#end-button').click();
  let history;
  await expect.poll(async()=>{
    const response=await request.get(`/api/history/${session.session_id}`);
    if(!response.ok()) return null;
    history=await response.json();return history.ended_at;
  },{timeout:5000}).toBeTruthy();
  const events=history.td_events;
  expect(events.filter(e=>e.event==='td_commit')).toHaveLength(1);
  expect(events.filter(e=>e.event==='response_restart')).toHaveLength(1);
  const prepared=events.filter(e=>e.event==='playback_task_prepared');
  const old=prepared.find(e=>e.response_id==='1:1'),fresh=prepared.find(e=>e.response_id==='1:2');
  expect(old).toBeTruthy();expect(fresh).toBeTruthy();
  const rendered=events.filter(e=>e.event==='playback_renderer_receipt');
  const stop=rendered.find(e=>e.playback_id===old.playback_id && e.renderer_event==='task_stopped');
  const start=rendered.find(e=>e.playback_id===fresh.playback_id && e.renderer_event==='task_started');
  expect(stop.rendered_samples).toBeGreaterThan(0);expect(start.rendered_samples).toBeGreaterThan(0);
  expect(stop.evidence_source).toBe('audio_worklet_render');
  expect(start.evidence_source).toBe('audio_worklet_render');
  expect(typeof stop.render_clock_id).toBe('string');
  expect(stop.render_clock_id.length).toBeGreaterThan(0);
  expect(start.render_clock_id).toBe(stop.render_clock_id);
  expect(start.render_sample_rate).toBe(stop.render_sample_rate);
  expect(start.render_frame).toBeGreaterThanOrEqual(stop.render_frame);
  expect(rendered.some(e=>e.playback_id===old.playback_id && e.renderer_event==='task_finished')).toBe(false);
  expect(receipts.every(r=>r.http_status===204)).toBe(true);
  expect(errors).toEqual([]);
  const state=await (await request.get('/__tts_probe')).json();
  expect(state.status).toBe('ok');expect(state.connections).toBe(1);expect(state.speak_attempts).toBe(2);
  expect(state.sessions).toBe(1);expect(state.render_gate_released).toBe(true);
  expect(new Set(state.speech_id_hashes).size).toBe(2);
  mkdirSync(evidence,{recursive:true});
  writeFileSync(`${evidence}/history.json`,JSON.stringify(history,null,2));
  writeFileSync(`${evidence}/probe-state.json`,JSON.stringify(state,null,2));
  writeFileSync(`${evidence}/receipts.json`,JSON.stringify(receipts,null,2));
  await page.screenshot({path:`${evidence}/formal-page.png`,fullPage:true});
  } catch(error) { failure=error; }
  finally {
    try {
      const stopped=await request.post('/__tts_probe/stop',{headers:{Origin:baseURL},timeout:2000});
      expect(stopped.status()).toBe(200);
      expect((await stopped.json()).stopped).toBe(true);
    } catch(error) { cleanupFailure=error; }
    try { await page.close({runBeforeUnload:false}); } catch(error) { cleanupFailure ||= error; }
  }
  if(process.env.VOICE_AGENT_TD_TTS_FAIL_AFTER_RENDER==='1') {
    expect(failure?.message).toBe('intentional-local-failure');
    const state=await (await request.get('/__tts_probe')).json();
    expect(state.stopped).toBe(true);
    mkdirSync(evidence,{recursive:true});
    writeFileSync(`${evidence}/failure-teardown.json`,JSON.stringify(state,null,2));
  } else if(failure) throw failure;
  if(cleanupFailure) throw cleanupFailure;
});
