import { test, expect } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || "../test-results/td-runtime-evidence";
mkdirSync(evidence,{recursive:true});

const enabled=process.env.VOICE_AGENT_TD_LOCAL_RUNTIME==="1" && process.env.VOICE_AGENT_GATE2_NUMBER_PLAYBACK==="1";
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


for (const [scenario,target] of [['complete',3],['overflow',2]]) {
 test(`Gate2 browser ${scenario} actual playback and dedup`,async({page,request,baseURL})=>{
  test.setTimeout(45000);
  await verifyFixture(request,baseURL);
  const payload=structuredClone(botPayload);
  payload.name=`Gate2 ${scenario} ${Date.now()}`;
  payload.opening_script='Please say your identifier.';
  payload.td_config.priority_rule={enabled:true,keywords:['identifier'],vocabulary:[{value:'1',aliases:['one']},{value:'2',aliases:['two']},{value:'3',aliases:['three']}],wpm_threshold:180,pause_ms:100,unit_gap_ms:50,collection:{target_length:target,timeout_ms:8000,overflow_pause_ms:350,incomplete_text:'Please complete the identifier.',overflow_text:'The identifier is too long.'}};
  const created=await request.post('/api/bots',{headers:{Origin:baseURL},data:payload});
  expect(created.status(),await created.text()).toBe(201); const bot=await created.json();
  const cache=await (await request.get(`/api/bots/${bot.id}/echo-audio`)).json();
  const generated=await request.post(`/api/bots/${bot.id}/echo-audio/generate`,{headers:{Origin:baseURL},data:{expected_fingerprint:cache.fingerprint}});
  expect(generated.status(),await generated.text()).toBe(200);
  const receipts=[]; let session;
  page.on('response',async response=>{
   if(response.url().endsWith('/api/sessions')&&response.status()===201) session=await response.json();
   if(response.url().endsWith('/playback-events')) receipts.push({...response.request().postDataJSON(),http_status:response.status()});
  });
  await page.goto('/'); await page.locator('.bot-card').filter({hasText:bot.name}).click();
  await page.locator('.test-menu summary').click(); await page.locator('[data-test-mode="web"]').click(); await page.locator('#start-button').click();
  await expect.poll(()=>Boolean(session)).toBe(true);
  // Include sustained silence beyond the collection timeout after the second input.
  await expect.poll(()=>receipts.filter(r=>r.event==='task_finished').length,{timeout:25000}).toBeGreaterThanOrEqual(3);
  await page.locator('#end-button').click();
  let history; await expect.poll(async()=>{history=await(await request.get(`/api/history/${session.session_id}`)).json();return history.ended_at;}).toBeTruthy();
  const events=history.td_events;
  writeFileSync(`${evidence}/${scenario}.json`,JSON.stringify({receipts,history},null,2));
  const prepared=events.filter(e=>e.event==='playback_task_prepared');
  const reminders=events.filter(e=>e.event==='identifier_reminder');
  const commits=events.filter(e=>e.event==='td_commit');
  const wanted=prepared.filter(e=>e.kind===(scenario==='overflow'?'overflow':'normal') && (scenario==='overflow' || e.response_id));
  expect(wanted).toHaveLength(1);
  const id=wanted[0].playback_id;
  expect(receipts.filter(r=>r.playback_id===id&&r.event==='task_started')).toHaveLength(1);
  const finished=receipts.filter(r=>r.playback_id===id&&r.event==='task_finished');
  expect(finished).toHaveLength(1); expect(finished[0].rendered_samples).toBeGreaterThan(0);
  if(scenario==='overflow') expect(reminders[0].text).toBe('The identifier is too long.');
  else expect(history.turns.some(t=>t.text.includes('The identifier has been received.'))).toBe(true);
  expect(receipts.every(r=>r.http_status===204)).toBe(true);
  if(scenario==='overflow') {expect(reminders).toHaveLength(1);expect(reminders[0].collected).toBe('123');expect(commits).toHaveLength(0);}
  else {expect(reminders).toHaveLength(0);expect(commits).toHaveLength(1);}
  const echoes=prepared.filter(e=>e.kind==='echo'); expect(echoes.length).toBeGreaterThanOrEqual(2);
  expect(receipts.some(r=>r.playback_id===echoes[0].playback_id&&r.event==='task_finished')).toBe(true);
  expect(receipts.some(r=>r.playback_id===echoes[1].playback_id&&r.event==='task_started')).toBe(false);
  const priorEnd=receipts.find(r=>r.playback_id===echoes[0].playback_id&&r.event==='task_finished');
  const nextStart=receipts.find(r=>r.playback_id===id&&r.event==='task_started');
  expect(nextStart.render_clock_id).toBe(priorEnd.render_clock_id);
  expect(nextStart.render_frame).toBeGreaterThanOrEqual(priorEnd.render_frame);
  await page.reload(); await page.getByRole('button',{name:'Sessions',exact:true}).click();
  await page.locator('.history-row').filter({hasText:session.session_id}).click();
  await expect(page.locator('#history-dialog')).toContainText(scenario==='overflow'?'The identifier is too long.':'The identifier has been received.');
  await page.screenshot({path:`${evidence}/${scenario}-history.png`,fullPage:true});

 });
}
