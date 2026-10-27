import { test, expect } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || "../test-results/td-runtime-evidence";
mkdirSync(evidence,{recursive:true});

const enabled=process.env.VOICE_AGENT_TD_LOCAL_RUNTIME==="1" && process.env.VOICE_AGENT_GATE2_MIXED==="1";
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


test('mixed submit then correction clears once and preserves the next collection',async({page,request,baseURL})=>{
 test.setTimeout(40000); await verifyFixture(request,baseURL);
 const payload=structuredClone(botPayload);payload.name=`Gate2 mixed ${Date.now()}`;payload.opening_script='请提供编号';
 payload.td_config.priority_rule={enabled:true,keywords:['编号'],vocabulary:Array.from({length:10},(_,i)=>({value:String(i),aliases:[String(i)]})),wpm_threshold:180,pause_ms:100,unit_gap_ms:50,collection:{target_length:6,timeout_ms:15000,overflow_pause_ms:350,incomplete_text:'请继续提供编号',overflow_text:'编号超位'}};
 const created=await request.post('/api/bots',{headers:{Origin:baseURL},data:payload});expect(created.status(),await created.text()).toBe(201);const bot=await created.json();
 const cache=await(await request.get(`/api/bots/${bot.id}/echo-audio`)).json();
 const generated=await request.post(`/api/bots/${bot.id}/echo-audio/generate`,{headers:{Origin:baseURL},data:{expected_fingerprint:cache.fingerprint}});expect(generated.status()).toBe(200);
 let session;const receipts=[];
 page.on('response',async r=>{if(r.url().endsWith('/api/sessions')&&r.status()===201)session=await r.json();if(r.url().endsWith('/playback-events'))receipts.push({...r.request().postDataJSON(),http_status:r.status()});});
 await page.goto('/');await page.locator('.bot-card').filter({hasText:bot.name}).click();await page.locator('.test-menu summary').click();await page.locator('[data-test-mode="web"]').click();await page.locator('#start-button').click();
 await expect.poll(()=>receipts.filter(r=>r.event==='task_stopped').length,{timeout:20000}).toBeGreaterThan(0);
 await expect.poll(()=>receipts.filter(r=>r.event==='task_started').length,{timeout:10000}).toBeGreaterThanOrEqual(5);
 await page.locator('#end-button').click();let history;
 await expect.poll(async()=>{history=await(await request.get(`/api/history/${session.session_id}`)).json();return history.ended_at;}).toBeTruthy();
 writeFileSync(`${evidence}/mixed.json`,JSON.stringify({receipts,history},null,2));
 const events=history.td_events,results=events.filter(e=>e.event==='identifier_tool_result');
 expect(results.map(e=>[e.operation,e.status,e.value])).toEqual([['submit','submitted','123'],['clear','cleared','']]);
 const local=events.filter(e=>e.event==='identifier_local_processed');expect(local.map(e=>e.collected)).toEqual(['1234','89']);
 expect(local.map(e=>e.text)).toEqual(['4','89']);expect(events.filter(e=>e.event==='td_commit').map(e=>e.text)).toEqual(['我的号码是123','不是123，是124']);
 const echoes=events.filter(e=>e.event==='playback_task_prepared'&&e.kind==='echo');expect(echoes).toHaveLength(2);
 expect(receipts.some(r=>r.playback_id===echoes[0].playback_id&&r.event==='task_stopped'&&r.rendered_samples>0)).toBe(true);
 expect(receipts.some(r=>r.playback_id===echoes[1].playback_id&&r.event==='task_started')).toBe(true);
 expect(history.turns.some(t=>t.text.includes('编号已清空，请完整重念。'))).toBe(true);
 expect(receipts.every(r=>r.http_status===204)).toBe(true);
 await page.reload();await page.getByRole('button',{name:'Sessions',exact:true}).click();await page.locator('.history-row').filter({hasText:session.session_id}).click();await expect(page.locator('#history-dialog')).toContainText('编号已清空，请完整重念。');await page.screenshot({path:`${evidence}/mixed-history.png`,fullPage:true});
});
