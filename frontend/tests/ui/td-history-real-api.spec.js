import {test,expect} from '@playwright/test';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
const enabled=process.env.VOICE_AGENT_TD_LOCAL_RUNTIME==='1' && Boolean(process.env.VOICE_AGENT_TD_B_SEED_HISTORY);
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-history-real-api';
mkdirSync(evidence,{recursive:true});
test.skip(!enabled,'Requires a completed synthetic call in the disposable loopback app');
for(const width of [1440,390])test(`real history HTTP failure retries without losing persisted call at ${width}px`,async({page,request,baseURL})=>{
 expect(['127.0.0.1','localhost']).toContain(new URL(baseURL).hostname);
 expect((await request.get('/health')).headers()['x-voiceagent-test-fixture']).toBe('td-local-offline');
 const seed=JSON.parse(readFileSync(process.env.VOICE_AGENT_TD_B_SEED_HISTORY));
 await page.setViewportSize({width,height:1000});
 await page.addInitScript(()=>localStorage.setItem('voiceagent-td-locale','en'));
 await page.goto('/');await page.getByRole('button',{name:'Sessions',exact:true}).click();
 const row=page.locator('.history-row').filter({hasText:seed.id});await expect(row).toBeVisible();
 const actual503=[];
 page.on('response',response=>{
  if(new URL(response.url()).pathname==='/api/history' && response.status()===503)actual503.push(response.status());
 });
 const pattern='**/api/history?**';
 await page.route(pattern,route=>route.continue({headers:{...route.request().headers(),
  'X-VoiceAgent-Test-History-Failure':String(width)}}));
 await page.locator('#refresh-history').click();
 await expect(page.locator('#history-load-error')).toContainText('Local history temporarily unavailable');
 await expect(row).toBeVisible();expect(actual503).toHaveLength(1);
 await page.unroute(pattern);await page.locator('#refresh-history').click();
 await expect(page.locator('#history-load-error')).toBeHidden();await expect(row).toBeVisible();
 await page.locator('#history-from').fill('2099-01-01');await page.locator('#history-from').press('Tab');
 await expect(page.locator('.history-row')).toHaveCount(0);
 await expect(page.locator('#history-list')).toContainText('No calls recorded yet.');
 await page.locator('#history-from').fill('');await page.locator('#history-from').press('Tab');
 await expect(row).toBeVisible();await row.click();
 await expect(page.locator('#history-dialog')).toBeVisible();
 if(seed.metrics.some(metric=>metric.timing_ranges?.e2e)) {
  const interval=seed.metrics.find(metric=>metric.timing_ranges?.e2e).timing_ranges.e2e;
  const measured=page.locator(`#history-dialog .e2e-timing-range[data-response-id="${interval.response_id}"]`);
  await expect(measured).toBeVisible();
  await expect(measured).toContainText(`${Math.floor(interval.lower_ms*10)/10}–${Math.ceil(interval.upper_ms*10)/10} ms`);
  await expect(measured).toContainText('VAD speech-end source sample');
 }
 if(seed.td_events.some(event=>event.event==='identifier_echo_resource_failed')) {
  const turn=page.locator('#history-dialog .sample-turn').first();
  await turn.locator('details.turn-td > summary').click();
  await expect(turn.getByRole('heading',{name:'Audio resource failed',exact:true})).toBeVisible();
  await expect(turn.getByRole('heading',{name:'Echo preparation failed',exact:true})).toBeVisible();
  await page.locator('#td-history-language').selectOption('zh');
  await expect(turn.getByRole('heading',{name:'跟读准备失败',exact:true})).toBeVisible();
 }
 expect(await page.locator('#history-dialog').evaluate(node=>node.scrollWidth<=node.clientWidth)).toBe(true);
 const after=await (await request.get(`/api/history/${seed.id}`)).json();
 expect(after.metrics).toEqual(seed.metrics);expect(after.td_events).toEqual(seed.td_events);
 await page.screenshot({path:`${evidence}/real-history-recovered-${width}.png`,fullPage:true});
 writeFileSync(`${evidence}/real-history-recovery-${width}.json`,JSON.stringify({evidenceLevel:'local-real',
  actualHttp503:actual503.length,retry:true,dateFilterEmpty:true,metricsExact:true,eventsExact:true,
  boundary:'single bounded HTTP middleware fault in loopback fixture; successful API and SQLite unmodified'},null,2));
});
