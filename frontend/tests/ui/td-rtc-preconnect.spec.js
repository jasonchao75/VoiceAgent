import {test,expect} from '@playwright/test';
test.skip(process.env.VOICE_AGENT_TD_LOCAL_RUNTIME!=='1','Requires offline local application');
test.use({permissions:['microphone'],launchOptions:{args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']}});
test('unsupported task playback releases each real pending session before retry',async({page,request,baseURL})=>{
  expect(['localhost','127.0.0.1']).toContain(new URL(baseURL).hostname);
  expect((await request.get('/health')).headers()['x-voiceagent-test-fixture']).toBe('td-local-offline');
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
  const generated=await request.post(`/api/bots/${bot.id}/echo-audio/generate`,{headers:{Origin:baseURL},data:{}});
  expect(generated.status()).toBe(200);
  const published=await request.post(`/api/bots/${bot.id}/publish`,{headers:{Origin:baseURL},data:{public_title:bot.name}});
  expect(published.status()).toBe(200);
  const share=await published.json();

  const publicId=share.public_id;
  const document=await request.get('/demo.html');
  await page.route(`**/demo/${publicId}`,route=>route.fulfill({response:document}));
  await page.addInitScript(()=>{
    Object.defineProperty(globalThis,'RTCRtpScriptTransform',{value:undefined,configurable:true});
    window.__setupTracks=[];
    const getMedia=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia=async(...args)=>{
      const stream=await getMedia(...args);window.__setupTracks.push(...stream.getTracks());return stream;
    };
  });
  let held=false,unblock;
  const gate=new Promise(resolve=>{unblock=resolve;});
  await page.route('**/api/sessions/*/events',async route=>{
    if(!held && route.request().postDataJSON()?.event==='mobile_call_error') {
      held=true;
      const response=await route.fetch();
      await gate;
      await route.fulfill({response});
    } else await route.continue();
  });
  const sessions=[],errors=[];
  let offers=0;
  page.on('request',r=>{if(r.url().includes('/api/public/webrtc/') && r.method()==='POST')offers++;});
  page.on('response',async r=>{
    if(r.url().endsWith(`/api/public/demos/${publicId}/sessions`) && r.status()===201)sessions.push(await r.json());
    if(r.url().endsWith('/events') && r.request().postDataJSON()?.event==='mobile_call_error')errors.push(r.status());
  });
  await page.goto(`/demo/${publicId}`);
  for(let i=0;i<4;i++) {
    await page.locator(i===0?'#start-call':'#retry').click();
    if(i===0) {
      await expect.poll(()=>held).toBe(true);
      await expect.poll(()=>page.evaluate(()=>window.__setupTracks.length>0 && window.__setupTracks.every(track=>track.readyState==='ended')),{timeout:1500}).toBe(true);
      unblock();
    }
    await expect(page.locator('#error-copy')).toHaveText(/cannot play identifier echoes/);
    await expect.poll(()=>errors.length).toBe(i+1);
    expect(errors.at(-1)).toBe(204);
    const health=await (await request.get('/health')).json();
    expect(health.pending_sessions).toBe(0);
    expect(health.active_sessions).toBe(0);
  }
  expect(sessions).toHaveLength(4);expect(offers).toBe(0);
  for(const session of sessions) {
    const history=await (await request.get(`/api/history/${session.session_id}`)).json();
    expect(history.status).toBe('failed');expect(history.error_category).toBe('playback_unsupported');
  }
});
