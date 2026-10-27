import {test,expect} from '@playwright/test';
import {readFileSync,mkdirSync} from 'node:fs';
const fixture=JSON.parse(readFileSync('../tests/ui/fixtures/voice-bot-editor.json'));
const catalog=JSON.parse(readFileSync('tests/ui/fixtures/td-catalog.json'));
const evidence=process.env.VOICE_AGENT_TD_UI_EVIDENCE || '../test-results/td-timing-history';
mkdirSync(evidence,{recursive:true});
for(const width of [1440,390]) test(`history keeps measured ranges on their original response at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:1000});
 await page.addInitScript(()=>localStorage.setItem('voiceagent-td-locale','en'));
 const interval={lower_ms:5.01,upper_ms:25.01,playback_id:'a'.repeat(32),response_id:'7:1',
  anchor_ids:['b'.repeat(32),'c'.repeat(32)],source:'authenticated_worklet_causal_bracket',origin:'server_audio_task_prepared'};
 const e2e={...interval,lower_ms:700.01,upper_ms:950.01,origin:'vad_speech_end_source_sample'};
 const detail={...fixture.history.detail,metrics:[{turn_index:0,playback_ms:null,turn_to_playback_ms:null,
  incomplete_reason:'bounded_timing_only',timing_ranges:{playback:interval,e2e}}],td_events:[
  {event:'conversation_utterance',turn_id:7,role:'user',text:'hello',history_metric_index:0},
  {event:'conversation_utterance',turn_id:7,role:'assistant',text:'Partial answer',response_id:'7:1'},
  {event:'conversation_utterance',turn_id:7,role:'assistant',text:'Final answer',response_id:'7:2'},
  {event:'playback_timing_bounds',turn_id:7,response_id:'7:1',playback_id:interval.playback_id,playback_range:interval,
   e2e_missing_reason:null},
  {event:'e2e_timing_bounds',turn_id:7,response_id:'7:1',playback_id:interval.playback_id,e2e_range:e2e},
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
 const dialog=page.locator('#history-dialog'),range=dialog.locator('.playback-timing-range');
 await expect(range).toHaveCount(1);
 await expect(dialog.locator('.e2e-timing-range')).toHaveCount(1);
 await expect(dialog.locator('.e2e-timing-range')).toHaveAttribute('data-response-id','7:1');
 await expect(dialog.locator('.e2e-timing-range')).toContainText('700–950.1 ms');
 await expect(dialog.locator('.history-metric')).toContainText('VAD speech-end source sample → client render');
 await expect(range).toHaveAttribute('data-response-id','7:1');
 await expect(range).toContainText('5–25.1 ms');
 await expect(range.getByText('Measured playback range',{exact:true})).toBeVisible();
 await expect(dialog.locator('.history-metric')).toContainText('playback 5–25.1 ms');
 await expect(dialog.locator('.history-metric')).toContainText('server audio task ready → client render');
 await expect(dialog.locator('.history-metric')).not.toContainText('speech-end clock unavailable');
 await expect(dialog.locator('.e2e-timing-range')).toContainText('VAD speech-end source sample');
 await dialog.locator('#td-history-language').selectOption('zh');
 await expect(range.getByText('已测播放延迟范围',{exact:true})).toBeVisible();
 await expect(dialog.locator('.e2e-timing-range')).toContainText('已测端到端延迟范围');
 await expect(dialog.locator('.e2e-timing-range')).toContainText('VAD停声源样本');
 await expect(range).toContainText('5–25.1 ms');
 expect(await dialog.evaluate(node=>node.scrollWidth<=node.clientWidth)).toBe(true);
 await page.screenshot({path:`${evidence}/range-history-${width}.png`,fullPage:true});
});
