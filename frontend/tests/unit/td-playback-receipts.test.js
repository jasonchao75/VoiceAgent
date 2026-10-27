import {test} from 'node:test';
import assert from 'node:assert/strict';
import {PlaybackReceiptSender} from '../../src/td-playback-receipts.js';
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function setup(fetcher) {
 const timers=new Map(),failures=[];let id=0;
 const sender=new PlaybackReceiptSender({sessionId:'s',token:'inert',fetcher,
  schedule:fn=>{timers.set(++id,fn);return id;},cancel:key=>timers.delete(key),
  onFailure:reason=>failures.push(reason)});
 return {sender,timers,failures};
}
test('hung start receipt has a deadline; stop cannot bypass it and failure is explicit once',async()=>{
 const calls=[];const {sender,timers,failures}=setup((url,options)=>{
  calls.push(options);return new Promise(()=>{});
 });
 const first=sender.enqueue({event:'task_started'}),stop=sender.enqueue({event:'task_stopped'});
 await flush();assert.equal(calls.length,1);assert.equal(calls[0].signal.aborted,false);
 [...timers.values()][0]();await first;await stop;
 assert.equal(calls[0].signal.aborted,true);assert.equal(calls.length,1);
 assert.deepEqual(failures,['playback_receipt_unconfirmed']);assert.equal(timers.size,0);
});
test('server acceptance with lost HTTP response never becomes a guessed successful receipt',async()=>{
 const accepted=[];const {sender,timers,failures}=setup((url,options)=>{
  accepted.push(JSON.parse(options.body));return new Promise(()=>{});
 });
 const pending=sender.enqueue({event:'task_stopped'});await flush();[...timers.values()][0]();
 await pending;assert.equal(accepted.length,1);assert.equal(failures.length,1);
 assert.equal(sender.failed,true);
});
test('close aborts and settles a pending request without failure callback or queued delivery',async()=>{
 const calls=[];const {sender,timers,failures}=setup((url,options)=>{
  calls.push(options);return new Promise(()=>{});
 });
 const pending=sender.enqueue({event:'task_started'});sender.enqueue({event:'task_stopped'});
 await flush();sender.close();await pending;await flush();
 assert.equal(calls[0].signal.aborted,true);assert.equal(calls.length,1);
 assert.equal(failures.length,0);assert.equal(timers.size,0);
});
test('successful receipt order and HTTP rejection keep the authenticated protocol',async()=>{
 const events=[];const {sender,failures}=setup(async(url,options)=>{
  assert.equal(options.headers.Authorization,'Bearer inert');
  events.push(JSON.parse(options.body).event);return {ok:events.length<3};
 });
 await sender.enqueue({event:'task_started'});await sender.enqueue({event:'task_stopped'});
 await sender.enqueue({event:'task_finished'});
 assert.deepEqual(events,['task_started','task_stopped','task_finished']);assert.equal(failures.length,1);
 sender.close();
});
