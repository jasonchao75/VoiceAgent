import { test, expect } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || "../test-results/td-settings-evidence";
mkdirSync(evidence,{recursive:true});
const fixture = JSON.parse(readFileSync("../tests/ui/fixtures/voice-bot-editor.json"));
const catalog = JSON.parse(readFileSync("tests/ui/fixtures/td-catalog.json"));
test.beforeEach(async({page})=>{await page.addInitScript(()=>localStorage.setItem("voiceagent-td-locale","en"));});

test("formal Advanced edits and saves explicit TD settings", async ({ page }) => {
  let saved, holdSave = false, finishSave;
  const bot = { ...fixture.bots[0], turn_detection_source: "self_developed", td_config: {
    minimum_ms: 600, maximum_ms: 2500, final_wait_ms: 300, alpha: .5, conflict_threshold: .8,
    vad: { confidence: .7, start_secs: .1, stop_secs: .15, min_volume: .6 },
    jev: { endpoint: "https://api.typesafe.ai/v1/systemone", model: "jev-latest", timeout_seconds: .8,
      noul_instructions: "Yield?", choice_instructions: "State?",
      options: [{id:"complete",meaning:"Done",wait_ms:600},{id:"incomplete",meaning:"Continue",wait_ms:1500}] },
    priority_rule: {enabled:false,keywords:["编号"],vocabulary:[{value:"1",aliases:["one"]}],wpm_threshold:90,pause_ms:350,unit_gap_ms:50},
  }};
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    let data;
    if (url.pathname === "/api/catalogs") data = catalog;
    else if (url.pathname === "/api/auth/session") data = {idle_expires_at:4000000000,absolute_expires_at:4000000000};
    else if (url.pathname === "/api/bots") data = [bot];
    else if (url.pathname === `/api/bots/${bot.id}` && route.request().method() === "PUT") {
      saved = route.request().postDataJSON(); Object.assign(bot, saved); data = bot;
      if (holdSave) await new Promise(resolve=>{finishSave=resolve;});
    } else if (url.pathname === `/api/bots/${bot.id}`) data = bot;
    else if (url.pathname.endsWith("/echo-audio")) data = {items:[],enabled:false};
    else return route.fulfill({status:404,body:"{}"});
    return route.fulfill({contentType:"application/json",body:JSON.stringify(data)});
  });
  await page.goto("/");
  await page.locator(".bot-card").first().click();
  await page.getByRole("button",{name:"Advanced",exact:true}).click();
  await page.locator("#td-entry").click();
  await page.locator('[data-td="semantic"]').click();
  await expect(page.locator("#minimum")).toHaveValue("600");
  await expect(page.locator('#td-entry')).toHaveAttribute('aria-current', 'page');
  await expect(page.locator('[data-td="semantic"]')).toHaveAttribute('aria-pressed', 'true');
  await page.locator('[data-td="vad"]').focus();
  await page.keyboard.press('Space');
  await expect(page.locator('[data-td="vad"]')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('[data-td="semantic"]')).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('[data-pane="vad"]')).toBeVisible();
  await page.locator('[data-td="semantic"]').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('[data-td="semantic"]')).toHaveAttribute('aria-pressed', 'true');

  const grid = page.locator('[data-pane="semantic"] .td-grid').first();
  await expect.poll(() => grid.evaluate(node => getComputedStyle(node).gridTemplateColumns.split(" ").length)).toBe(2);
  await page.locator("#minimum").fill("650");
  await page.getByRole('button', {name:'Bot settings', exact:true}).click();
  await page.locator('.pipeline-card[data-component="asr"]').click();
  await page.locator('#bot-turn-source').selectOption('provider_native');
  await page.getByRole('button', {name:'Collapse component drawer', exact:true}).click();
  await page.getByRole('button', {name:'Advanced', exact:true}).click();
  await expect(page.locator('#td-entry')).toBeHidden();
  await expect(page.locator('#td-general')).toBeVisible();
  await page.getByRole('button', {name:'Bot settings', exact:true}).click();
  await page.locator('.pipeline-card[data-component="asr"]').click();
  await page.locator('#bot-turn-source').selectOption('self_developed');
  await page.getByRole('button', {name:'Collapse component drawer', exact:true}).click();
  await page.getByRole('button', {name:'Advanced', exact:true}).click();
  await page.locator('#td-entry').click();
  await expect(page.locator('#minimum')).toHaveValue('650');

  await page.getByRole("button",{name:"Save TD settings",exact:true}).click();
  await expect.poll(()=>saved?.td_config?.minimum_ms).toBe(650);
  expect(saved.td_config.priority_rule.vocabulary[0].aliases).toEqual(["one"]);
  expect(saved.td_config.jev.noul_instructions).toBe("Yield?");
  expect(saved.td_config.jev.max_calls).toBe(100);
  await expect(page.getByLabel("Jev session call limit", {exact:true})).toHaveCount(0);
  await page.locator("#open-jev").click();
  await page.locator('[data-jev="preview"]').click();
  await page.locator("#jev-refresh-preview").click();
  const preview = JSON.parse(await page.locator("#jev-request-preview").textContent());
  expect(preview.state.transcript_status).toBe("Partial");
  expect(preview.questions.speech_state.criteria).toEqual({complete:"Done",incomplete:"Continue"});
  expect(preview.questions.speech_state.wait_ms).toBeUndefined();
  expect(preview).not.toHaveProperty("api_key");
  await page.locator('[data-jev="questions"]').click();
  await page.locator("#jev-add-option").click();
  const added = page.locator("#jev-options .jev-option").last();
  await added.getByLabel("Option identifier").fill("holding_floor");
  await added.getByLabel("Option meaning").fill("Waiting");
  await added.getByLabel("Option total wait").fill("2000");
  await added.getByLabel("Option total wait").blur();
  await page.locator('[data-jev="preview"]').click();
  await expect(page.locator("#sim-distribution input")).toHaveCount(3);
  await page.locator("#policy-calculate").click();
  await expect(page.locator("#policy-result")).toContainText("Target silence");
  await page.locator("#jev-back").click();
  await page.locator("#minimum").fill("675");
  holdSave = true;
  await page.getByRole("button",{name:"Save TD settings",exact:true}).click();
  await expect.poll(()=>Boolean(finishSave)).toBe(true);
  await page.locator("#minimum").fill("700");
  finishSave();
  await expect(page.locator("#save-state")).toContainText("newer edits unsaved");
  await expect(page.locator("#minimum")).toHaveValue("700");
  holdSave = false;
  await page.getByRole("button",{name:"Save TD settings",exact:true}).click();
  await expect.poll(()=>saved?.td_config?.minimum_ms).toBe(700);
  await expect(page.locator("#save-state")).toHaveText("Saved");
  await page.locator("#open-jev").click();
  await page.locator('[data-jev="preview"]').click();
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    await expect.poll(async () => page.locator("#advanced-empty").evaluate(node=>node.scrollWidth-node.clientWidth)).toBeLessThanOrEqual(0);
    await page.screenshot({path:`${evidence}/jev-preview-${width}.png`});
  }
});

