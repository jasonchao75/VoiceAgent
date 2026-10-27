import {test,expect} from '@playwright/test';
test('browser clock sampler uses native fetch without losing its Window receiver',async({page})=>{
 let requests=0;
 await page.route('**/api/sessions/clock-fixture/playback-clock**',route=>{
  requests++;
  return route.fulfill({status:requests===1?201:204,contentType:'application/json',
   body:requests===1?JSON.stringify({sample_id:'b'.repeat(32)}):undefined});
 });
 await page.route('**/__clock-component',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><body></body>'}));
 await page.goto('/__clock-component');
 await page.evaluate(async unbound=>{
  const {RenderClockSampler}=await import('/src/td-render-clock.js');
  window.__clockErrors=[];
  let sampler;
  sampler=new RenderClockSampler({sessionId:'clock-fixture',token:'inert',clockId:'a'.repeat(32),sampleRate:48000,
   port:{postMessage:data=>sampler.observe({event:'clock_sample',sample_id:data.sample_id,render_frame:1024,render_sample_rate:48000})},
   ...(unbound?{fetcher:globalThis.fetch}:{}),
   onError:reason=>window.__clockErrors.push(reason)});
  window.__clockSampler=sampler;sampler.start();
 },process.env.VOICE_AGENT_TD_NATIVE_FETCH_UNBOUND==='1');
 try {
  await expect.poll(()=>requests,{timeout:3000}).toBe(2);
  expect(await page.evaluate(()=>window.__clockErrors)).toEqual([]);
 } finally {await page.evaluate(()=>window.__clockSampler.close());}
});
