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

test("same opening PCM local playback timing with an explicit output observer",async({page,request,baseURL},info)=>{
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
    window.__timing={};
    const meterURL=URL.createObjectURL(new Blob([`class Meter extends AudioWorkletProcessor {
      constructor(){super();this.sent=false;}
      process(inputs,outputs){const input=inputs[0]?.[0],out=outputs[0]?.[0];
        if(out && input) out.set(input);
        if(!this.sent && input?.some(v=>Math.abs(v)>0.001)){this.sent=true;this.port.postMessage({frame:currentFrame,rate:sampleRate});}
        return true;}}
      registerProcessor('timing-meter',Meter);`],{type:'text/javascript'}));
    const NativeContext=window.AudioContext,NativeNode=window.AudioWorkletNode;
    function meter(context){
      const node=new NativeNode(context,'timing-meter');node.__benchMeter=true;
      node.port.onmessage=({data})=>{
        if(window.__timing.firstOutput!==undefined) return;
        const stamp=context.getOutputTimestamp();
        window.__timing.firstOutput=performance.now();
        window.__timing.renderEstimate=stamp.performanceTime+(data.frame/data.rate-stamp.contextTime)*1000;
      };
      return node;
    }
    window.AudioContext=class extends NativeContext {
      constructor(...args){super(...args);const add=this.audioWorklet.addModule.bind(this.audioWorklet);
        this.audioWorklet.addModule=async(url,...rest)=>{await add(url,...rest);if(!this.__meterReady){if(url!==meterURL) await add(meterURL);this.__meterReady=true;}};
      }
    };
    const connect=AudioNode.prototype.connect;
    AudioNode.prototype.connect=function(destination,...rest){
      if(this instanceof NativeNode && !this.__benchMeter && destination===this.context.destination){
        const observer=meter(this.context);connect.call(this,observer);connect.call(observer,destination);
        return destination;
      }
      return connect.call(this,destination,...rest);
    };
    window.__latencyObserverContext=new AudioContext({sampleRate:48000});
    window.__latencyObserverReady=(async()=>{
      await window.__latencyObserverContext.audioWorklet.addModule(meterURL);
      await window.__latencyObserverContext.resume();
    })();
    const play=HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play=async function(){
      if(this.srcObject && !this.muted && !this.__meterAttached){
        this.__meterAttached=true;
        await window.__latencyObserverReady;
        const context=window.__latencyObserverContext;
        await play.call(this);
        const source=context.createMediaStreamSource(this.captureStream()),observer=meter(context),silent=context.createGain();
        silent.gain.value=0;
        source.connect(observer);observer.connect(silent);silent.connect(context.destination);
      }
      return play.call(this);
    };
    const NativePeer=window.RTCPeerConnection;
    window.RTCPeerConnection=class extends NativePeer{
      constructor(...args){super(...args);const create=this.createDataChannel.bind(this);
        this.createDataChannel=(...values)=>{const channel=create(...values);
          channel.addEventListener('message',({data})=>{let value;try{value=JSON.parse(data);}catch{return;}
            if(value.type==='bot-started-speaking' && window.__timing.botMarker===undefined) window.__timing.botMarker=performance.now();});
          return channel;};}
    };
  });
  let session;
  const receipts=[];
  page.on("response",async response=>{
    if(response.url().endsWith("/playback-events")) receipts.push({status:response.status(),receipt:response.request().postDataJSON()});
  });
  page.on("response",async r=>{if(r.url().endsWith(`/api/public/demos/${publicId}/sessions`) && r.status()===201) session=await r.json();});
  await page.goto(`/demo/${publicId}`);
  await page.evaluate(()=>window.__latencyObserverReady);
  await page.locator("#start-call").click();
  await expect.poll(()=>Boolean(session),{timeout:10000}).toBe(true);
  await expect(page.locator('[data-screen="live"]')).toBeVisible({timeout:20000});
  await expect.poll(()=>page.evaluate(()=>Number.isFinite(window.__timing.firstOutput)),{timeout:10000}).toBe(true);
  const timing=await page.evaluate(()=>window.__timing);
  writeFileSync(`${evidence}/timing-${process.env.VOICE_AGENT_TIMING_MODE || 'unknown'}.json`,JSON.stringify(timing,null,2));
  await page.locator('#end').click();
  expect(Number.isFinite(timing.botMarker)).toBe(true);
});
