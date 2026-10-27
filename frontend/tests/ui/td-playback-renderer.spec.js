import { readFileSync } from "node:fs";
const packet=JSON.parse(readFileSync("tests/ui/fixtures/td-task-wire.json"));
import { test, expect } from "@playwright/test";

test("production renderer confirms a tagged PCM task from the actual AudioWorklet", async ({page}) => {
  await page.route("**/api/**",route=>route.fulfill({status:503,body:"{}"}));
  await page.goto("/");
  await page.locator("body").click({position:{x:200,y:90}});
  const events=await page.evaluate(async({wire,playback_id,interruption_wire})=>{
    const {TaskMediaManager,TaskWebSocketSerializer}=await import("/src/td-playback.js");
    const observed=[];
    let finish, echoStarted, echoStopped;
    const echoStart = new Promise(resolve=>{echoStarted=resolve;});
    const echoStop = new Promise(resolve=>{echoStopped=resolve;});
    const finished=new Promise(resolve=>{finish=resolve;});
    const manager=new TaskMediaManager(undefined,16000,event=>{
      observed.push(event);
      if(event.event==="task_finished") finish();
      if(event.playback_id==="local-echo" && event.event==="task_started") echoStarted();
      if(event.playback_id==="local-echo" && event.event==="task_stopped") echoStopped();
    });
    try {
      await manager._wavStreamPlayer.connect();
      const serializer=new TaskWebSocketSerializer(manager);
      const parsed=await serializer.deserialize(new Blob([Uint8Array.from(atob(wire),char=>char.charCodeAt(0))]));
      manager.bufferBotAudio(parsed.audio);
      manager.control({event:"task_end",playback_id});
      await Promise.race([finished,new Promise((_,reject)=>setTimeout(()=>reject(new Error("No render acknowledgement")),3000))]);
      manager.pendingIdentity={playback_id:"local-echo",kind:"echo",response_id:null};
      manager.bufferBotAudio(new Int16Array(48000).fill(8192));
      await Promise.race([echoStart,new Promise((_,reject)=>setTimeout(()=>reject(new Error("No echo start")),3000))]);
      const interruption=await serializer.deserialize(new Blob([Uint8Array.from(atob(interruption_wire),char=>char.charCodeAt(0))]));
      if (interruption.type!=="raw") throw new Error("Untargeted native interruption escaped serial task controls");
      await manager.userStartedSpeaking();
      manager.control({event:"stop_task",playback_id:"local-echo",request_id:"explicit-clear"});
      await Promise.race([echoStop,new Promise((_,reject)=>setTimeout(()=>reject(new Error("No stop acknowledgement")),3000))]);
      manager.pendingIdentity={playback_id:"local-echo",kind:"echo",response_id:null};
      if (manager.bufferBotAudio(new Int16Array([8192])).length !== 0) throw new Error("Stopped task reentered");
      manager.control({event:"stop_task",playback_id:"never-render",request_id:"early-stop"});
      manager.pendingIdentity={playback_id:"never-render",kind:"normal",response_id:"turn:3"};
      if (manager.bufferBotAudio(new Int16Array([8192])).length !== 0) throw new Error("Early stop lost");
      await manager.disconnect();
      manager.pendingIdentity={playback_id:"after-disconnect",kind:"normal",response_id:"turn:4"};
      if(manager.bufferBotAudio(new Int16Array([8192])).length !== 0) throw new Error("Disconnected renderer reopened");
      return observed;
    } finally { await manager._wavStreamPlayer.context?.close(); }
  },packet);
  expect(events.map(event=>event.event)).toEqual(["task_started","task_finished","task_started","task_stopped"]);
  expect(events[0].playback_id).toBe(packet.playback_id);
  expect(events[1].rendered_samples).toBe(2400);
  expect(events[0].render_frame).toBeGreaterThanOrEqual(0);
  expect(events[0].render_sample_rate).toBe(24000);
  expect(events[0].render_clock_id).toMatch(/^[a-f0-9]{32}$/);
  expect(events[1].render_clock_id).toBe(events[0].render_clock_id);
  expect(events[1].render_frame-events[0].render_frame).toBe(2400);

  expect(events[1].evidence_source).toBe("audio_worklet_render");
  expect(events[3].request_id).toBe("explicit-clear");
  expect(events[3].rendered_samples).toBeGreaterThan(0);
  expect(events[3].rendered_samples).toBeLessThan(48000);
});
