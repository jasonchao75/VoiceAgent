import template from "./td-settings.html?raw";
import "./td-settings.css";
import { mountTDLocale } from "./td-locale.js";

export function mountTDSettings(root, { request, saved, hasUnsavedTTS = () => false }) {
  root.classList.add("td-settings-host");
  const general = document.createElement("div");
  general.id = "td-general";
  const fallback = root.querySelector('[for="bot-fallback-script"]');
  for (const node of [fallback, root.querySelector("#bot-fallback-script"), root.querySelector("#bot-fallback-script + .hint"), root.querySelector("#save-advanced-settings")]) {
    if (node) general.append(node);
  }
  const nav = document.createElement("nav");
  nav.className = "td-subnav";
  nav.setAttribute("aria-label", "Advanced sections");
  nav.innerHTML = '<button type="button" data-advanced="general">General</button><button type="button" id="td-entry" data-advanced="td">Turn Detection</button>';
  root.append(nav, general);
  const content = document.createElement("div");
  content.className = "td-content";
  content.innerHTML = template;
  root.append(content);
  const $ = selector => root.querySelector(selector);
  const $$ = selector => [...root.querySelectorAll(selector)];
  let bot, source, config, dirty = false, revision = 0, loaded = false, audioState, previewContext, saving = false;
  const value = id => $(`#${id}`).value;
  const put = (id, data) => { $(`#${id}`).value = data ?? ""; };
  const number = id => {
    const input = $(`#${id}`);
    if (!input.value.trim() || !Number.isFinite(Number(input.value)) || !input.checkValidity()) throw new Error(`Enter a valid ${input.labels?.[0]?.textContent || id}.`);
    return Number(input.value);
  };
  const error = message => { $("#form-error").textContent = message; $("#form-error").hidden = !message; };
  function section(name) {
    root.classList.toggle("td-showing-jev", name === "jev");
    general.hidden = name !== "general";
    $("#td").hidden = name !== "td";
    $("#td-jev").hidden = name !== "jev";
    $$('[data-advanced]').forEach(button => {
      const current = button.dataset.advanced === (name === "jev" ? "td" : name);
      button.classList.toggle("active", button.dataset.advanced === name);
      if (current) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
  }
  function tab(attribute, name, pane) {
    $$(`[data-${attribute}]`).forEach(button => {
      const selected = button.dataset[attribute] === name;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
    $$(`[data-${pane}]`).forEach(node => { node.hidden = node.dataset[pane.replace(/-([a-z])/g, (_, char) => char.toUpperCase())] !== name; });
  }
  $$('[data-td], [data-jev]').forEach(button => {
    button.setAttribute("aria-pressed", String(button.classList.contains("active")));
  });
  nav.addEventListener("click", event => { if (event.target.dataset.advanced) section(event.target.dataset.advanced); });
  $$('[data-td]').forEach(button => { button.type = "button"; button.onclick = () => tab("td", button.dataset.td, "pane"); });
  $$('[data-jev]').forEach(button => { button.type = "button"; button.onclick = () => tab("jev", button.dataset.jev, "jev-pane"); });
  $("#open-jev").onclick = () => { section("jev"); $("#jev-back").focus(); };
  $("#jev-back").onclick = () => { section("td"); tab("td", "semantic", "pane"); $("#open-jev").focus(); };
  $("#jev-reveal").onclick = () => { const input = $("#jev-key"); input.type = input.type === "password" ? "text" : "password"; $("#jev-reveal").textContent = input.type === "password" ? "Show" : "Hide"; };
  const keySave = document.createElement("label");
  keySave.className = "switch-row";
  keySave.innerHTML = '<span>Save API key for this Bot</span><input id="jev-save-key" type="checkbox">';
  $("#jev-key").closest(".input-with-action").after(keySave);
  function markDirty() {
    dirty = true; revision++;
    $("#save-state").textContent = "Unsaved changes";
    $("#jev-save-status").textContent = "Unsaved changes";
  }
  function removeEditableRow(element, fallback) {
    // A removed focused subtree must not strand keyboard navigation on the document.
    const focused = element.contains(document.activeElement);
    const adjacent = element.nextElementSibling || element.previousElementSibling;
    element.remove();
    if (focused) (adjacent?.querySelector("input") || $(fallback)).focus();
  }
  function mapping(row = {}) {
    const element = document.createElement("div");
    element.className = "td-vocab-row td-mapping";
    element.innerHTML = '<input class="td-aliases" aria-label="Recognized variants"><span class="td-mapping-arrow" aria-hidden="true">→</span><input class="td-target" aria-label="Echo value"><div class="td-audio-status cache-row-audio">Not generated</div><button class="td-remove" type="button" aria-label="Delete mapping">×</button>';
    element.querySelector(".td-aliases").value = (row.aliases || []).join(", ");
    element.querySelector(".td-target").value = row.value || "";
    element.querySelector("button").onclick = () => { removeEditableRow(element, "#add-word"); markDirty(); };
    $("#mappings").append(element);
    return element;
  }
  function option(row = {}) {
    const element = document.createElement("div");
    element.className = "jev-option";
    element.innerHTML = '<input aria-label="Option identifier" placeholder="Label"><input aria-label="Option meaning" placeholder="Meaning"><div class="td-unit"><input type="number" min="0" max="120000" aria-label="Option total wait" placeholder="ms"><span>ms</span></div><button type="button" aria-label="Delete option">×</button>';
    const inputs = element.querySelectorAll("input");
    [row.id, row.meaning, row.wait_ms].forEach((data, index) => { inputs[index].value = data ?? ""; });
    element.querySelector("button").onclick = () => { removeEditableRow(element, "#jev-add-option"); markDirty(); syncDistribution(); };
    $("#jev-options").append(element);
    return element;
  }
  $("#add-word").onclick = () => { const row = mapping(); markDirty(); row.querySelector("input").focus(); };
  $("#jev-add-option").onclick = () => { const row = option(); markDirty(); syncDistribution(); row.querySelector("input").focus(); };
  function enabled() {
    $("#rule-fields").disabled = !$("#rule-enabled").checked;
    const collectionDisabled = !$("#rule-enabled").checked || !$("#collection-enabled").checked;
    for (const id of ["number-length", "collection-timeout", "collection-message", "overflow-message"])
      $("#" + id).disabled = collectionDisabled;
    $("#jev-pin-field").hidden = value("jev-model") !== "pinned";
  }
  content.addEventListener("input", event => {
    if (event.target.id === "td-language") return;
    markDirty(); enabled();
    if (event.target.closest("#mappings")) {
      $$(".td-audio-status button").forEach(button=>{button.disabled=true;});
      $$(".td-audio-status span").forEach(label=>{label.textContent="Save to check audio";});
    }
  });
  content.addEventListener("change", enabled);
  function collect() {
    if (source !== "self_developed" && !dirty) return config;
    const vocabulary = $$(".td-vocab-row").map(row => ({
      value: row.querySelector(".td-target").value.trim(),
      aliases: row.querySelector(".td-aliases").value.split(/[,，]/).map(item => item.trim()).filter(Boolean),
    }));
    const aliases = new Set(), targets = new Set();
    for (const row of vocabulary) {
      if (!row.value || !row.aliases.length || targets.has(row.value)) throw new Error("Enter unique echo values and recognized variants.");
      targets.add(row.value);
      for (const alias of row.aliases) {
        const key = alias.normalize("NFKC").toLowerCase();
        if (aliases.has(key)) throw new Error("Recognized variants must be unique.");
        aliases.add(key);
      }
    }
    const options = $$("#jev-options .jev-option").map(row => {
      const inputs = row.querySelectorAll("input");
      if (!inputs[0].value.trim() || !inputs[1].value.trim() || inputs[2].value === "" || !inputs[2].checkValidity()) throw new Error("Complete each Jev output option.");
      return {id: inputs[0].value.trim(), meaning: inputs[1].value.trim(), wait_ms: Number(inputs[2].value)};
    });
    if (options.length < 2 || new Set(options.map(row => row.id)).size !== options.length) throw new Error("Enter at least two unique Jev options.");
    const rule = {...(config?.priority_rule || {}), enabled: $("#rule-enabled").checked, keywords: value("keywords").split("\n").map(item=>item.trim()).filter(Boolean), vocabulary};
    for (const [field,id] of [["wpm_threshold","wpm"],["pause_ms","echo-pause"],["unit_gap_ms","echo-gap"]]) rule[field] = value(id) === "" && !rule.enabled ? null : number(id);
    if (rule.enabled && (!rule.keywords.length || !rule.vocabulary.length)) throw new Error("Enter at least one keyword and vocabulary mapping.");
    if ($("#collection-enabled").checked) rule.collection = {
      target_length:number("number-length"), timeout_ms:number("collection-timeout"),
      overflow_pause_ms: config?.priority_rule?.collection?.overflow_pause_ms ?? number("echo-pause"),
      incomplete_text:value("collection-message"), overflow_text:value("overflow-message"),
    }; else rule.collection = null;
    const result = {
      minimum_ms:number("minimum"), maximum_ms:number("maximum"), final_wait_ms:number("final-wait"),
      alpha:number("fusion-alpha"), conflict_threshold:number("conflict-high"),
      vad:{confidence:number("confidence"),start_secs:number("vad-start")/1000,stop_secs:number("vad-stop")/1000,min_volume:number("volume")},
      jev:{endpoint:value("jev-endpoint"),model:value("jev-model")==="pinned"?value("jev-pin").trim():"jev-latest",timeout_seconds:number("jev-timeout")/1000,max_calls:100,noul_instructions:value("jev-yield-instructions"),choice_instructions:value("jev-state-instructions"),options},
      priority_rule:rule,
    };
    if (result.maximum_ms < result.minimum_ms) throw new Error("Maximum silence must be at least minimum silence.");
    return result;
  }
  async function save(event) {
    event?.preventDefault();
    error("");
    if (saving) return;
    if (!bot) return error("Select a Bot first.");
    const id = bot.id;
    try {
      const next = collect(), payload = {td_config:next, save_jev_key:$("#jev-save-key").checked};
      if (value("jev-key")) {
        if (!$("#jev-save-key").checked) throw new Error("Select Save API key to retain this Jev key.");
        payload.jev_api_key = value("jev-key"); payload.save_jev_key = true;
      }
      const version = revision;
      saving = true;
      // The Bot endpoint replaces the full configuration; retain unrelated saved fields and keys.
      const current = await request(`/api/bots/${id}`);
      const {id: _id, has_jev_key, has_saved_keys, has_asr_key, has_tts_key, has_llm_key,
        asr_account_catalog, created_at, updated_at, ...fields} = current;
      const result = await request(`/api/bots/${id}`, {method:"PUT",body:{...fields,
        save_asr_key:has_asr_key, save_tts_key:has_tts_key, save_llm_key:has_llm_key, ...payload}});
      saved(result);
      if (bot?.id !== id) return;
      config = result.td_config; bot = result;
      $("#jev-error").textContent = "";
      $("#jev-error").hidden = true;
      if (version !== revision) {
        dirty = true;
        $("#save-state").textContent = "Earlier changes saved · newer edits unsaved";
        $("#jev-save-status").textContent = "Earlier changes saved · newer edits unsaved";
        return;
      }
      dirty = false;
      put("jev-key", ""); $("#jev-key").type = "password";
      $("#save-state").textContent = "Saved"; $("#jev-save-status").textContent = "Saved";
      await refreshAudio();
    } catch (failure) {
      if (bot?.id !== id) return;
      error(failure.message); $("#jev-error").textContent = failure.message; $("#jev-error").hidden = false;
    }
    finally { saving = false; }
  }
  $("#td-form").onsubmit = save;
  $("#jev-form").onsubmit = save;
  $("#jev-check").onclick = () => { try { collect(); $("#jev-check-status").textContent = "Fields valid · no external request"; } catch (failure) { $("#jev-check-status").textContent = failure.message; } };
  const units = text => /^\d+$/u.test(text) ? [...text] : [text];
  function displayAudio(state) {
    audioState = state;
    for (const row of $$(".td-vocab-row")) {
      const target = row.querySelector(".td-target").value;
      const assets = units(target).map(unit => (state.assets || []).find(asset => asset.unit === unit));
      const ready = target && assets.every(asset => asset?.status === "ready" && asset.url);
      const slot = row.querySelector(".td-audio-status");
      slot.replaceChildren();
      const label = document.createElement("span");
      label.className = "hint";
      label.textContent = ready ? "Ready" : assets.some(asset => asset?.status === "failed") ? "Failed" : "Missing / mismatched";
      const listen = document.createElement("button");
      listen.className = "td-link-button";
      listen.type = "button"; listen.textContent = "Listen"; listen.disabled = !ready;
      listen.onclick = async () => {
        try {
          if (dirty || hasUnsavedTTS()) throw new Error("Save the Bot and vocabulary before listening.");
          await previewContext?.close();
          const context = new AudioContext(); previewContext = context;
          await context.resume();
          const buffers = await Promise.all(assets.map(async asset => {
            const response = await fetch(asset.url, {credentials:"same-origin"});
            if (!response.ok) throw new Error("Audio resource unavailable. Refresh its status.");
            return context.decodeAudioData(await response.arrayBuffer());
          }));
          if (previewContext !== context) return;
          let offset = context.currentTime + .02;
          for (const buffer of buffers) {
            const source = context.createBufferSource(); source.buffer = buffer; source.connect(context.destination); source.start(offset);
            offset += buffer.duration + number("echo-gap") / 1000;
          }
        } catch (failure) { $("#cache-action-status").textContent = failure.message; }
      };
      slot.append(label, listen);
    }
  }
  async function refreshAudio() {
    if (!bot?.id) return;
    const id = bot.id, version = revision;
    try {
      const state = await request(`/api/bots/${id}/echo-audio`);
      if (bot?.id === id && version === revision) displayAudio(state);
    } catch (failure) {
      if (bot?.id === id && version === revision) $("#cache-action-status").textContent = failure.message;
    }
  }
  $("#cache-generate").onclick = async () => {
    const button = $("#cache-generate"), id = bot?.id, version = revision;
    try {
      if (!id || dirty || hasUnsavedTTS()) throw new Error("Save the Bot and vocabulary before generating audio.");
      if (!audioState?.fingerprint) throw new Error("Audio status is unavailable. Reload this Bot and retry.");
      button.disabled = true;
      $("#cache-action-status").textContent = "Generating missing audio…";
      const state = await request(`/api/bots/${id}/echo-audio/generate`, {method:"POST",body:{expected_fingerprint:audioState.fingerprint}});
      if (bot?.id !== id || version !== revision) return;
      displayAudio(state);
      $("#cache-action-status").textContent = (state.assets || []).some(asset => asset.status !== "ready") ? "Some audio failed. Retry to generate missing audio." : "Audio ready · stored permanently";
    } catch (failure) { if (bot?.id === id) $("#cache-action-status").textContent = failure.message; }
    finally { button.disabled = false; }
  };
  function preview() {
    try {
      const data = collect();
      $("#jev-request-preview").textContent = JSON.stringify({model:data.jev.model,state:{assistant:value("jev-sample-assistant"),user:value("jev-sample-user"),transcript_status:value("jev-transcript-kind")},questions:{yield:{type:"noul",instructions:data.jev.noul_instructions},speech_state:{type:"choice",instructions:data.jev.choice_instructions,criteria:Object.fromEntries(data.jev.options.map(option=>[option.id,option.meaning]))}}}, null, 2);
    } catch (failure) { $("#jev-request-preview").textContent = failure.message; }
  }
  $("#jev-refresh-preview").onclick = preview;
  function syncDistribution() {
    const prior = Object.fromEntries($$("#sim-distribution input").map(input=>[input.dataset.option,input.value]));
    const examples = {complete:"0.8",incomplete:"0.2",holding_floor:"0",unclear:"0"};
    $("#sim-distribution").replaceChildren();
    for (const row of $$("#jev-options .jev-option")) {
      const id = row.querySelector("input").value.trim();
      const label = document.createElement("label"); label.className = "prob-row";
      const text = document.createElement("span"); text.textContent = id; label.append(text);
      const input = document.createElement("input"); input.type = "number"; input.min = "0"; input.max = "1"; input.step = ".01"; input.dataset.option = id; input.value = prior[id] ?? examples[id] ?? "0"; label.append(input); $("#sim-distribution").append(label);
    }
  }
  $("#jev-options").addEventListener("change", syncDistribution);
  $("#policy-calculate").onclick = () => {
    syncDistribution();
    try {
      const data = collect(), probability = number("sim-yield"), elapsed = number("sim-elapsed");
      const distribution = $$("#sim-distribution input").map(input=>Number(input.value));
      if (distribution.some(value=>!Number.isFinite(value)||value<0||value>1) || Math.abs(distribution.reduce((sum,value)=>sum+value,0)-1)>1e-6) throw new Error("Choice probabilities must sum to 1.");
      const noul = data.minimum_ms+(1-probability)*(data.maximum_ms-data.minimum_ms);
      const choice = data.jev.options.reduce((sum,option,index)=>sum+option.wait_ms*distribution[index],0);
      const complete = data.jev.options.reduce((sum,option,index)=>sum+(option.id==="complete"?distribution[index]:0),0);
      const holding = data.jev.options.reduce((sum,option,index)=>sum+(["incomplete","holding_floor"].includes(option.id)?distribution[index]:0),0);
      const conflict = (probability>=data.conflict_threshold && holding>=data.conflict_threshold) || (probability<=1-data.conflict_threshold && complete>=data.conflict_threshold);
      const target = Math.min(data.maximum_ms,Math.max(data.minimum_ms,conflict?Math.max(noul,choice):data.alpha*noul+(1-data.alpha)*choice));
      $("#policy-result").textContent = `Target silence ${Math.round(target)} ms − elapsed ${elapsed} ms = remaining ${Math.round(Math.max(0,target-elapsed))} ms.`;
    } catch (failure) { $("#policy-result").textContent = failure.message; }
  };
  function load(next, nextSource, force = false) {
    source = nextSource;
    $("#td-entry").hidden = source !== "self_developed";
    if (loaded && bot?.id === next?.id && !force) { if (source !== "self_developed") section("general"); return; }
    loaded = true; bot = next; config = structuredClone(next?.td_config || null); dirty = false; revision++;
    const data = config || {}, rule = data.priority_rule || {}, vad = data.vad || {}, jev = data.jev || {};
    const fields = {minimum:data.minimum_ms,maximum:data.maximum_ms,"final-wait":data.final_wait_ms,"fusion-alpha":data.alpha,"conflict-high":data.conflict_threshold,"vad-start":vad.start_secs == null?null:vad.start_secs*1000,"vad-stop":vad.stop_secs == null?null:vad.stop_secs*1000,confidence:vad.confidence,volume:vad.min_volume,"jev-endpoint":jev.endpoint || "https://api.typesafe.ai/v1/systemone","jev-timeout":jev.timeout_seconds == null?null:jev.timeout_seconds*1000,"jev-yield-instructions":jev.noul_instructions,"jev-state-instructions":jev.choice_instructions,keywords:(rule.keywords || []).join("\n"),wpm:rule.wpm_threshold,"echo-pause":rule.pause_ms,"echo-gap":rule.unit_gap_ms,"number-length":rule.collection?.target_length,"collection-timeout":rule.collection?.timeout_ms,"collection-message":rule.collection?.incomplete_text,"overflow-message":rule.collection?.overflow_text,"jev-key":""};
    Object.entries(fields).forEach(([id,data])=>put(id,data));
    $$(".bot-name").forEach(node=>{node.textContent=next?.name || "Selected Bot";});
    $("#save-state").textContent = config ? "Saved" : "Enter settings";
    $("#jev-save-status").textContent = config ? "Saved" : "Enter settings";
    $("#jev-check-status").textContent = "Not checked · no external request";
    $("#jev-request-preview").textContent = "";
    $("#jev-error").hidden = true;
    $("#jev-key").type = "password";
    $("#jev-reveal").textContent = "Show";
    put("jev-model", jev.model && jev.model !== "jev-latest"?"pinned":"jev-latest"); put("jev-pin",jev.model);
    $("#jev-save-key").checked = Boolean(next?.has_jev_key);
    $("#rule-enabled").checked = Boolean(rule.enabled); $("#collection-enabled").checked = Boolean(rule.collection);
    $("#mappings").replaceChildren(); (rule.vocabulary || []).forEach(mapping);
    $("#jev-options").replaceChildren(); (jev.options || []).forEach(option);
    $("#sim-distribution").replaceChildren();
    syncDistribution();
    $("#cache-current-tts").textContent = next ? `${next.tts_provider} · ${next.tts_model} · ${next.tts_voice} · ${next.tts_speed}×` : "Select a Bot to prepare audio.";
    audioState = null; previewContext?.close().catch(()=>{}); previewContext = undefined;
    enabled(); error(""); section("general");
    refreshAudio();
  }
  mountTDLocale(root, {externalControl:true});
  return {load,collect, get dirty(){return dirty;}};
}
