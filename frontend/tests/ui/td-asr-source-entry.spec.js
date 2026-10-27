import {test,expect} from '@playwright/test';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
const fixture=JSON.parse(readFileSync('../tests/ui/fixtures/voice-bot-editor.json'));
const catalog=JSON.parse(readFileSync('tests/ui/fixtures/td-catalog.json'));
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-asr-source-entry';
mkdirSync(evidence,{recursive:true});
const models=[['deepgram','flux-general-en'],['deepgram','flux-general-multi'],['deepgram','nova-3'],
 ['speechmatics','enhanced'],['soniox','stt-rt-v5'],['assemblyai','universal-3-5-pro']];
for(const width of [1440,390]) test(`six catalog ASR models expose only valid TD entries at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:1000});
 await page.addInitScript(()=>localStorage.setItem('voiceagent-td-locale','en'));
 await page.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;
  const data=path==='/api/catalogs'?catalog:path==='/api/bots'?fixture.bots:
   path.startsWith('/api/bots/')?fixture.bots[0]:path==='/api/auth/session'?{idle_expires_at:4000000000,absolute_expires_at:4000000000}:{};
  return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('/');await page.locator('.bot-card').first().click();
 const results=[];
 for(const [provider,model] of models) {
  await page.getByRole('button',{name:'Bot settings',exact:true}).click();
  await page.locator('.pipeline-card[data-component="asr"]').click();
  await page.locator('#bot-asr').selectOption(provider);
  await page.locator('#bot-asr-model').selectOption(model);
  const definition=catalog.asr_providers.providers.find(item=>item.id===provider).models.find(item=>item.id===model);
  const enabled=await page.locator('#bot-turn-source').evaluate(select=>[...select.options].filter(option=>!option.disabled).map(option=>option.value));
  expect(enabled.sort()).toEqual([...definition.turn_sources].sort());
  await page.locator('#bot-turn-source').selectOption('self_developed');
  expect(await page.locator('.component-drawer').evaluate(node=>node.scrollWidth<=node.clientWidth)).toBe(true);
  await page.screenshot({path:`${evidence}/source-${model}-${width}.png`,fullPage:true});
  if(results.length===0){
   await page.keyboard.press('Escape');await expect(page.locator('.component-drawer')).toBeHidden();
  }else await page.getByRole('button',{name:'Collapse component drawer',exact:true}).click();
  await page.getByRole('button',{name:'Advanced',exact:true}).click();
  await expect(page.locator('#td-entry')).toBeVisible();await page.locator('#td-entry').click();
  await page.locator('[data-td="semantic"]').click();
  if(results.length===0) await page.locator('#minimum').fill('650');
  else await expect(page.locator('#minimum')).toHaveValue('650');
  await page.getByRole('button',{name:'Bot settings',exact:true}).click();
  await page.locator('.pipeline-card[data-component="asr"]').click();
  const other=definition.turn_sources.find(value=>value!=='self_developed');
  await page.locator('#bot-turn-source').selectOption(other);
  await page.getByRole('button',{name:'Collapse component drawer',exact:true}).click();
  await page.getByRole('button',{name:'Advanced',exact:true}).click();
  await expect(page.locator('#td-entry')).toBeHidden();await expect(page.locator('#td-general')).toBeVisible();
  results.push({provider,model,enabled,selfEntry:true,nativeOrOffHidesEntry:true,retainedDraft:true});
 }
 writeFileSync(`${evidence}/six-source-entries-${width}.json`,JSON.stringify({evidenceLevel:'fixture',vendorCompatibilityProven:false,results},null,2));
});
