import {test,expect} from '@playwright/test';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
const fixture=JSON.parse(readFileSync('../tests/ui/fixtures/voice-bot-editor.json'));
const catalog=JSON.parse(readFileSync('tests/ui/fixtures/td-catalog.json'));
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-validation-states';
mkdirSync(evidence,{recursive:true});
for(const language of ['en','zh']) for(const width of [1440,390]) test(`TD invalid drafts remain local at ${width}px ${language}`,async({page})=>{
 await page.setViewportSize({width,height:1000});
 await page.addInitScript(lang=>localStorage.setItem('voiceagent-td-locale',lang),language);
 const bot={...fixture.bots[0],turn_detection_source:'self_developed',td_config:{
  minimum_ms:600,maximum_ms:2500,final_wait_ms:300,alpha:.5,conflict_threshold:.8,
  vad:{confidence:.7,start_secs:.1,stop_secs:.15,min_volume:.6},
  jev:{endpoint:'https://api.typesafe.ai/v1/systemone',model:'jev-latest',timeout_seconds:.8,
   noul_instructions:'Yield?',choice_instructions:'State?',options:[
    {id:'complete',meaning:'Done',wait_ms:600},{id:'incomplete',meaning:'Continue',wait_ms:1500}]},
  priority_rule:{enabled:true,keywords:['identifier'],vocabulary:[{value:'1',aliases:['one']}],wpm_threshold:90,pause_ms:350,unit_gap_ms:50},
 }};
 const writes=[],states=[];
 await page.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;let data;
  if(path==='/api/catalogs')data=catalog;
  else if(path==='/api/bots')data=[bot];
  else if(path===`/api/bots/${bot.id}`){
   if(route.request().method()==='PUT'){const body=route.request().postDataJSON();writes.push(body);Object.assign(bot,body);}data=bot;
  }else if(path.endsWith('/echo-audio'))data={items:[],enabled:false};
  else if(path==='/api/auth/session')data={idle_expires_at:4000000000,absolute_expires_at:4000000000};
  else data={};
  return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('/');await page.locator('.bot-card').first().click();
 await page.getByRole('button',{name:'Advanced',exact:true}).click();await page.locator('#td-entry').click();
 async function invalid(name,selector,submit,error) {
  await page.locator(submit).click();const alert=page.locator(error);
  await expect(alert).toBeVisible();
  if(language==='zh')await expect(alert).toContainText(/[\u4e00-\u9fff]/);
  else await expect(alert).not.toContainText(/[\u4e00-\u9fff]/);
  expect(writes).toHaveLength(0);
  expect(await page.locator('#advanced-empty').evaluate(node=>node.scrollWidth<=node.clientWidth)).toBe(true);
  states.push({name,error:await alert.textContent(),draft:await page.locator(selector).inputValue(),writes:writes.length});
 }
 await page.locator('[data-td="rules"]').click();await page.locator('#keywords').fill('');
 await invalid('empty-keyword','#keywords','#td-form button[type="submit"]','#form-error');
 await expect(page.locator('#keywords')).toHaveValue('');await page.locator('#keywords').fill('identifier');
 await page.locator('.td-aliases').fill('one, ONE');
 await invalid('duplicate-alias','.td-aliases','#td-form button[type="submit"]','#form-error');
 await page.locator('.td-aliases').fill('one');await page.locator('[data-td="semantic"]').click();
 await page.locator('#minimum').fill('3000');
 await invalid('inverted-wait','#minimum','#td-form button[type="submit"]','#form-error');
 await page.locator('#minimum').fill('600');await page.locator('#open-jev').click();
 await page.locator('[data-jev="questions"]').click();const meaning=page.locator('.jev-option input').nth(1);
 await meaning.fill('');await invalid('empty-option','.jev-option input >> nth=1','#jev-form button[type="submit"]','#jev-error');
 await page.screenshot({path:`${evidence}/invalid-draft-${width}-${language}.png`,fullPage:true});
 await meaning.fill('Done');await page.locator('#jev-form button[type="submit"]').click();
 await expect.poll(()=>writes.length).toBe(1);expect(writes[0].td_config.minimum_ms).toBe(600);
 expect(writes[0].td_config.jev.noul_instructions).toBe('Yield?');
 expect(writes[0]).not.toHaveProperty('jev_api_key');
 writeFileSync(`${evidence}/invalid-drafts-${width}-${language}.json`,JSON.stringify({evidenceLevel:'fixture',states,validSave:true},null,2));
});