test('number completeness disabled fields load, toggle and save as null on the formal route',async({page},info)=>{
 if(info.project.name==='narrow-chromium')await page.setViewportSize({width:390,height:844});
 let saved;
 const bot={...fixture.bots[0],turn_detection_source:'self_developed',td_config:{
  minimum_ms:600,maximum_ms:2500,final_wait_ms:200,alpha:.5,conflict_threshold:.8,
  vad:{confidence:.7,start_secs:.1,stop_secs:.15,min_volume:.6},
  jev:{endpoint:'https://api.typesafe.ai/v1/systemone',model:'jev-latest',timeout_seconds:.8,
   noul_instructions:'Yield?',choice_instructions:'State?',options:[{id:'complete',meaning:'Done',wait_ms:600},{id:'incomplete',meaning:'Continue',wait_ms:1500}]},
  priority_rule:{enabled:true,keywords:['number'],vocabulary:[{value:'1',aliases:['one']}],
   wpm_threshold:90,pause_ms:350,unit_gap_ms:50,collection:null}}};
 await page.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;
  let data;
  if(path==='/api/catalogs')data=catalog;
  else if(path==='/api/auth/session')data={idle_expires_at:4000000000,absolute_expires_at:4000000000};
  else if(path==='/api/bots')data=[bot];
  else if(path===`/api/bots/${bot.id}`){
   if(route.request().method()==='PUT'){saved=route.request().postDataJSON();Object.assign(bot,saved);}
   data=bot;
  }else if(path.endsWith('/echo-audio'))data={items:[],enabled:false};
  else return route.fulfill({status:404,body:'{}'});
  return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('/');await page.locator('.bot-card').first().click();
 await page.getByRole('button',{name:'Advanced',exact:true}).click();
 await page.locator('#td-entry').click();await page.locator('[data-td="rules"]').click();
 const fields=['number-length','collection-timeout','collection-message','overflow-message'];
 for(const id of fields)await expect(page.locator('#'+id)).toBeDisabled();
 await page.locator('#collection-enabled').check();
 for(const id of fields)await expect(page.locator('#'+id)).toBeEnabled();
 await page.locator('#number-length').fill('16');await page.locator('#collection-timeout').fill('8000');
 await page.locator('#collection-message').fill('Please complete your number.');
 await page.locator('#overflow-message').fill('Please check your number.');
 await page.getByRole('button',{name:'Save TD settings',exact:true}).click();
 await expect.poll(()=>saved?.td_config?.priority_rule?.collection?.target_length).toBe(16);
 await page.locator('#collection-enabled').uncheck();
 for(const id of fields)await expect(page.locator('#'+id)).toBeDisabled();
 await page.getByRole('button',{name:'Save TD settings',exact:true}).click();
 await expect.poll(()=>saved?.td_config?.priority_rule?.collection).toBe(null);
 await page.reload();await page.locator('.bot-card').first().click();
 await page.getByRole('button',{name:'Advanced',exact:true}).click();await page.locator('#td-entry').click();
 await page.locator('[data-td="rules"]').click();
 for(const id of fields)await expect(page.locator('#'+id)).toBeDisabled();
 expect(await page.locator('#td').evaluate(node=>node.scrollWidth<=node.clientWidth)).toBe(true);
 await page.screenshot({path:`${evidence}/collection-disabled-${info.project.name}.png`});
});
