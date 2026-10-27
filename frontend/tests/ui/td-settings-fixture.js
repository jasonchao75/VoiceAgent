import {readFileSync} from 'node:fs';
const frozen=readFileSync('../openspec/changes/archive/2026-10-27-add-jev-semantic-turn-detection/prototypes/index.html','utf8');
const fixture=JSON.parse(readFileSync('../tests/ui/fixtures/voice-bot-editor.json'));
const catalog=JSON.parse(readFileSync('tests/ui/fixtures/td-catalog.json'));

export async function openTDSettings(page,context,{width=1440,language='en',baseline=true}={}) {
  await page.setViewportSize({width,height:1000});
  await page.addInitScript(lang=>localStorage.setItem('voiceagent-td-locale',lang),language);
  let reference;
  if(baseline) {
    reference=await context.newPage();await reference.setViewportSize({width,height:1000});
    await reference.route('**/__frozen-v014',route=>route.fulfill({contentType:'text/html',body:frozen}));
    await reference.goto('http://127.0.0.1:5177/__frozen-v014');
    await reference.locator('#td-language').selectOption(language);
    await reference.locator('[data-td="rules"]').click();
  }
  const vocabulary=reference?await reference.locator('#mappings .td-mapping').evaluateAll(rows=>rows.map(row=>({
    aliases:row.querySelectorAll('input')[0].value.split(',').map(value=>value.trim()),
    value:row.querySelectorAll('input')[1].value,
  }))):[{aliases:['one','一','1'],value:'1'}];
  const bot={...fixture.bots[0],turn_detection_source:'self_developed',td_config:{
    minimum_ms:600,maximum_ms:2500,final_wait_ms:200,alpha:.5,conflict_threshold:.8,
    vad:{confidence:.7,start_secs:.1,stop_secs:.15,min_volume:.6},
    jev:{endpoint:'https://api.typesafe.ai/v1/systemone',model:'jev-latest',timeout_seconds:.8,
      noul_instructions:'Yield?',choice_instructions:'State?',options:[
        {id:'complete',meaning:'Done',wait_ms:600},{id:'incomplete',meaning:'Continue',wait_ms:1500}]},
    priority_rule:{enabled:true,keywords:['identifier'],vocabulary,wpm_threshold:90,pause_ms:350,unit_gap_ms:50,
      collection:{target_length:16,timeout_ms:8000,overflow_pause_ms:350,
        incomplete_text:'Please complete the number.',overflow_text:'Please check the number.'}},
  }};
  const writes=[];
  await page.route('**/api/**',route=>{
    const path=new URL(route.request().url()).pathname;let data;
    if(path==='/api/catalogs')data=catalog;
    else if(path==='/api/auth/session')data={idle_expires_at:4000000000,absolute_expires_at:4000000000};
    else if(path==='/api/bots')data=[bot];
    else if(path===`/api/bots/${bot.id}`){
      if(route.request().method()==='PUT'){const payload=route.request().postDataJSON();writes.push(payload);Object.assign(bot,payload);}
      data=bot;
    }else if(path.endsWith('/echo-audio'))data={items:[],enabled:false};
    else if(path==='/api/history')data={items:fixture.history.items,total:fixture.history.items.length,limit:25,offset:0};
    else if(path.startsWith('/api/history/'))data=fixture.history.detail;
    else return route.fulfill({status:404,body:'{}'});
    return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.goto('/');await page.locator('.bot-card').first().click();
  await page.getByRole('button',{name:'Advanced',exact:true}).click();await page.locator('#td-entry').click();
  await page.locator('[data-td="rules"]').click();
  return {reference,bot,writes};
}
