import { test } from "node:test";
import assert from "node:assert/strict";
import { buildTDHistory } from "../../src/td-history.js";

test("explicit original turn identity groups resumed candidates and Final response versions", () => {
  const model=buildTDHistory({metrics:[{turn_index:0,llm_first_token_ms:12}],td_events:[
    {event:"candidate_created",turn_id:7,candidate:1},
    {event:"speech_resumed",turn_id:7},
    {event:"candidate_created",turn_id:7,candidate:2},
    {event:"conversation_utterance",turn_id:7,role:"user",text:"12",history_metric_index:0},
    {event:"conversation_utterance",turn_id:"7",role:"assistant",response_id:"7:1",text:"old"},
    {event:"conversation_utterance",turn_id:"7",role:"assistant",response_id:"7:2",text:"new"},
    {event:"playback_task_prepared",turn_id:null,playback_id:"unassigned"},
    {event:"candidate_created",turn_id:8,candidate:3},
    {event:"source_transcript",turn_id:7,text:"late original"},
  ]});
  assert.equal(model.turns.length,2);
  assert.equal(model.turns[0].attempts.length,2);
  assert.equal(model.turns[0].attempts[0].outcome,"cancelled");
  assert.equal(model.turns[0].utterances.length,3);
  assert.equal(model.turns[0].metric.llm_first_token_ms,12);
  assert.equal(model.turns[1].metric,null);
  assert.equal(model.session.length,1);
  assert.equal(model.turns[0].events.at(-1).text,"late original");
});

test("legacy sessions invent no TD attempts, turns or probabilities", () => {
  const model=buildTDHistory({turns:[{role:"user",text:"old"}],metrics:[{turn_index:0}]});
  assert.equal(model.turns.length,0);
  assert.equal(model.session.length,0);
});
