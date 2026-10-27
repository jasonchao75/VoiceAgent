// Historical identity comes from captured events, never text matching or today's Bot settings.
import { mountTDLocale } from "./td-locale.js";
import { formatLatencyInterval } from "./td-timing.js";
export function buildTDHistory(call) {
  const groups=new Map(), session=[], playbackTurns=new Map();
  const events=call.td_events || [];
  for (const event of events) if(event.playback_id && event.turn_id!==null && event.turn_id!==undefined) playbackTurns.set(event.playback_id,event.turn_id);
  for (const event of events) {
    const id=event.turn_id ?? playbackTurns.get(event.playback_id);
    if (!(typeof id === "string" || (typeof id === "number" && Number.isFinite(id))) || String(id)==="") {
      session.push(event); continue;
    }
    const key=String(id);
    if (!groups.has(key)) groups.set(key,{id:key,events:[],attempts:[],utterances:[],metric:null});
    const turn=groups.get(key);
    turn.events.push(event);
    if (event.event==="candidate_created") turn.attempts.push({id:event.candidate,events:[],outcome:"pending"});
    const attempt=event.candidate===undefined ? turn.attempts.at(-1) : turn.attempts.find(a=>a.id===event.candidate);
    if (attempt) {
      attempt.events.push(event);
      if (event.event==="speech_resumed" && attempt.outcome!=="committed") attempt.outcome="cancelled";
      if (event.event==="td_commit") attempt.outcome="committed";
      if (event.event==="identifier_local_processed") attempt.outcome="rule processed";
    }
    if (event.event==="conversation_utterance") {
      turn.utterances.push(event);
      const index=event.history_metric_index;
      if (Number.isInteger(index) && index>=0 && call.metrics?.[index]) turn.metric=call.metrics[index];
    }
  }
  return {turns:[...groups.values()],session};
}

