import {test,expect} from '@playwright/test';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
const frozen=readFileSync('../openspec/changes/archive/2026-10-27-add-jev-semantic-turn-detection/prototypes/index.html','utf8');
const fixture=JSON.parse(readFileSync('../tests/ui/fixtures/voice-bot-editor.json'));
const catalog=JSON.parse(readFileSync('tests/ui/fixtures/td-catalog.json'));
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-history-baseline';
mkdirSync(evidence,{recursive:true});
for(const width of [1440,390]) test(`formal Sessions retains frozen turn hierarchy at ${width}px`,async({page,context,baseURL})=>{
 await page.setViewportSize({width,height:1000});
 await page.addInitScript(()=>localStorage.setItem('voiceagent-td-locale','en'));
 const detail={...fixture.history.detail,td_events:[
  {event:'candidate_created',turn_id:1,candidate:1},
  {event:'td_commit',turn_id:1,candidate:1},
  {event:'conversation_utterance',turn_id:1,role:'user',text:'Example input'},
  {event:'conversation_utterance',turn_id:1,role:'assistant',response_id:'1:1',text:'Example reply'},
 ]};
 await page.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;
  const data=path==='/api/catalogs'?catalog:path==='/api/bots'?fixture.bots:
   path==='/api/history'?{items:fixture.history.items,total:fixture.history.items.length,limit:25,offset:0}:
   path.startsWith('/api/history/')?detail:path==='/api/auth/session'?{idle_expires_at:4000000000,absolute_expires_at:4000000000}:{};
  return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto('/');await page.getByRole('button',{name:'Sessions',exact:true}).click();
 await page.locator('.history-row').first().click();
 const actual=page.locator('#history-dialog .sample-turn').first();
 await expect(actual.locator(':scope > header.td-row')).toHaveCount(1);
 await expect(actual.locator(':scope > header .td-badge')).toHaveText('committed');
 await expect(actual.locator('.message.user').first()).toContainText('User');
 const baseline=await context.newPage();await baseline.setViewportSize({width,height:1000});
 await baseline.route('**/__td-history-frozen',route=>route.fulfill({contentType:'text/html',body:frozen}));
 await baseline.goto(new URL('/__td-history-frozen',baseURL).href);
 await baseline.locator('[data-page="sessions"]').click();await baseline.locator('.history-row').first().click();
 async function signature(turn) {return turn.evaluate(root=>{
  const style=(selector,keys)=>{const node=root.querySelector(selector);if(!node)return null;
   const css=getComputedStyle(node);return Object.fromEntries(keys.map(key=>[key,css[key]]));};
  const drawer=root.closest('.history-dialog');
  const metadata=Object.fromEntries(['h2','h2 + p','.recording-unavailable'].map(selector=>{
   const css=getComputedStyle(drawer.querySelector(selector));
   return [selector,{fontSize:css.fontSize,color:css.color}];
  }));
  const list=document.querySelector('.history-panel');
  const listStyle={titleFont:getComputedStyle(list.querySelector('h2')).fontSize,
   filterColumns:getComputedStyle(list.querySelector('.history-filters')).gridTemplateColumns.split(' ').length,
   columns:[...list.querySelector('.history-table-header').children].map(node=>getComputedStyle(node).display)};
  return {listStyle,metadata,header:style(':scope > header',['display','alignItems']),
   title:style('h3',['fontSize','fontWeight','marginTop','marginBottom']),
   badge:style('header .td-badge',['fontSize','color','backgroundColor','borderRadius']),
   user:style('.message.user p',['fontSize','padding','borderRadius','backgroundColor']),
   details:style('details.turn-td',['borderTopWidth','paddingTop']),
   overflow:root.scrollWidth>root.clientWidth};
 });}
 const reference=await signature(baseline.locator('#td-history .sample-turn').first());
 const production=await signature(actual);
 writeFileSync(`${evidence}/history-structure-${width}.json`,JSON.stringify({reference,production},null,2));
 expect(production).toEqual(reference);
 const title=await page.locator('#history-detail > h2').boundingBox();
 const drawerHeader=await page.locator('#history-dialog > header').boundingBox();
 writeFileSync(`${evidence}/history-title-geometry-${width}.json`,JSON.stringify({title,drawerHeader},null,2));
 expect(title.y).toBeGreaterThanOrEqual(drawerHeader.y+drawerHeader.height);
 await page.screenshot({path:`${evidence}/history-structure-${width}.png`,fullPage:true});
 await baseline.close();
 if(width===1440)await page.getByRole('button',{name:'Share',exact:true}).click();
 else await page.keyboard.press('Escape');
 await expect(page.locator('#history-dialog')).toBeHidden();
});
