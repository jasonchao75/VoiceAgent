import {test,expect} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
import {openTDSettings} from './td-settings-fixture.js';
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-vocab-header';
mkdirSync(evidence,{recursive:true});
test.use({channel:process.env.VOICE_AGENT_TD_UI_CHANNEL || undefined});
async function vocabularySignature(page) {
 return page.locator('#vocabulary').evaluate(root=>{
  const header=root.querySelector('.vocab-head'),row=root.querySelector('#mappings .td-mapping');
  const style=getComputedStyle(header),area=root.getBoundingClientRect();
  const rect=node=>{const b=node.getBoundingClientRect();return {left:b.left-area.left,right:b.right-area.left,top:b.top-area.top,width:b.width};};
  const cells=[row.querySelectorAll('input')[0],row.querySelectorAll('input')[1],row.querySelector('.cache-row-audio')];
  return {style:Object.fromEntries(['display','fontSize','color','marginTop','columnGap'].map(key=>[key,style[key]])),
   labels:[...header.children].map(node=>node.textContent),header:[...header.children].slice(0,3).map(rect),
   cells:cells.map(rect),audioGridRow:getComputedStyle(cells[2]).gridRowStart,
   overflow:root.scrollWidth>root.clientWidth};
 });
}
for(const [language,width] of [['zh',1440],['en',1440],['zh',390],['en',390],['en',650],['en',701]]) {
 test(`frozen vocabulary header and input/audio columns at ${width}px ${language}`,async({page,context})=>{
  const {reference}=await openTDSettings(page,context,{width,language});
  const before=await vocabularySignature(reference),after=await vocabularySignature(page);
  writeFileSync(`${evidence}/header-${width}-${language}.json`,JSON.stringify({baseline:before,production:after},null,2));
  await page.locator('#vocabulary').screenshot({path:`${evidence}/formal-vocabulary-${width}-${language}.png`});
  await reference.locator('#vocabulary').screenshot({path:`${evidence}/frozen-vocabulary-${width}-${language}.png`});
  expect(after.style).toEqual(before.style);expect(after.labels).toEqual(before.labels);
  expect(after.overflow).toBe(false);
  if(width>700) {
   expect(after.style.display).toBe('grid');
   for(let i=0;i<3;i++) {
    expect(Math.abs(after.header[i].left-before.header[i].left)).toBeLessThan(1);
    expect(Math.abs(after.header[i].width-before.header[i].width)).toBeLessThan(1);
    expect(Math.abs((after.header[i].left-after.cells[i].left)
      -(before.header[i].left-before.cells[i].left))).toBeLessThan(1);
    const center=(after.header[i].left+after.header[i].right)/2;
    if(width===1440) {
      expect(center).toBeGreaterThanOrEqual(after.cells[i].left);
      expect(center).toBeLessThanOrEqual(after.cells[i].right);
    }
   }
  }else {
   expect(after.style.display).toBe('none');expect(after.audioGridRow).toBe(before.audioGridRow);
   expect(after.cells[2].top).toBeGreaterThan(after.cells[0].top);
  }
  await reference.close();
 });
}
