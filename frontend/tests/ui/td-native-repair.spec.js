import {test as base,expect} from '@playwright/test';
const test=base.extend({request:async({request,playwright,baseURL},use)=>{
  const login=await request.post('/api/auth/login',{data:{username:'fixture-manager',password:'fixture-local-only'}});
  expect(login.status()).toBe(200);
  const cookie=login.headers()['set-cookie'].split(';')[0];
  const manager=await playwright.request.newContext({baseURL,extraHTTPHeaders:{Cookie:cookie}});
  try {await use(manager);} finally {await manager.dispose();}
}});
import {mkdirSync,writeFileSync} from 'node:fs';

test.skip(process.env.VOICE_AGENT_TD_NATIVE_REPAIR !== '1','Requires isolated offline native fixture');
test.use({permissions:['microphone'],launchOptions:{args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--autoplay-policy=no-user-gesture-required']}});

test('anonymous published identifier call uses native audio without decoder APIs or task receipts',async({page,request,baseURL},info)=>{
  test.setTimeout(40000);
  const response=await request.post('/api/bots',{headers:{Origin:baseURL},data:{
    name:`Native identifier ${Date.now()}`,asr_provider:'deepgram',asr_model:'flux-general-en',
    tts_provider:'deepgram_flux',tts_voice:'flux-alexis-en',llm_provider:'openai',llm_base_url:'https://api.openai.com/v1',llm_model:'gpt-4.1-mini',
    system_prompt:'Offline local fixture only.',opening_script:'Please say your identifier.',turn_detection_source:'self_developed',
    td_config:{minimum_ms:100,maximum_ms:600,final_wait_ms:50,alpha:.5,conflict_threshold:.8,
      vad:{confidence:.7,start_secs:.2,stop_secs:.2,min_volume:.6},
      jev:{endpoint:'https://api.typesafe.ai/v1/systemone',model:'jev-latest',timeout_seconds:2,noul_instructions:'Yield?',choice_instructions:'State?',options:[{id:'complete',meaning:'Done',wait_ms:100},{id:'incomplete',meaning:'Continue',wait_ms:500}]},
      priority_rule:{enabled:true,keywords:['identifier'],vocabulary:[{value:'1',aliases:['one']},{value:'2',aliases:['two']}],wpm_threshold:90,pause_ms:100,unit_gap_ms:50,
        collection:{target_length:4,timeout_ms:15000,overflow_pause_ms:100,incomplete_text:'Please complete the identifier.',overflow_text:'Too long.'}}},
    save_asr_key:true,save_tts_key:true,save_llm_key:true,save_jev_key:true,
    asr_api_key:'local-inert-asr-000000',tts_api_key:'local-inert-tts-000000',llm_api_key:'local-inert-llm-000000',jev_api_key:'local-inert-jev-000000',
  }});
  expect(response.status(),await response.text()).toBe(201);
  const bot=await response.json();
  expect((await request.post(`/api/bots/${bot.id}/echo-audio/generate`,{headers:{Origin:baseURL},data:{}})).status()).toBe(200);
  const published=await request.post(`/api/bots/${bot.id}/publish`,{headers:{Origin:baseURL},data:{public_title:bot.name}});
  expect(published.status(),await published.text()).toBe(200);
  const {public_id}=await published.json();
  const document=await request.get('/demo.html');
  await page.route(`**/demo/${public_id}`,r=>r.fulfill({response:document}));
  await page.addInitScript(()=>{
    for(const key of ['AudioDecoder','RTCRtpScriptTransform'])Object.defineProperty(globalThis,key,{value:undefined,configurable:true});
    Object.defineProperty(RTCRtpReceiver.prototype,'createEncodedStreams',{value:undefined,configurable:true});
  });
  const receipts=[];let session;
  page.on('request',r=>{if(/playback-events|playback-clock|td-rtp-candidate-worker/.test(r.url()))receipts.push(r.url());});
  page.on('response',async r=>{if(r.url().endsWith(`/api/public/demos/${public_id}/sessions`)&&r.status()===201)session=await r.json();});
  await page.goto(`/demo/${public_id}`);
  expect(await page.context().cookies()).toEqual([]);
  expect(await page.evaluate(async()=> (await fetch('/api/bots')).status)).toBe(401);
  await page.locator('#start-call').click();
  await expect.poll(()=>session?.playback_mode).toBe('native');
  await expect(page.locator('[data-screen="live"]')).toBeVisible({timeout:15000});
  await expect(page.locator('audio')).toHaveJSProperty('paused',false);
  const media=await page.evaluate(async()=>{
    const audio=document.querySelector('audio'),context=new AudioContext();
    await context.resume();
    const source=context.createMediaStreamSource(audio.srcObject),analyser=context.createAnalyser();
    source.connect(analyser);let peak=0;const data=new Float32Array(2048);analyser.fftSize=2048;
    for(let i=0;i<80;i++){analyser.getFloatTimeDomainData(data);peak=Math.max(peak,...data.map(Math.abs));await new Promise(r=>setTimeout(r,25));}
    await context.close();return {peak};
  });
  expect(media.peak).toBeGreaterThan(.001);
  // History events are atomically persisted at hangup, not during the live call.
  await page.waitForTimeout(9000);
  await page.locator('#end').click();
  await expect(page.locator('audio')).toHaveJSProperty('srcObject',null);
  await expect.poll(async()=>{
    const h=await(await request.get(`/api/history/${session.session_id}`)).json();
    return h.td_events?.some(e=>e.event==='identifier_tool_result'&&e.status==='cleared');
  },{timeout:10000}).toBe(true);
  const history=await(await request.get(`/api/history/${session.session_id}`)).json();
  expect(history.td_events.some(e=>e.event==='playback_server_send_cancelled')).toBe(true);
  expect(history.td_events.some(e=>e.event.startsWith('playback_client_'))).toBe(false);
  expect(receipts).toEqual([]);
  const folder='/tmp/voiceagent-native-browser-final';mkdirSync(folder,{recursive:true});
  writeFileSync(`${folder}/${info.project.name}.json`,JSON.stringify({media,mode:session.playback_mode,event_names:history.td_events.map(e=>e.event),receipts},null,2));
  await page.screenshot({path:`${folder}/${info.project.name}.png`});
});
