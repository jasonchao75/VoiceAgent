import {chromium} from '/Volumes/work/OpenCode/VoiceAgent/frontend/node_modules/@playwright/test/index.mjs';
import {openTDSettings} from '/Volumes/work/OpenCode/VoiceAgent/frontend/tests/ui/td-settings-fixture.js';
const browser=await chromium.launch();
try {
 const context=await browser.newContext({baseURL:'http://127.0.0.1:5192'});
 const page=await context.newPage();await openTDSettings(page,context,{width:390,baseline:false});
 let release,started;
 const requested=new Promise(resolve=>started=resolve);
 await page.route('**/api/history?**',async route=>{
  started();await new Promise(resolve=>release=resolve);await route.fallback();
 });
 await page.getByRole('button',{name:'Sessions',exact:true}).focus();await page.keyboard.press('Enter');
 await requested;
 const row=page.locator('.history-row').first();await row.focus();
 await page.evaluate(()=>{window.reviewTrigger=document.activeElement;});
 await page.keyboard.press('Enter');await page.locator('#close-history').waitFor({state:'visible'});
 const opened=await page.locator('#close-history').evaluate(n=>n===document.activeElement);
 release();await page.waitForResponse(r=>new URL(r.url()).pathname==='/api/history');
 await page.waitForFunction(()=>!window.reviewTrigger.isConnected);
 await page.keyboard.press('Escape');
 console.log(JSON.stringify({openedWithCloseFocused:opened,triggerDetached:await page.evaluate(()=>!window.reviewTrigger.isConnected),
  drawerHidden:await page.locator('#history-dialog').evaluate(n=>n.hidden),focus:await page.evaluate(()=>({tag:document.activeElement.tagName,id:document.activeElement.id,visible:!!document.activeElement.getClientRects().length}))}));
 await context.close();
} finally {await browser.close();}
