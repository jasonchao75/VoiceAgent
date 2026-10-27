import {test,expect} from '@playwright/test';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
const frozen=readFileSync('../openspec/changes/archive/2026-10-27-add-jev-semantic-turn-detection/prototypes/index.html','utf8');
const fixture=JSON.parse(readFileSync('../tests/ui/fixtures/voice-bot-editor.json'));
const catalog=JSON.parse(readFileSync('tests/ui/fixtures/td-catalog.json'));
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-shell-baseline';
mkdirSync(evidence,{recursive:true});
for(const width of [1440,390]) test(`formal Share keeps frozen profile QR and link cards at ${width}px`,async({page,context})=>{
  await page.setViewportSize({width,height:1000});
  await page.route('**/api/**',route=>{
    const path=new URL(route.request().url()).pathname;
    const data=path==='/api/catalogs'?catalog:path==='/api/bots'?fixture.bots:
      path==='/api/auth/session'?{idle_expires_at:4000000000,absolute_expires_at:4000000000}:{};
    return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  });
  await page.goto('/?share_fixture=1');
  await page.locator('.bot-card').first().click();
  await page.getByRole('button',{name:'Share',exact:true}).click();
  const baseline=await context.newPage();await baseline.setViewportSize({width,height:1000});
  await baseline.route('**/__td-frozen-shell',route=>route.fulfill({contentType:'text/html',body:frozen}));
  await baseline.goto(new URL('/__td-frozen-shell',page.url()).href);
  await baseline.locator('[data-page="share"]').click();
  async function signature(current){return current.locator('#share-page').evaluate(root=>({
    headings:[...root.querySelectorAll('.share-card h2')].map(node=>node.textContent),
    cards:[...root.querySelectorAll('.share-card')].map(node=>{const css=getComputedStyle(node);return {radius:css.borderRadius,padding:css.padding,background:css.backgroundColor};}),
    overflow:root.scrollWidth>root.clientWidth,
    grid:getComputedStyle(root.querySelector('.share-grid')).gridTemplateColumns.split(' ').length,
  }));}
  const actual=await signature(page),expected=await signature(baseline);
  const shellOrder=async current=>current.locator('.config-panel').evaluate(list=>{
    const content=document.querySelector('#share-page');
    return list.getBoundingClientRect().top>=content.getBoundingClientRect().bottom;
  });
  const approvedMobileOrder=width===390?{
    decision:'D-072',formalListAfterContent:await shellOrder(page),
    frozenListAfterContent:await shellOrder(baseline),
  }:null;
  writeFileSync(`${evidence}/share-shell-${width}.json`,JSON.stringify({actual,expected,approvedMobileOrder},null,2));
  await page.screenshot({path:`${evidence}/share-formal-${width}.png`,fullPage:true});
  await baseline.screenshot({path:`${evidence}/share-frozen-${width}.png`,fullPage:true});
  expect(actual).toEqual(expected);expect(actual.overflow).toBe(false);
  if(approvedMobileOrder){
    expect(approvedMobileOrder.formalListAfterContent).toBe(true);
    expect(approvedMobileOrder.frozenListAfterContent).toBe(false);
  }
  await baseline.close();
  const originalLink=await page.locator('#share-link').inputValue();
  await page.getByRole('button',{name:'Disable link',exact:true}).click();
  await expect(page.locator('#share-qr')).toHaveClass(/disabled/);
  await page.getByRole('button',{name:'Enable link',exact:true}).click();
  await expect(page.getByRole('button',{name:'Disable link',exact:true})).toBeVisible();
  await page.getByLabel('Public description').fill('Private synthetic draft.');
  await expect(page.getByText('Unpublished changes',{exact:true})).toBeVisible();
  await expect(page.locator('#share-link')).toHaveValue(originalLink);
  expect(await page.locator('#share-page').evaluate(node=>node.scrollWidth<=node.clientWidth)).toBe(true);
  writeFileSync(`${evidence}/share-states-${width}.json`,JSON.stringify({evidenceLevel:'fixture',
    disabled:true,reenabled:true,unpublishedDraft:true,linkRetained:true,actualPersistenceProven:false},null,2));
});
