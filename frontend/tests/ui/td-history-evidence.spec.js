import { expect, test } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

const fixture = JSON.parse(readFileSync(path.resolve("../tests/ui/fixtures/voice-bot-editor.json")));
const catalog = JSON.parse(readFileSync(path.resolve("tests/ui/fixtures/td-catalog.json")));
const evidence = path.resolve(process.env.VOICE_AGENT_TD_UI_EVIDENCE || "../test-results/td-history-evidence");
mkdirSync(evidence,{recursive:true});
test.beforeEach(async({page})=>{await page.addInitScript(()=>localStorage.setItem("voiceagent-td-locale","en"));});

for (const width of [1440, 390]) {
  test(`history keeps legacy playback unverified at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.route("**/api/**", async (route) => {
      const url = new URL(route.request().url());
      let response;
      if (url.pathname === "/api/catalogs") response = catalog;
      else if (url.pathname === "/api/bots") response = fixture.bots;
      else if (url.pathname === "/api/history") response = {
        items: fixture.history.items, total: fixture.history.items.length, limit: 25, offset: 0,
      };
      else if (url.pathname.startsWith("/api/history/")) response = fixture.history.detail;
      else if (url.pathname === "/api/auth/session") response = {
        idle_expires_at: 4000000000, absolute_expires_at: 4000000000,
      };
      else return route.fulfill({ status: 404, body: "{}" });
      return route.fulfill({ contentType: "application/json", body: JSON.stringify(response) });
    });
    await page.goto("/");
    await expect(page.locator(".bot-card").first()).toBeVisible();
    await page.getByRole("button", { name: "Sessions", exact: true }).click();
    await page.locator(".history-row").first().click();
    const dialog = page.locator("#history-dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.locator(".history-metric").first()).toContainText("unverified client report");
    const dimensions = await dialog.evaluate((element) => ({
      client: element.clientWidth, scroll: element.scrollWidth,
    }));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client);
    const originalText=await dialog.locator(".message p").allTextContents();
    await expect(dialog.locator("#td-history-language")).toBeVisible();
    await dialog.locator("#td-history-language").selectOption("zh");
    await expect(dialog.locator(".turn-td>summary").first()).toContainText("TD 判断记录");
    expect(await dialog.locator(".message p").allTextContents()).toEqual(originalText);
    await dialog.locator("#td-history-language").selectOption("en");
    await page.locator("#close-history").click();
    await page.locator(".history-row").first().click();
    await expect(dialog.locator("#td-history-language")).toHaveCount(1);
    expect(await dialog.locator(".message p").allTextContents()).toEqual(originalText);
    await page.screenshot({ path: path.join(evidence, `history-evidence-${width}.png`) });
  });
}

for (const width of [1440,390]) {
  test(`formal per-turn history preserves candidates and response versions at ${width}px`,async({page})=>{
    await page.setViewportSize({width,height:1000});
    const detail={...fixture.history.detail,td_events:[
      {event:"td_settings_snapshot",turn_id:null,minimum_ms:600,maximum_ms:2500,final_wait_ms:200,alpha:.5,jev_model:"fixture-model"},
      {event:"assistant_opening",text:"Advanced settings"},
      {event:"candidate_created",turn_id:7,candidate:1},
      {event:"speech_resumed",turn_id:7},
      {event:"candidate_created",turn_id:7,candidate:2},
      {event:"jev_result",turn_id:7,candidate:2,status:"ok",noul:.9,probabilities:{complete:.8,incomplete:.2}},
      {event:"jev_wait_calculated",turn_id:7,candidate:2,noul_ms:790,choice_ms:860,target_ms:825,remaining_ms:375,conflict:false},
      {event:"td_commit",turn_id:7,candidate:2,text:"12",source_final:false},
      {event:"conversation_utterance",turn_id:7,role:"user",text:"12",history_metric_index:0},
      {event:"conversation_utterance",turn_id:"7",role:"assistant",text:"Partial answer",response_id:"7:1"},
      {event:"conversation_utterance",turn_id:"7",role:"assistant",text:"Final answer",response_id:"7:2"},
      {event:"identifier_echo_scheduled",turn_id:7,text:"12",kind:"echo",playback_id:"echo-7"},
      {event:"playback_dispatched",playback_id:"echo-7",status:"sent_unknown"},
      {event:"playback_renderer_receipt",turn_id:7,response_id:"7:2",playback_id:"normal-7",
        renderer_event:"task_started",rendered_samples:128,render_frame:1024,
        render_sample_rate:24000,render_clock_id:"c".repeat(32),evidence_source:"audio_worklet_render"},
      {event:"candidate_created",turn_id:8,candidate:3},
      {event:"conversation_utterance",turn_id:8,role:"user",text:"<img src=x onerror=alert(1)>"},
      {event:"source_transcript",turn_id:7,text:"late original",source_revision:2},
      {event:"source_transcript",turn_id:7,text:"Priority rules",source_revision:3},
      {event:"source_transcript",turn_id:null,related_turn_ids:[7,8],text:"unassigned shared range"},
      {event:"unranged_transcript",turn_id:null,text:"UNRANGED snapshot evidence",stream_epoch:1,normalized_segment_count:1,raw_frame_kind:"InterimTranscriptionFrame",reason:"source_audio_range_unavailable"},
    ]};
    await page.route("**/api/**",async route=>{
      const url=new URL(route.request().url());let response;
      if(url.pathname==="/api/catalogs") response=catalog;
      else if(url.pathname==="/api/bots") response=fixture.bots;
      else if(url.pathname==="/api/history") response={items:fixture.history.items,total:fixture.history.items.length,limit:25,offset:0};
      else if(url.pathname.startsWith("/api/history/")) response=detail;
      else if(url.pathname==="/api/auth/session") response={idle_expires_at:4000000000,absolute_expires_at:4000000000};
      else return route.fulfill({status:404,body:"{}"});
      return route.fulfill({contentType:"application/json",body:JSON.stringify(response)});
    });
    await page.goto("/");
    await page.getByRole("button",{name:"Sessions",exact:true}).click();
    await page.locator(".history-row").first().click();
    const dialog=page.locator("#history-dialog");
    await expect(dialog.locator(".sample-turn")).toHaveCount(2);
    const original=dialog.locator('[data-turn-id="7"]');
    await expect(original.locator(".turn-td>summary")).toHaveText("TD decisions · 2 attempts");
    await expect(original).toContainText("Partial answer");
    await expect(original).toContainText("Final answer");
    await expect(original).toContainText("Sent · playback unconfirmed");
    await expect(original.locator(".history-metric")).toContainText("unverified client report");
    await original.locator(".turn-td").evaluate(node=>{node.open=true;});
    await expect(original).toContainText("Attempt 1 · cancelled");
    await expect(original.getByText("Target silence (ms)",{exact:true})).toBeVisible();
    await expect(original.getByText("825",{exact:true})).toBeVisible();
    await expect(original).toContainText("late original");
    await expect(original.getByText("Render frame",{exact:true})).toBeVisible();
    await expect(original.getByText("1024",{exact:true})).toBeVisible();
    await expect(dialog.locator('[data-turn-id="8"]')).not.toContainText("late original");
    await expect(original).not.toContainText("UNRANGED snapshot evidence");
    await expect(dialog.locator('[data-turn-id="8"]')).not.toContainText("UNRANGED snapshot evidence");
    await expect(dialog.getByText("Transcript without proven range",{exact:true})).toHaveCount(1);
    await expect(dialog.locator("img")).toHaveCount(0);
    await expect(dialog.getByText("Session evidence without turn attribution",{exact:true})).toBeVisible();
    await dialog.getByLabel("Jump to turn").selectOption("8");
    expect(await dialog.evaluate(node=>{
      const box=node.getBoundingClientRect();
      return Boolean(document.elementFromPoint(box.left+100,box.top+5)?.closest(".history-dialog-header"));
    })).toBe(true);
    const dimensions=await dialog.evaluate(node=>({client:node.clientWidth,scroll:node.scrollWidth}));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client);
    const literalValues=()=>dialog.locator(".message p,.td-record dd").allTextContents();
    const before=await literalValues();
    await expect(dialog.locator("#td-history-language")).toBeVisible();
    await dialog.locator("#td-history-language").selectOption("zh");
    await expect(original.locator(".turn-td>summary")).toContainText("TD 判断记录");
    await expect(original).toContainText("候选 1 · 已取消");
    expect(await literalValues()).toEqual(before);
    await expect(original.getByText("目标静音（ms）",{exact:true})).toHaveCount(1);
    await dialog.evaluate(node=>{node.scrollTop=0;});
    await page.screenshot({path:path.join(evidence,`history-turns-zh-${width}.png`)});
    await dialog.locator("#td-history-language").selectOption("en");
    await expect(original.locator(".turn-td>summary")).toHaveText("TD decisions · 2 attempts");
    expect(await literalValues()).toEqual(before);
    await page.screenshot({path:path.join(evidence,`history-turns-${width}.png`)});
  });
}

for (const width of [1440,390]) {
  for (const kind of ['incomplete','overflow']) {
    test(`unsubmitted ${kind} identifier remains visible after refresh at ${width}px`,async({page})=>{
      await page.setViewportSize({width,height:1000});
      const text=kind==='overflow'?'The identifier is too long.':'Please complete the identifier.';
      const detail={...fixture.history.detail,turns:[],metrics:[],td_events:[
        {event:'assistant_opening',turn_id:null,text:'Please say your identifier.'},
        {event:'identifier_local_processed',turn_id:1,text:'one two three',collected:'123'},
        {event:'identifier_reminder',turn_id:1,text,collected:'123',kind},
        {event:'playback_task_prepared',turn_id:1,playback_id:'reminder-1',kind},
        {event:'playback_renderer_receipt',turn_id:1,playback_id:'reminder-1',renderer_event:'task_finished',rendered_samples:24000},
      ]};
      await page.route('**/api/**',async route=>{
        const url=new URL(route.request().url());let body;
        if(url.pathname==='/api/catalogs')body=catalog;
        else if(url.pathname==='/api/bots')body=fixture.bots;
        else if(url.pathname==='/api/history')body={items:fixture.history.items,total:fixture.history.items.length,limit:25,offset:0};
        else if(url.pathname.startsWith('/api/history/'))body=detail;
        else if(url.pathname==='/api/auth/session')body={idle_expires_at:4000000000,absolute_expires_at:4000000000};
        else return route.fulfill({status:404,body:'{}'});
        return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
      });
      await page.goto('/');
      await page.reload();
      await page.getByRole('button',{name:'Sessions',exact:true}).click();
      await page.locator('.history-row').first().click();
      const dialog=page.locator('#history-dialog'),turn=dialog.locator('[data-turn-id="1"]');
      await expect(turn).toHaveCount(1);
      await expect(turn).toContainText('one two three');
      await expect(turn).toContainText(text);
      await expect(turn.locator('.td-badge')).toHaveText('rule processed');
      await expect(turn.locator('.history-metric')).toContainText('make no LLM request');
      await turn.locator('.turn-td').evaluate(node=>node.open=true);
      await expect(turn).toContainText('123');
      await expect(turn).toContainText('task_finished');
      await expect(dialog.locator('.message p').first()).toHaveText('Please say your identifier.');
      const before=await turn.locator('.message p,.td-record dd').allTextContents();
      await dialog.locator('#td-history-language').selectOption('zh');
      expect(await turn.locator('.message p,.td-record dd').allTextContents()).toEqual(before);
      expect(await dialog.evaluate(node=>node.scrollWidth<=node.clientWidth)).toBe(true);
      await page.screenshot({path:path.join(evidence,`identifier-${kind}-${width}.png`),fullPage:true});
    });
  }
}
