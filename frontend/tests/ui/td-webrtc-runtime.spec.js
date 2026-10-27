import {test,expect} from "@playwright/test";
import {mkdirSync,writeFileSync} from "node:fs";
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || "../test-results/td-webrtc-evidence";
mkdirSync(evidence,{recursive:true});
const enabled=process.env.VOICE_AGENT_TD_LOCAL_RUNTIME==="1";
test.skip(!enabled,"Requires the loopback-only disposable TD application");
test.use({permissions:["microphone"],launchOptions:{args:["--use-fake-device-for-media-stream","--use-fake-ui-for-media-stream","--autoplay-policy=no-user-gesture-required"]}});
test.afterEach(async({page},info)=>{
  const diagnostics=await page.evaluate(async()=>({samples:window.__rtcSamples,tracks:window.__rtcTracks,
    stats:await Promise.all((window.__rtcConnections||[]).map(async pc=>[...(await pc.getStats()).values()]
      .filter(s=>s.type==="inbound-rtp" && s.kind==="audio")))})).catch(()=>({closed:true}));
  writeFileSync(`${evidence}/rtc-probe-diagnostics.${info.project.name}.json`,JSON.stringify(diagnostics,null,2));
});

test("formal mobile route establishes the existing WebRTC audio track with local TD",async({page,request,baseURL},info)=>{
  test.setTimeout(45000);
  expect(["localhost","127.0.0.1"]).toContain(new URL(baseURL).hostname);
  expect((await request.get("/health")).headers()["x-voiceagent-test-fixture"]).toBe("td-local-offline");
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
    window.__rtcSamples=[];
    window.__rtcTracks=[];
    window.__rtcConnections=[];
    const Native=window.RTCPeerConnection;
    window.RTCPeerConnection=class extends Native {
      constructor(...args){
        super(...args);
        window.__rtcConnections.push(this);
        this.addEventListener("track",async event=>{
          if(event.track.kind!=="audio") return;
          const context=new AudioContext(),source=context.createMediaStreamSource(new MediaStream([event.track]));
          window.__rtcTracks.push({kind:event.track.kind,state:event.track.readyState,context:context.state,enabled:event.track.enabled,muted:event.track.muted});
          const analyser=context.createAnalyser(),silent=context.createGain();
          analyser.fftSize=2048;silent.gain.value=0;source.connect(analyser);analyser.connect(silent);silent.connect(context.destination);
          await context.resume();
          const bins=new Float32Array(analyser.frequencyBinCount);
          setInterval(()=>{
            analyser.getFloatFrequencyData(bins);
            let peak=0;for(let i=1;i<bins.length;i++) if(bins[i]>bins[peak]) peak=i;
            window.__rtcSamples.push({at:performance.now(),frequency:peak*context.sampleRate/analyser.fftSize,db:bins[peak]});
          },20);
        });
      }
    };
  });
  let session;
  page.on("response",async r=>{if(r.url().endsWith(`/api/public/demos/${publicId}/sessions`) && r.status()===201) session=await r.json();});
  await page.goto(`/demo/${publicId}`);
  await page.locator("#start-call").click();
  await expect.poll(()=>Boolean(session),{timeout:10000}).toBe(true);
  await expect(page.locator('[data-screen="live"]')).toBeVisible({timeout:20000});
  await expect.poll(()=>page.evaluate(()=>window.__rtcSamples.some(s=>s.db>-35 && Math.abs(s.frequency-440)<40)),{timeout:15000}).toBe(true);
  await expect.poll(()=>page.evaluate(()=>window.__rtcSamples.some(s=>s.db>-35 && Math.abs(s.frequency-880)<40)),{timeout:10000}).toBe(true);
  await expect(page.locator("audio")).toHaveCount(1);
  await expect(page.locator("audio")).toHaveJSProperty("paused",false);
  await expect.poll(()=>page.evaluate(()=>{
    const first=window.__rtcSamples.find(s=>s.db>-35 && Math.abs(s.frequency-880)<40);
    return first && window.__rtcSamples.at(-1).at-first.at;
  })).toBeGreaterThan(700);
  const samples=await page.evaluate(()=>window.__rtcSamples.filter(s=>s.db>-35));
  const partial=samples.filter(s=>Math.abs(s.frequency-440)<40),final=samples.filter(s=>Math.abs(s.frequency-880)<40);
  expect(partial.length).toBeGreaterThan(0);expect(final.length).toBeGreaterThan(0);
  expect(partial.at(-1).at-partial[0].at).toBeLessThan(2000);
  expect(partial.at(-1).at).toBeLessThan(final[0].at);
  writeFileSync(`${evidence}/received-tones.${info.project.name}.json`,JSON.stringify(samples,null,2));
  await page.locator("#end").click();
  await expect(page.locator("audio")).toHaveJSProperty("paused",true);
  await expect(page.locator("audio")).toHaveJSProperty("srcObject",null);
  await expect.poll(async()=>{
    const history=await (await request.get(`/api/history/${session.session_id}`)).json();
    return history.td_events?.filter(event=>event.event==="response_restart").length;
  },{timeout:15000}).toBe(1);
});
