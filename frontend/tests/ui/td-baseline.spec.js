import {test, expect} from '@playwright/test';
import {mkdirSync, readFileSync, writeFileSync} from 'node:fs';

const frozen = readFileSync('../openspec/changes/archive/2026-10-27-add-jev-semantic-turn-detection/prototypes/index.html', 'utf8');
const fixture = JSON.parse(readFileSync('../tests/ui/fixtures/voice-bot-editor.json'));
const catalog = JSON.parse(readFileSync('tests/ui/fixtures/td-catalog.json'));
const evidence = process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-baseline-evidence';
mkdirSync(evidence,{recursive:true});
const decisions = readFileSync('../openspec/changes/archive/2026-10-27-add-jev-semantic-turn-detection/decisions/decision-log.md', 'utf8');
const keySaveDecision = decisions.match(/^### D-056\b[\s\S]*?(?=^### |$(?![\s\S]))/m)?.[0] || '';

async function state(page, name) {
  if (name.startsWith('jev-')) {
    if (!(await page.locator('#jev-back').isVisible())) {
      await page.locator('[data-td="semantic"]').click();
      await page.locator('#open-jev').click();
    }
    await page.locator(`[data-jev="${name.slice(4)}"]`).click();
  } else {
    if (await page.locator('#jev-back').isVisible()) await page.locator('#jev-back').click();
    await page.locator(`[data-td="${name}"]`).click();
  }
}

async function signature(page, name) {
  const selector = name.startsWith('jev-') ? '.advanced-empty:has(#jev-back)' : '#td';
  return page.locator(selector).evaluate(root => {
    const visible = node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
    const controls = [...root.querySelectorAll('input,select,textarea')].filter(visible);
    return {
      overflow:[root, ...root.querySelectorAll('fieldset,.td-grid,.vocab-gap,.jev-option')]
        .filter(node=>visible(node) && node.scrollWidth > node.clientWidth + 1)
        .map(node=>node.id || node.className),
      unnamed:controls.filter(node=>!node.labels?.length && !node.getAttribute('aria-label') && !node.getAttribute('aria-labelledby'))
        .map(node=>node.id || node.type),
      controls:controls.map(node=>{
        const style = getComputedStyle(node);
        return {id:node.id || `anonymous:${controls.filter(item=>!item.id).indexOf(node)}`, type:node.type, fontSize:style.fontSize, color:style.color,
          background:style.backgroundColor, radius:style.borderRadius,
          width:Math.round(node.getBoundingClientRect().width)};
      }),
    };
  });
}

for (const language of ['zh', 'en']) for (const width of [1440, 390]) {
  test(`Checkpoint A compares production settings to frozen v0.14 at ${width}px ${language}`, async ({page, context}) => {
    await page.addInitScript(language => localStorage.setItem('voiceagent-td-locale', language), language);
    await page.setViewportSize({width, height:1000});
    const baseline = await context.newPage();
    await baseline.setViewportSize({width, height:1000});
    await baseline.route('**/__frozen-v014', route=>route.fulfill({contentType:'text/html', body:frozen}));
    await baseline.goto('http://127.0.0.1:5177/__frozen-v014');
    const td = await baseline.evaluate(()=>{
      const value=id=>document.getElementById(id).value;
      const number=id=>Number(value(id));
      return {minimum_ms:number('minimum'), maximum_ms:number('maximum'), final_wait_ms:number('final-wait'),
        alpha:number('fusion-alpha'), conflict_threshold:number('conflict-high'),
        vad:{confidence:number('confidence'), start_secs:number('vad-start')/1000,
          stop_secs:number('vad-stop')/1000, min_volume:number('volume')},
        jev:{endpoint:value('jev-endpoint'), model:value('jev-model'), timeout_seconds:number('jev-timeout')/1000,
          noul_instructions:value('jev-yield-instructions'), choice_instructions:value('jev-state-instructions'),
          options:[...document.querySelectorAll('#jev-options .jev-option')].map(row=>{
            const inputs=row.querySelectorAll('input');
            return {id:inputs[0].value, meaning:inputs[1].value, wait_ms:Number(inputs[2].value)};
          })},
        priority_rule:{enabled:true, keywords:value('keywords').split('\n'),
          vocabulary:[...document.querySelectorAll('#mappings .td-mapping')].map(row=>{
            const inputs=row.querySelectorAll('input');
            return {value:inputs[1].value, aliases:inputs[0].value.split(',').map(v=>v.trim())};
          }), wpm_threshold:number('wpm'), pause_ms:number('echo-pause'), unit_gap_ms:number('echo-gap'),
          collection:{target_length:number('number-length'), timeout_ms:number('collection-timeout'),
            overflow_pause_ms:number('echo-pause'), incomplete_text:value('collection-message'), overflow_text:value('overflow-message')}}};
    });
    const bot = {...fixture.bots[0], turn_detection_source:'self_developed', td_config:td};
    await page.route('**/api/**', async route=>{
      const path = new URL(route.request().url()).pathname;
      let data;
      if (path === '/api/catalogs') data = catalog;
      else if (path === '/api/auth/session') data = {idle_expires_at:4000000000,absolute_expires_at:4000000000};
      else if (path === '/api/bots') data = [bot];
      else if (path === `/api/bots/${bot.id}`) data = bot;
      else if (path.endsWith('/echo-audio')) data = {items:[],enabled:false};
      else return route.fulfill({status:404,body:'{}'});
      return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
    });
    await page.goto('/');
    await page.locator('.bot-card').first().click();
    await page.getByRole('button',{name:'Advanced',exact:true}).click();
    await page.locator('#td-entry').click();
    const results = [];
    for (const name of ['rules','semantic','vad','jev-connection','jev-questions','jev-preview']) {
      await state(baseline, name); await state(page, name);
      if (name === 'jev-preview') {
        await baseline.locator('#policy-calculate').click();
        await page.locator('#policy-calculate').click();
        await expect(page.locator('#policy-result')).toContainText('825');
      }
      const before = await signature(baseline, name), after = await signature(page, name);
      results.push({name, baseline:before, production:after});
      const selector = name.startsWith('jev-') ? '.advanced-empty:has(#jev-back)' : '#td';
      if (language === 'en') {
        const copy = await page.locator(selector).locator('h3:visible,p.hint:visible,p.jev-help:visible').allTextContents();
        expect.soft(copy.join('\n'), `${name} static English copy`).not.toMatch(/\p{Script=Han}/u);
      }
      await baseline.locator(selector).screenshot({path:`${evidence}/baseline-${name}-${width}-${language}.png`});
      await page.locator(selector).screenshot({path:`${evidence}/formal-${name}-${width}-${language}.png`});
      writeFileSync(`${evidence}/baseline-comparison-${width}-${language}.json`,JSON.stringify(results,null,2));
      expect(after.overflow, name).toEqual([]);
      expect(after.unnamed, name).toEqual([]);
      if (name === 'jev-connection') {
        // D-056 approves exactly this extra control, without rewriting the frozen HTML.
        expect(keySaveDecision).toContain('- Status: Confirmed');
        expect(keySaveDecision).toContain('A：保留保存Key复选框（推荐）');
        const keySave = page.locator('#jev-save-key');
        await expect(keySave).not.toBeChecked();
        await expect(keySave).toHaveAccessibleName(/为此\s*Bot\s*保存\s*API|Save API key for this Bot/i);
        expect(after.controls.filter(control => control.id === 'jev-save-key')).toHaveLength(1);
        expect.soft(after.controls.filter(control => control.id !== 'jev-save-key'), name).toEqual(before.controls);
      } else expect.soft(after.controls, name).toEqual(before.controls);
    }
    await baseline.close();
  });
}
