// Read existing loopback fixture history; never start a call or contact a vendor.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../../../../../frontend/package.json',import.meta.url));
const {chromium}=require('@playwright/test');
const browser=await chromium.launch();
try {
  for(const width of [1440,390]) {
    const page=await browser.newPage({viewport:{width,height:1000}});
    await page.addInitScript(()=>localStorage.setItem('voiceagent-td-locale','zh'));
    await page.goto('http://127.0.0.1:5177/');
    await page.getByRole('button',{name:'Sessions',exact:true}).click();
    await page.locator('.history-row').first().click();
    const dialog=page.locator('#history-dialog');
    const rows=dialog.locator('.td-record>h4');
    await rows.first().waitFor({state:'attached'});
    const raw=(await rows.allTextContents()).filter(text=>/^(playback|identifier_tool|tool_|media_gap|identifier_old)/.test(text));
    assert.deepEqual(raw,[]);
    await dialog.locator('.turn-td').evaluateAll(nodes=>nodes.forEach(node=>{node.open=true;}));
    const chinese=()=>dialog.locator('.td-record:has(> h4:text-is("编号工具结果"))');
    assert.match(await chinese().textContent(),/工具操作clear/);
    assert.match(await chinese().textContent(),/编号位数0/);
    const values=await dialog.locator('dd').allTextContents();
    await dialog.locator('#td-history-language').selectOption('en');
    assert.deepEqual(await dialog.locator('dd').allTextContents(),values);
    const english=dialog.locator('.td-record:has(> h4:text-is("Identifier tool result"))');
    assert.match(await english.textContent(),/Tool operationclear/);
    await english.scrollIntoViewIfNeeded();
    await dialog.screenshot({path:new URL(`history-tool-${width}-en.png`,import.meta.url).pathname});
    await dialog.locator('#td-history-language').selectOption('zh');
    await chinese().scrollIntoViewIfNeeded();
    await dialog.screenshot({path:new URL(`history-tool-${width}-zh.png`,import.meta.url).pathname});
    assert(await dialog.evaluate(node=>node.scrollWidth<=node.clientWidth));
    console.log(JSON.stringify({width,raw_titles:raw,preserved_values:values.length,overflow:false}));
    await page.close();
  }
} finally {await browser.close();}