const names={
  response_restart:"Final replaced Partial",
  identifier_old_candidate_invalidated:"Previous identifier candidate invalidated",
  identifier_tool_result:"Identifier tool result",identifier_tool_result_offered:"Identifier result offered",
  media_gap:"Audio input gap",playback_cancelled:"Playback cancelled",
  playback_client_finished:"Client render finished",playback_client_started:"Client render started",
  playback_client_stopped:"Client render stopped",playback_dispatched:"Audio dispatched",
  playback_queued:"Playback queued",playback_stop_requested:"Playback stop requested",
  playback_task_prepared:"Playback task prepared",tool_callback_completed:"Tool callback completed",
  tool_settled:"Tool settled",tool_started:"Tool started",
  candidate_created:"Pause candidate",speech_resumed:"Speech resumed",source_transcript:"ASR revision",
  td_settings_snapshot:"Historical TD settings",jev_decision_attempt:"Jev decision attempt",
  jev_wait_calculated:"Wait calculation",jev_result:"Jev result",jev_discarded:"Stale Jev result discarded",td_commit:"Turn submitted",
  identifier_local_processed:"Identifier collected locally",identifier_evaluated:"Identifier rule evaluation",
  identifier_local_revision:"Identifier revision",identifier_retained_revision:"Earlier identifier revision",
  response_restarted:"Final replaced Partial",identifier_reminder:"Configured reminder",
  identifier_echo_scheduled:"Rule echo prepared",playback_renderer_receipt:"Client render evidence",
  playback_timing_bounds:"Measured playback range",e2e_timing_bounds:"Measured E2E range",
  playback_source_failed:"Audio source failed",identifier_echo_resource_failed:"Audio resource failed",
  identifier_echo_job_failed:"Echo preparation failed",
  unranged_transcript:"Transcript without proven range",
  asr_source_evidence_failed:"ASR source evidence unavailable",
  identifier_echo_ready:"Audio resource ready",identifier_echo_resource_ready:"Audio resource ready",identifier_echo_synthesis_started:"Audio recovery synthesis",
};
const fields={operation:"Tool operation",value:"Identifier value",count:"Identifier count",generation:"Collection generation",
  source_id:"Source identity",source_ranges:"Source ranges",request_id:"Request identity",
  text:"Transcript",source_final:"Source Final",source_revision:"Source revision",source_withdrawn:"ASR source removed",stream_epoch:"Connection",
  candidate:"Candidate",status:"Status",reason:"Reason",noul:"Yield probability",probabilities:"Choice distribution",
  path:"Routing",matched_keyword:"Matched keyword",assistant:"Ordinary reply context",units:"Business units",
  start_ms:"ASR start (ms)",end_ms:"ASR end (ms)",wpm:"WPM",wpm_threshold:"WPM threshold",
  timing_reason:"Timing evidence",elapsed_ms:"Elapsed silence (ms)",collected:"Collected value",
  response_id:"Response",old_response_id:"Previous response",playback_id:"Playback task",output_kind:"Output kind",
  renderer_event:"Renderer event",rendered_samples:"Rendered samples",client_elapsed_ms:"Client receipt time (ms)",
  playback_range:"Playback interval evidence",anchors:"Clock anchors",e2e_missing_reason:"E2E missing reason",
  e2e_range:"E2E interval evidence",source_anchors:"Capture clock anchors",
  render_anchors:"Render clock anchors",source_coordinates:"Source sample mapping",
  speech_end_audio_ms:"VAD speech-end audio position (ms)",
  render_frame:"Render frame",render_sample_rate:"Render sample rate (Hz)",render_clock_id:"Render clock scope",
  unit:"Audio unit",fingerprint:"TTS configuration fingerprint",resource_version:"Published resource version",
  recovery_path:"Runtime audio recovery",failure_reason:"Failure reason",duration_ms:"Duration (ms)",recovered:"Recovered",error_type:"Error",
  minimum_ms:"Minimum silence (ms)",maximum_ms:"Maximum silence (ms)",final_wait_ms:"Final wait (ms)",
  alpha:"Fusion weight",conflict_threshold:"Conflict threshold",vad:"Silero settings",jev_model:"Jev model",noul_instructions:"Yield instructions",choice_instructions:"Choice instructions",options:"Choice waits",transcript_status:"Source status",
  noul_ms:"Noul wait (ms)",choice_ms:"Choice wait (ms)",target_ms:"Target silence (ms)",remaining_ms:"Remaining silence (ms)",conflict:"Conflict protection",
  normalized_segment_count:"Changed source segments",raw_frame_kind:"Raw transcript frame",
  silence_start_ms:"Last voice end (ms)",deadline_ms:"Maximum silence deadline (ms)",
};
function element(tag,cls,text) {
  const node=document.createElement(tag); if(cls) node.className=cls;
  if(text!==undefined) node.textContent=text; return node;
}
function eventRecord(event) {
  const row=element("section","td-record");
  row.append(element("h4","",names[event.event] || event.event.replaceAll("_"," ")));
  const dl=element("dl");
  for(const [key,label] of Object.entries(fields)) if(event[key]!==undefined) {
    const pair=element("div");
    const value=element("dd","",event[key]===null ? "Not available" : typeof event[key]==="object" ? JSON.stringify(event[key]) : String(event[key]));
    value.dataset.tdLiteral="";
    const displayLabel=key==="elapsed_ms" && event.event.startsWith("identifier_echo_resource_")
      ? "Resource duration (ms)" : label;
    pair.append(element("dt","",displayLabel),value);
    dl.append(pair);
  }
  row.append(dl);return row;
}
function utterance(role,text,label) {
  label ||= role==="user" ? "User" : "Assistant";
  const node=element("article",`message ${role==="user"?"user":"agent"}`);
  if(label) {
    const caption=element("small","hint");
    label.split(" · ").forEach((part,index)=>{
      if(index) caption.append(document.createTextNode(" · "));
      const fragment=element("span","",part);
      if(index===1 && label.startsWith("Normal reply · ")) fragment.dataset.tdLiteral="";
      caption.append(fragment);
    });
    node.append(caption);
  }
  const body=element("p","",text);body.dataset.tdLiteral="";
  node.append(body);return node;
}
export function appendMissingTD(root) {
  const details=element("details","turn-td");
  const summary=element("summary");
  summary.append(element("span","","TD decisions"),document.createTextNode(" · "),element("span","","Not captured"));
  details.append(summary,element("p","hint","No self-developed TD or Jev evidence was captured for this historical turn."));
  root.append(details);
}
export function appendTDHistory(root,call,formatMetric) {
  const model=buildTDHistory(call);
  // Older sessions retain their original conversation renderer when no identity was captured.
  const hasTurnContent=model.turns.some(turn=>turn.utterances.length || turn.events.some(event=>
    ["identifier_local_processed","identifier_reminder","identifier_echo_scheduled"].includes(event.event)));
  // Local collection and reminders are history even when no ordinary user turn was submitted.
  if (!hasTurnContent) {
    // Preserve legacy conversations, but expose unowned evidence from pre-commit failures.
    if (call.turns?.length || !model.session.length) return false;
    model.turns=[];
  }
  const panel=element("section","td-history");
  const opening=model.session.find(e=>e.event==="assistant_opening");
  if(opening) panel.append(utterance("assistant",opening.text,"Opening"));
  const jumpLabel=element("label","hint","Jump to turn");
  const jump=element("select");jump.id="turn-jump";jump.setAttribute("aria-label","Jump to turn");
  for(const turn of model.turns) { const option=element("option","",`Turn ${turn.id}`);option.value=turn.id;jump.append(option); }
  jumpLabel.append(jump);if(model.turns.length) panel.append(jumpLabel);
  jump.addEventListener("change",()=>panel.querySelector(`[data-turn-id="${CSS.escape(jump.value)}"]`)?.scrollIntoView({block:"start"}));
  for(const turn of model.turns) {
    const card=element("article","sample-turn");card.dataset.turnId=turn.id;
    const header=element("header","td-row");
    header.append(element("h3","",`Turn ${turn.id}`));
    const outcome=turn.events.some(event=>event.event==='td_commit') ? 'committed' : turn.attempts.at(-1)?.outcome
      || (turn.events.some(event=>event.event==='identifier_local_processed') ? 'rule processed' : 'Not captured');
    header.append(element('span','td-badge',outcome));card.append(header);
    for(const event of turn.events) {
      if(event.event==="conversation_utterance") {
        card.append(utterance(event.role,event.text,event.response_id ? `Normal reply · ${event.response_id}` : undefined));
        if(event.role==='assistant' && event.response_id) {
          const timing=turn.events.find(item=>item.event==='playback_timing_bounds'
            && item.response_id===event.response_id && formatLatencyInterval(item.playback_range));
          if(timing) {
            const range=element('section','td-box playback-timing-range');
            range.dataset.responseId=event.response_id;
            range.dataset.playbackId=timing.playback_id;
            range.append(element('strong','','Measured playback range'));
            const value=element('p','',formatLatencyInterval(timing.playback_range));
            value.dataset.tdLiteral='';range.append(value);
            range.append(element('p','hint','Server audio task ready → client render'));
            range.append(element('p','hint','Source: authenticated render samples; interval width is measurement uncertainty.'));
            card.append(range);
          }
          const e2e=turn.events.find(item=>item.event==='e2e_timing_bounds'
            && item.response_id===event.response_id && formatLatencyInterval(item.e2e_range));
          if(e2e) {
            const range=element('section','td-box e2e-timing-range');
            range.dataset.responseId=event.response_id;range.dataset.playbackId=e2e.playback_id;
            range.append(element('strong','','Measured E2E range'));
            const value=element('p','',formatLatencyInterval(e2e.e2e_range));
            value.dataset.tdLiteral='';range.append(value);
            range.append(element('p','hint','VAD speech-end source sample → client render'));
            range.append(element('p','hint','Source: authenticated capture and render samples; interval width is measurement uncertainty.'));
            card.append(range);
          }
        }
      }
      else if(event.event==="identifier_local_processed") card.append(utterance("user",event.text,"Identifier segment"));
      else if(event.event==="identifier_reminder") card.append(utterance("assistant",event.text,"Configured reminder"));
      else if(event.event==="identifier_echo_scheduled") {
        const receipt=turn.events.filter(e=>e.playback_id===event.playback_id && e.event==="playback_renderer_receipt").at(-1);
        const dispatched=turn.events.some(e=>e.playback_id===event.playback_id && e.event==="playback_dispatched");
        const status=receipt ? `${receipt.renderer_event.replace("task_","")} · ${receipt.rendered_samples} samples` : dispatched ? "Sent · playback unconfirmed" : "Scheduled · playback unconfirmed";
        card.append(utterance("assistant",event.text,`${event.kind==="correction"?"Correction echo":"Rule echo"} · ${status}`));
      }
    }
    if(turn.metric && formatMetric) card.append(element("p","history-metric",formatMetric(turn.metric,turn.id)));
    else card.append(element("p","history-metric","Latency metrics not captured for this turn. Rule echoes and configured reminders make no LLM request."));
    const details=element("details","turn-td");
    const summary=element("summary");
    summary.append(element("span","","TD decisions"),document.createTextNode(` · ${turn.attempts.length} `),element("span","","attempts"));
    details.append(summary);
    for(const attempt of turn.attempts) {
      const attemptNode=element("section","td-record td-attempt");
      const heading=element("h4");
      const identity=element("span","",String(attempt.id));identity.dataset.tdLiteral="";
      heading.append(element("span","","Attempt"),document.createTextNode(" "),identity,document.createTextNode(" · "),element("span","",attempt.outcome));
      attemptNode.append(heading);
      for(const event of attempt.events) if(event.event!=="conversation_utterance") attemptNode.append(eventRecord(event));
      details.append(attemptNode);
    }
    const included=new Set(turn.attempts.flatMap(attempt=>attempt.events));
    for(const event of turn.events) if(!included.has(event) && event.event!=="conversation_utterance") details.append(eventRecord(event));
    card.append(details);panel.append(card);
  }
  if(model.session.some(e=>e.event!=="assistant_opening")) {
    const details=element("details","turn-td");details.append(element("summary","","Session evidence without turn attribution"));
    for(const event of model.session) if(event.event!=="assistant_opening") details.append(eventRecord(event));
    panel.append(details);
  }
  mountTDLocale(panel,{id:"td-history-language"});
  root.append(panel);return true;
}
