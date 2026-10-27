import {test,expect} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
import {openTDSettings} from './td-settings-fixture.js';
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-keyboard';
mkdirSync(evidence,{recursive:true});
test.use({channel:process.env.VOICE_AGENT_TD_UI_CHANNEL || undefined});
test.afterEach(async({page},info)=>{
 const snapshot=await page.locator('#advanced-empty').ariaSnapshot().catch(()=>null);
 const focus=await page.evaluate(()=>({tag:document.activeElement?.tagName,id:document.activeElement?.id,
  visible:!!document.activeElement?.getClientRects().length})).catch(()=>null);
 writeFileSync(`${evidence}/${info.title.replaceAll(/[^a-zA-Z0-9-]/g,'_')}.json`,JSON.stringify({
  evidenceLevel:'fixture',browser:info.project.name,status:info.status,focus,ariaSnapshot:snapshot,
  boundary:'browser keyboard/DOM accessibility only; not VoiceOver or physical device proof'},null,2));
});
for(const width of [1440,390]) {
 test(`keyboard section navigation and named controls at ${width}px`,async({page,context})=>{
  await openTDSettings(page,context,{width,baseline:false});
  await page.locator('[data-advanced="general"]').focus();await page.keyboard.press('Enter');
  await expect(page.locator('#td-general')).toBeVisible();
  await page.keyboard.press('Tab');await expect(page.locator('#td-entry')).toBeFocused();
  await page.keyboard.press('Space');await expect(page.locator('#td')).toBeVisible();
  await page.keyboard.press('Tab');await expect(page.locator('[data-td="semantic"]')).toBeFocused();
  await page.keyboard.press('Enter');await expect(page.locator('[data-td="semantic"]')).toHaveAttribute('aria-pressed','true');
  expect(await page.locator('[data-td="semantic"]').evaluate(node=>node.matches(':focus-visible'))).toBe(true);
  await page.locator('#open-jev').focus();await page.keyboard.press('Enter');
  await expect(page.locator('#jev-back')).toBeFocused();
  await page.locator('[data-jev="questions"]').focus();await page.keyboard.press('Space');
  await expect(page.locator('[data-jev="questions"]')).toHaveAttribute('aria-pressed','true');
  await page.locator('#jev-back').focus();await page.keyboard.press('Enter');
  await expect(page.locator('#open-jev')).toBeFocused();
  await page.locator('[data-td="rules"]').focus();await page.keyboard.press('Enter');
  await page.locator('#rule-enabled').focus();await page.keyboard.press('Space');
  await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Save TD settings',exact:true})).toBeFocused();
  await page.keyboard.press('Shift+Tab');await expect(page.locator('#rule-enabled')).toBeFocused();
  await page.keyboard.press('Space');await page.locator('#collection-enabled').focus();await page.keyboard.press('Space');
  await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Save TD settings',exact:true})).toBeFocused();
  const controls=page.locator('#advanced-empty input:visible,#advanced-empty select:visible,#advanced-empty textarea:visible,#advanced-empty button:visible');
  expect(await controls.count()).toBeGreaterThan(8);
  for(let i=0;i<await controls.count();i++)await expect(controls.nth(i)).toHaveAccessibleName(/\S/);
  const ids=await page.locator('#advanced-empty [id]').evaluateAll(nodes=>nodes.map(node=>node.id));
  expect(new Set(ids).size).toBe(ids.length);
  await page.screenshot({path:`${evidence}/keyboard-rules-${width}.png`,fullPage:true});
 });
 test(`keyboard vocabulary and Jev row creation and removal preserve focus at ${width}px`,async({page,context})=>{
  await openTDSettings(page,context,{width,baseline:false});
  await page.locator('#add-word').focus();await page.keyboard.press('Enter');
  await expect(page.locator('.td-aliases').last()).toBeFocused();
  await page.locator('#mappings .td-mapping').last().locator('.td-remove').focus();await page.keyboard.press('Enter');
  await expect(page.locator('.td-aliases').first()).toBeFocused();
  await page.locator('#mappings .td-mapping').first().locator('.td-remove').focus();await page.keyboard.press('Enter');
  await expect(page.locator('#add-word')).toBeFocused();
  await page.locator('[data-td="semantic"]').focus();await page.keyboard.press('Enter');
  await page.locator('#open-jev').focus();await page.keyboard.press('Enter');
  await page.locator('[data-jev="questions"]').focus();await page.keyboard.press('Enter');
  await page.locator('#jev-add-option').focus();await page.keyboard.press('Space');
  await expect(page.locator('.jev-option').last().locator('input').first()).toBeFocused();
  await page.locator('.jev-option').last().locator('button').focus();await page.keyboard.press('Enter');
  await expect(page.locator('.jev-option').last().locator('input').first()).toBeFocused();
 });
 test(`keyboard Sessions drawer opens and Escape restores its trigger at ${width}px`,async({page,context})=>{
  await openTDSettings(page,context,{width,baseline:false});
  await page.getByRole('button',{name:'Sessions',exact:true}).focus();
  await Promise.all([page.waitForResponse(response=>new URL(response.url()).pathname==='/api/history'),page.keyboard.press('Enter')]);
  const row=page.locator('.history-row').first();await row.focus();await page.keyboard.press('Enter');
  await expect(page.locator('#history-dialog')).toBeVisible();await expect(page.locator('#close-history')).toBeFocused();
  await page.keyboard.press('Escape');await expect(page.locator('#history-dialog')).toBeHidden();await expect(row).toBeFocused();
 });
 test(`keyboard Sessions returns to refreshed row identity at ${width}px`,async({page,context})=>{
  await openTDSettings(page,context,{width,baseline:false});
  let release,started;
  const requested=new Promise(resolve=>started=resolve);
  await page.route('**/api/history?**',async route=>{
   started();await new Promise(resolve=>release=resolve);await route.fallback();
  });
  await page.getByRole('button',{name:'Sessions',exact:true}).focus();await page.keyboard.press('Enter');await requested;
  const row=page.locator('.history-row').first();const name=await row.locator('strong').first().innerText();await row.focus();
  const old=await row.elementHandle();await page.keyboard.press('Enter');await expect(page.locator('#close-history')).toBeFocused();
  const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/history');release();await response;
  await expect.poll(()=>old.evaluate(node=>node.isConnected)).toBe(false);
  await page.keyboard.press('Escape');await expect(page.locator('#history-dialog')).toBeHidden();
  await expect(page.locator('.history-row').filter({hasText:name})).toBeFocused();
 });
 test(`keyboard ASR component drawer focus and source selection at ${width}px`,async({page,context})=>{
  await openTDSettings(page,context,{width,baseline:false});
  await page.getByRole('button',{name:'Bot settings',exact:true}).focus();await page.keyboard.press('Enter');
  const card=page.locator('.pipeline-card[data-component="asr"]');await card.focus();await page.keyboard.press('Enter');
  await expect(page.getByRole('button',{name:'Collapse component drawer',exact:true})).toBeFocused();
  await page.keyboard.press('Tab');await expect(page.locator('#bot-asr')).toBeFocused();
  await page.locator('#bot-turn-source').focus();await page.keyboard.press('Home');await page.keyboard.press('End');
  await expect(page.locator('#bot-turn-source')).toHaveValue('self_developed');
  await page.keyboard.press('Escape');await expect(page.locator('.component-drawer')).toBeHidden();await expect(card).toBeFocused();
 });
}
