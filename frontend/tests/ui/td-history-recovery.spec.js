import {test, expect} from '@playwright/test';
import {mkdirSync, readFileSync} from 'node:fs';

const fixture = JSON.parse(readFileSync('../tests/ui/fixtures/voice-bot-editor.json'));
const catalog = JSON.parse(readFileSync('tests/ui/fixtures/td-catalog.json'));
const evidence = process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-history-recovery';
mkdirSync(evidence, {recursive:true});

for (const width of [1440, 390]) {
  test(`Sessions failure recovers to an empty list without stale error at ${width}px`, async ({page}) => {
    await page.setViewportSize({width, height:1000});
    let mode = 'loaded';
    await page.route('**/api/**', async route => {
      const pathname = new URL(route.request().url()).pathname;
      let data;
      if (pathname === '/api/catalogs') data = catalog;
      else if (pathname === '/api/auth/session') data = {idle_expires_at:4000000000,absolute_expires_at:4000000000};
      else if (pathname === '/api/bots') data = fixture.bots;
      else if (pathname === '/api/history') {
        if (mode === 'failed') return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'History fixture unavailable'})});
        data = {items:mode === 'empty' ? [] : fixture.history.items,total:mode === 'empty' ? 0 : fixture.history.items.length,limit:25,offset:0};
      } else return route.fulfill({status:404,body:'{}'});
      return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
    });
    await page.goto('/');
    await expect(page.locator('.bot-card').first()).toBeVisible();
    await page.getByRole('button',{name:'Sessions',exact:true}).click();
    await expect(page.locator('.history-row').first()).toBeVisible();
    mode = 'failed';
    await page.locator('#refresh-history').click();
    const notice = page.getByRole('alert').filter({hasText:'History fixture unavailable'});
    await expect(notice).toBeVisible();
    await page.screenshot({path:`${evidence}/history-failed-${width}.png`});
    mode = 'empty';
    await page.locator('#refresh-history').click();
    await expect(page.locator('#history-list')).toContainText('No calls recorded yet.');
    await expect(page.locator('.history-row')).toHaveCount(0);
    await expect(page.locator('#history-load-error')).toBeHidden();
    expect(await page.locator('#history-list').evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true);
    await page.screenshot({path:`${evidence}/history-recovered-${width}.png`});
  });
}
