import { PipecatClient } from "@pipecat-ai/client-js";
import { WebSocketTransport } from "@pipecat-ai/websocket-transport";
import "./styles.css";

const app = document.querySelector("#app");

app.innerHTML = `
  <main class="shell">
    <header class="topbar">
      <a class="brand" href="/" aria-label="Flux Voice Lab home">
        <span class="brand-mark"><i></i><i></i><i></i></span>
        <span>Flux Voice Lab</span>
      </a>
      <div class="environment"><span class="status-dot"></span>Local test environment</div>
    </header>

    <section class="workspace">
      <aside class="config-panel">
        <div class="panel-heading">
          <p class="eyebrow">Voice bots</p>
          <h1>Pick a bot, then talk</h1>
          <p>Bots keep your agent configuration. API keys can be saved encrypted on the server, or provided once per session.</p>
        </div>

        <section class="bot-panel">
          <div class="list-head">
            <h2>Your bots</h2>
            <button id="new-bot-button" class="inline-button" type="button">+ New bot</button>
          </div>
          <div id="bot-list" class="bot-list"></div>
        </section>

        <section id="session-keys" class="session-keys" hidden>
          <div class="list-head"><h2>Session keys</h2></div>
          <p class="hint">This bot has no saved keys. Enter both keys for this session only — they are never saved.</p>
          <label for="session-deepgram-key">Deepgram API key</label>
          <div class="input-with-action">
            <input id="session-deepgram-key" type="password" autocomplete="new-password" />
            <button class="text-button reveal" type="button" data-target="session-deepgram-key">Show</button>
          </div>
          <label for="session-llm-key">LLM API key</label>
          <div class="input-with-action">
            <input id="session-llm-key" type="password" autocomplete="new-password" />
            <button class="text-button reveal" type="button" data-target="session-llm-key">Show</button>
          </div>
          <button id="test-session-llm" class="secondary-button diagnostic-button" type="button">Test selected bot LLM</button>
          <div id="session-diagnostic-result" class="diagnostic-result" hidden></div>
        </section>

        <section id="bot-editor" hidden>
          <div class="list-head"><h2 id="editor-title">New bot</h2></div>
          <form id="bot-form" autocomplete="off">
            <label for="bot-name">Bot name</label>
            <input id="bot-name" maxlength="100" required />

            <fieldset>
              <legend>Pipeline</legend>
              <label for="bot-asr">ASR provider</label>
              <select id="bot-asr">
                <option value="deepgram_flux">Deepgram Flux (English)</option>
              </select>

              <label for="bot-tts">TTS provider</label>
              <select id="bot-tts">
                <option value="deepgram_flux">Deepgram Flux</option>
              </select>

              <label for="bot-voice">Voice</label>
              <select id="bot-voice"></select>
              <article id="bot-voice-card" class="voice-card"></article>
              <div class="link-row">
                <a id="bot-voice-docs-link" href="#" target="_blank" rel="noreferrer">Voice catalog ↗</a>
                <a id="bot-voice-listen-link" href="#" target="_blank" rel="noreferrer">Listen ↗</a>
              </div>
            </fieldset>

            <fieldset>
              <legend>Intelligence</legend>
              <label for="bot-llm-provider">LLM provider</label>
              <select id="bot-llm-provider"></select>

              <label for="bot-llm-base-url">Base URL</label>
              <input id="bot-llm-base-url" type="url" required />

              <label for="bot-llm-model">Model</label>
              <input id="bot-llm-model" list="bot-model-options" required />
              <datalist id="bot-model-options"></datalist>
              <div class="field-help">
                <span>Choose a recommendation or type an exact model ID</span>
                <a id="bot-llm-models-link" href="#" target="_blank" rel="noreferrer">Model docs ↗</a>
              </div>

              <label for="bot-system-prompt">System prompt</label>
              <textarea id="bot-system-prompt" rows="5" maxlength="30000" required></textarea>

              <label for="bot-opening-script">Opening script</label>
              <textarea id="bot-opening-script" rows="3" maxlength="2000"></textarea>
              <p class="hint">Leave blank for a user-first conversation.</p>
              <button id="test-bot-llm" class="secondary-button diagnostic-button" type="button">Test LLM connection</button>
              <div id="bot-diagnostic-result" class="diagnostic-result" hidden></div>
            </fieldset>

            <fieldset>
              <legend>API keys</legend>
              <label class="checkbox-row" for="bot-save-keys">
                <input id="bot-save-keys" type="checkbox" />
                <span>Save API keys encrypted on the server</span>
              </label>
              <p id="keep-keys-hint" class="hint" hidden>
                Keys are saved for this bot. Leave both fields blank to keep them, or enter new keys to replace them.
              </p>
              <div id="bot-key-fields" hidden>
                <label for="bot-deepgram-key">Deepgram API key</label>
                <div class="input-with-action">
                  <input id="bot-deepgram-key" type="password" autocomplete="new-password" />
                  <button class="text-button reveal" type="button" data-target="bot-deepgram-key">Show</button>
                </div>
                <div class="field-help">
                  <span>Encrypted before storage · never returned by the API</span>
                  <a href="https://console.deepgram.com/" target="_blank" rel="noreferrer">Get a key ↗</a>
                </div>

                <label for="bot-llm-key">LLM API key</label>
                <div class="input-with-action">
                  <input id="bot-llm-key" type="password" autocomplete="new-password" />
                  <button class="text-button reveal" type="button" data-target="bot-llm-key">Show</button>
                </div>
                <div class="field-help">
                  <span>Encrypted before storage · never returned by the API</span>
                  <a id="bot-llm-key-link" href="#" target="_blank" rel="noreferrer">Get a key ↗</a>
                </div>
              </div>
              <p id="byok-hint" class="hint">
                Unchecked: keys are requested once per session and never saved (BYOK).
              </p>
            </fieldset>

            <div class="editor-actions">
              <button id="save-bot-button" class="primary-button" type="submit">Save bot</button>
              <button id="cancel-bot-button" class="secondary-button" type="button">Cancel</button>
            </div>
          </form>
        </section>

        <details class="quick-start">
          <summary>Quick start — one-off session without a bot</summary>
          <form id="session-form" autocomplete="off">
            <fieldset>
              <legend>Credentials</legend>
              <label for="deepgram-key">Deepgram API key</label>
              <div class="input-with-action">
                <input id="deepgram-key" type="password" autocomplete="new-password" required />
                <button class="text-button reveal" type="button" data-target="deepgram-key">Show</button>
              </div>
              <div class="field-help">
                <span>BYOK · used only for this session</span>
                <a href="https://console.deepgram.com/" target="_blank" rel="noreferrer">Get a key ↗</a>
              </div>

              <label for="llm-key">LLM API key</label>
              <div class="input-with-action">
                <input id="llm-key" type="password" autocomplete="new-password" required />
                <button class="text-button reveal" type="button" data-target="llm-key">Show</button>
              </div>
              <div class="field-help">
                <span>BYOK · kept in server memory only</span>
                <a id="llm-key-link" href="#" target="_blank" rel="noreferrer">Get a key ↗</a>
              </div>
            </fieldset>

            <fieldset>
              <legend>Intelligence</legend>
              <label for="llm-provider">LLM provider</label>
              <select id="llm-provider"></select>

              <label for="llm-base-url">Base URL</label>
              <input id="llm-base-url" type="url" required />

              <label for="llm-model">Model</label>
              <input id="llm-model" list="model-options" required />
              <datalist id="model-options"></datalist>
              <div class="field-help">
                <span>Choose a recommendation or type an exact model ID</span>
                <a id="llm-models-link" href="#" target="_blank" rel="noreferrer">Model docs ↗</a>
              </div>

              <label for="system-prompt">System prompt</label>
              <textarea id="system-prompt" rows="5" maxlength="30000" required></textarea>

              <label for="opening-script">Opening script</label>
              <textarea id="opening-script" rows="3" maxlength="2000"></textarea>
              <p class="hint">Leave blank for a user-first conversation.</p>
              <button id="test-quick-llm" class="secondary-button diagnostic-button" type="button">Test LLM connection</button>
              <div id="quick-diagnostic-result" class="diagnostic-result" hidden></div>
            </fieldset>

            <fieldset>
              <legend>Voice</legend>
              <label for="flux-voice">Flux voice</label>
              <select id="flux-voice"></select>
              <article id="voice-card" class="voice-card"></article>
              <div class="link-row">
                <a id="voice-docs-link" href="#" target="_blank" rel="noreferrer">Voice catalog ↗</a>
                <a id="voice-listen-link" href="#" target="_blank" rel="noreferrer">Listen ↗</a>
              </div>
            </fieldset>

            <button id="quick-start-button" class="primary-button" type="submit">
              Start one-off session
            </button>
          </form>
        </details>

        <section class="history-panel">
          <div class="list-head">
            <h2>Call history</h2>
            <button id="refresh-history" class="inline-button" type="button">Refresh</button>
          </div>
          <div id="history-list" class="history-list"></div>
        </section>
      </aside>

      <section class="conversation-panel">
        <div class="conversation-header">
          <div>
            <p class="eyebrow">Live session</p>
            <h2>Conversation</h2>
          </div>
          <div id="session-state" class="state-pill" data-state="idle">
            <span></span><b>Ready to start</b>
          </div>
        </div>

        <section class="stage" aria-live="polite">
          <div id="orb" class="orb" data-speaker="idle">
            <div class="orb-core"></div>
            <div class="orb-ring ring-one"></div>
            <div class="orb-ring ring-two"></div>
          </div>
          <p id="speaker-label" class="speaker-label">Select a bot, then start a session</p>
          <div class="waveform" aria-hidden="true">
            <i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i>
          </div>
        </section>

        <section id="transcript" class="transcript">
          <div class="empty-state">
            <span>Transcript</span>
            <p>Your English conversation will appear here in real time.</p>
          </div>
        </section>

        <section class="metrics-grid">
          <article><span>WebSocket</span><strong id="ws-status">Disconnected</strong></article>
          <article><span>ASR / LLM / TTS</span><strong id="pipeline-status">Standby</strong></article>
          <article><span>Turn → audio</span><strong id="e2e-latency">—</strong></article>
          <article><span>LLM → playback</span><strong id="synthesis-latency">—</strong></article>
        </section>

        <div id="error-banner" class="error-banner" role="alert" hidden></div>

        <footer class="controls">
          <button id="start-button" class="primary-button" type="button">
            <span class="mic-icon">●</span> Start session
          </button>
          <button id="end-button" class="secondary-button" type="button" disabled>End session</button>
          <p id="privacy-note">User audio is saved for 7 days; transcripts and metrics for 30 days.</p>
        </footer>
      </section>
    </section>
    <dialog id="history-dialog" class="history-dialog">
      <button id="close-history" class="text-button dialog-close" type="button">Close</button>
      <div id="history-detail"></div>
    </dialog>
  </main>
`;

const elements = {
  botList: document.querySelector("#bot-list"),
  newBot: document.querySelector("#new-bot-button"),
  editor: document.querySelector("#bot-editor"),
  editorTitle: document.querySelector("#editor-title"),
  botForm: document.querySelector("#bot-form"),
  botName: document.querySelector("#bot-name"),
  botAsr: document.querySelector("#bot-asr"),
  botTts: document.querySelector("#bot-tts"),
  botVoice: document.querySelector("#bot-voice"),
  botVoiceCard: document.querySelector("#bot-voice-card"),
  botVoiceDocs: document.querySelector("#bot-voice-docs-link"),
  botVoiceListen: document.querySelector("#bot-voice-listen-link"),
  botProvider: document.querySelector("#bot-llm-provider"),
  botBaseUrl: document.querySelector("#bot-llm-base-url"),
  botModel: document.querySelector("#bot-llm-model"),
  botModelOptions: document.querySelector("#bot-model-options"),
  botLlmKeyLink: document.querySelector("#bot-llm-key-link"),
  botLlmModelsLink: document.querySelector("#bot-llm-models-link"),
  botSystemPrompt: document.querySelector("#bot-system-prompt"),
  botOpeningScript: document.querySelector("#bot-opening-script"),
  testBotLlm: document.querySelector("#test-bot-llm"),
  botDiagnostic: document.querySelector("#bot-diagnostic-result"),
  botSaveKeys: document.querySelector("#bot-save-keys"),
  botKeyFields: document.querySelector("#bot-key-fields"),
  botDeepgramKey: document.querySelector("#bot-deepgram-key"),
  botLlmKey: document.querySelector("#bot-llm-key"),
  keepKeysHint: document.querySelector("#keep-keys-hint"),
  byokHint: document.querySelector("#byok-hint"),
  cancelBot: document.querySelector("#cancel-bot-button"),
  sessionKeys: document.querySelector("#session-keys"),
  sessionDeepgramKey: document.querySelector("#session-deepgram-key"),
  sessionLlmKey: document.querySelector("#session-llm-key"),
  testSessionLlm: document.querySelector("#test-session-llm"),
  sessionDiagnostic: document.querySelector("#session-diagnostic-result"),
  quickForm: document.querySelector("#session-form"),
  deepgramKey: document.querySelector("#deepgram-key"),
  llmKey: document.querySelector("#llm-key"),
  provider: document.querySelector("#llm-provider"),
  baseUrl: document.querySelector("#llm-base-url"),
  model: document.querySelector("#llm-model"),
  modelOptions: document.querySelector("#model-options"),
  systemPrompt: document.querySelector("#system-prompt"),
  openingScript: document.querySelector("#opening-script"),
  testQuickLlm: document.querySelector("#test-quick-llm"),
  quickDiagnostic: document.querySelector("#quick-diagnostic-result"),
  voice: document.querySelector("#flux-voice"),
  voiceCard: document.querySelector("#voice-card"),
  voiceDocs: document.querySelector("#voice-docs-link"),
  voiceListen: document.querySelector("#voice-listen-link"),
  llmKeyLink: document.querySelector("#llm-key-link"),
  llmModelsLink: document.querySelector("#llm-models-link"),
  start: document.querySelector("#start-button"),
  end: document.querySelector("#end-button"),
  state: document.querySelector("#session-state"),
  orb: document.querySelector("#orb"),
  speaker: document.querySelector("#speaker-label"),
  transcript: document.querySelector("#transcript"),
  wsStatus: document.querySelector("#ws-status"),
  pipelineStatus: document.querySelector("#pipeline-status"),
  e2eLatency: document.querySelector("#e2e-latency"),
  synthesisLatency: document.querySelector("#synthesis-latency"),
  error: document.querySelector("#error-banner"),
  historyList: document.querySelector("#history-list"),
  refreshHistory: document.querySelector("#refresh-history"),
  historyDialog: document.querySelector("#history-dialog"),
  historyDetail: document.querySelector("#history-detail"),
  closeHistory: document.querySelector("#close-history"),
};

let catalogs;
let bots = [];
let selectedBotId;
let editingBotId;
let client;
let sessionId;
let sessionToken;
let sessionStartedAt;
let userStoppedAt;
let llmFirstTokenAt;
let currentAssistantBubble;
let currentAssistantText = "";
let interimUserBubble;
let botSpeaking = false;

function setSessionState(state, label) {
  elements.state.dataset.state = state;
  elements.state.querySelector("b").textContent = label;
}

function setSpeaker(speaker, label) {
  elements.orb.dataset.speaker = speaker;
  elements.speaker.textContent = label;
}

function setFormLocked(locked) {
  for (const form of [elements.botForm, elements.quickForm]) {
    for (const control of form.elements) control.disabled = locked;
  }
  elements.newBot.disabled = locked;
  elements.sessionDeepgramKey.disabled = locked;
  elements.sessionLlmKey.disabled = locked;
  for (const button of elements.botList.querySelectorAll("button")) button.disabled = locked;
  elements.start.disabled = locked || !selectedBotId;
  elements.end.disabled = !locked;
}

function showError(message) {
  elements.error.textContent = message;
  elements.error.hidden = false;
}

function clearError() {
  elements.error.hidden = true;
  elements.error.textContent = "";
}

async function apiRequest(path, { method = "GET", body } = {}) {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const message = typeof error.detail === "string" ? error.detail : `Request failed (${response.status}).`;
    throw new Error(message);
  }
  if (response.status === 204) return undefined;
  return response.json();
}

function diagnosticPayload(kind) {
  if (kind === "bot") {
    const bot = editingBotId && bots.find((item) => item.id === editingBotId);
    if (bot?.has_saved_keys && !elements.botLlmKey.value) return { bot_id: bot.id };
    return {
      llm_provider: elements.botProvider.value,
      llm_base_url: elements.botBaseUrl.value,
      llm_model: elements.botModel.value,
      llm_api_key: elements.botLlmKey.value,
    };
  }
  return {
    llm_provider: elements.provider.value,
    llm_base_url: elements.baseUrl.value,
    llm_model: elements.model.value,
    llm_api_key: elements.llmKey.value,
  };
}

async function testLlm(kind) {
  clearError();
  const output = kind === "bot" ? elements.botDiagnostic : kind === "session" ? elements.sessionDiagnostic : elements.quickDiagnostic;
  const button = kind === "bot" ? elements.testBotLlm : kind === "session" ? elements.testSessionLlm : elements.testQuickLlm;
  button.disabled = true;
  output.hidden = false;
  output.textContent = "Testing a minimal request…";
  try {
    const result = await apiRequest("/api/llm/diagnostics", {
      method: "POST",
      body: kind === "session"
        ? { bot_id: selectedBotId, llm_api_key: elements.sessionLlmKey.value }
        : diagnosticPayload(kind),
    });
    output.dataset.success = String(result.success);
    const tokens = result.reasoning_tokens === null ? "not reported" : result.reasoning_tokens;
    output.textContent = `${result.success ? "Connected" : "Failed"} · ${result.provider}/${result.model}\n${result.summary}\nFirst token: ${result.first_token_ms ?? "—"} ms · Reasoning: ${result.reasoning_status} (${tokens} tokens)\n${result.suggestion} · ID ${result.diagnostic_id}`;
  } catch (error) {
    output.dataset.success = "false";
    output.textContent = error instanceof Error ? error.message : "Diagnostic failed.";
  } finally {
    button.disabled = false;
  }
}

async function loadHistory() {
  const data = await apiRequest("/api/history?limit=25&offset=0");
  if (!data.items.length) {
    elements.historyList.innerHTML = '<p class="empty-bots">No calls recorded yet.</p>';
    return;
  }
  elements.historyList.replaceChildren(...data.items.map((call) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "history-card";
    const duration = call.duration_ms === null ? "pending" : `${Math.round(call.duration_ms / 1000)}s`;
    button.textContent = `${call.bot_name || "One-off session"} · ${duration}\n${new Date(call.started_at).toLocaleString()} · ${call.status}`;
    button.addEventListener("click", () => showHistory(call.id));
    return button;
  }));
}

async function showHistory(callId) {
  const call = await apiRequest(`/api/history/${callId}`);
  elements.historyDetail.replaceChildren();
  const heading = document.createElement("h2");
  heading.textContent = call.bot_name || "One-off session";
  const meta = document.createElement("p");
  meta.textContent = `${new Date(call.started_at).toLocaleString()} · ${call.llm_provider}/${call.llm_model} · ${call.status}`;
  elements.historyDetail.append(heading, meta);
  if (call.has_recording) {
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.src = `/api/history/${call.id}/recording`;
    elements.historyDetail.append(audio);
  }
  for (const turn of call.turns) addHistoryTurn(turn);
  for (const metric of call.metrics) {
    const row = document.createElement("p");
    row.className = "history-metric";
    row.textContent = `Turn ${metric.turn_index + 1}: LLM ${metric.llm_first_token_ms ?? "—"} ms · TTS ${metric.tts_first_audio_ms ?? "—"} ms · playback ${metric.turn_to_playback_ms ?? "—"} ms · reasoning ${metric.reasoning_status}/${metric.reasoning_tokens ?? "not reported"}`;
    elements.historyDetail.append(row);
  }
  const remove = document.createElement("button");
  remove.className = "card-button danger";
  remove.textContent = "Delete call";
  remove.addEventListener("click", async () => {
    if (!window.confirm("Delete this call, transcript, metrics, and recording?")) return;
    await apiRequest(`/api/history/${call.id}`, { method: "DELETE" });
    elements.historyDialog.close();
    await loadHistory();
  });
  elements.historyDetail.append(remove);
  elements.historyDialog.showModal();
}

function addHistoryTurn(turn) {
  const item = document.createElement("article");
  item.className = `message ${turn.role === "user" ? "user" : "agent"}`;
  const label = document.createElement("span");
  label.textContent = turn.role === "user" ? "You" : "Agent";
  const text = document.createElement("p");
  text.textContent = turn.text;
  item.append(label, text);
  elements.historyDetail.append(item);
}

function addTranscript(role, text, { interim = false } = {}) {
  elements.transcript.querySelector(".empty-state")?.remove();
  const bubble = document.createElement("article");
  bubble.className = `message ${role}${interim ? " interim" : ""}`;
  const roleLabel = document.createElement("span");
  roleLabel.textContent = role === "user" ? "You" : "Agent";
  const content = document.createElement("p");
  content.textContent = text;
  bubble.append(roleLabel, content);
  elements.transcript.append(bubble);
  elements.transcript.scrollTop = elements.transcript.scrollHeight;
  return bubble;
}

function voiceEntry(modelId) {
  return catalogs.flux_voices.voices.find((entry) => entry.model_id === modelId);
}

function updateVoiceCard(selectEl, cardEl) {
  const voice = voiceEntry(selectEl.value);
  if (!voice) {
    cardEl.innerHTML = "";
    return;
  }
  cardEl.innerHTML = `
    <div><strong>${voice.name}</strong><code>${voice.model_id}</code></div>
    <p>${voice.accent} · ${voice.gender} · ${voice.age}</p>
    <p>${voice.traits.join(", ")}</p>
    <small>Best for ${voice.use_cases.join(", ")}</small>
  `;
}

function fillVoiceSelect(selectEl, selectedId) {
  selectEl.replaceChildren(
    ...catalogs.flux_voices.voices.map((voice) => {
      const option = document.createElement("option");
      option.value = voice.model_id;
      option.textContent = `${voice.name} — ${voice.accent}, ${voice.traits.slice(0, 2).join(" & ")}`;
      return option;
    }),
  );
  if (selectedId) selectEl.value = selectedId;
}

function fillProviderSelect(selectEl, selectedId) {
  selectEl.replaceChildren(
    ...catalogs.llm_providers.providers.map((provider) => {
      const option = document.createElement("option");
      option.value = provider.id;
      option.textContent = provider.name;
      return option;
    }),
  );
  if (selectedId) selectEl.value = selectedId;
}

function applyProviderPreset(refs, { preserveModel = false } = {}) {
  const provider = catalogs.llm_providers.providers.find(
    (entry) => entry.id === refs.provider.value,
  );
  if (!provider) return;
  refs.baseUrl.value = provider.base_url;
  refs.baseUrl.readOnly = provider.id !== "custom";
  refs.model.readOnly = !provider.supports_custom_model;
  if (!preserveModel) refs.model.value = provider.default_model;
  refs.modelOptions.replaceChildren(
    ...provider.recommended_models.map((model) => {
      const option = document.createElement("option");
      option.value = model;
      return option;
    }),
  );
  refs.keyLink.href = provider.api_key_url;
  refs.modelsLink.href = provider.models_url;
}

const quickProviderRefs = {
  provider: elements.provider,
  baseUrl: elements.baseUrl,
  model: elements.model,
  modelOptions: elements.modelOptions,
  keyLink: elements.llmKeyLink,
  modelsLink: elements.llmModelsLink,
};

const botProviderRefs = {
  provider: elements.botProvider,
  baseUrl: elements.botBaseUrl,
  model: elements.botModel,
  modelOptions: elements.botModelOptions,
  keyLink: elements.botLlmKeyLink,
  modelsLink: elements.botLlmModelsLink,
};

// --- Bot list and editor ----------------------------------------------------

function renderBotList() {
  if (!bots.length) {
    elements.botList.innerHTML = `<p class="empty-bots">No bots yet. Create your first bot to skip re-entering the configuration every time.</p>`;
  } else {
    elements.botList.replaceChildren(
      ...bots.map((bot) => {
        const voice = voiceEntry(bot.tts_voice);
        const card = document.createElement("article");
        card.className = "bot-card";
        card.dataset.selected = String(bot.id === selectedBotId);
        card.innerHTML = `
          <header>
            <strong></strong>
            ${bot.has_saved_keys ? '<span class="badge">Keys saved</span>' : '<span class="badge byok">BYOK</span>'}
          </header>
          <p></p>
          <div class="card-actions">
            <button class="card-button select-bot" type="button"></button>
            <button class="card-button edit-bot" type="button">Edit</button>
            <button class="card-button danger delete-bot" type="button">Delete</button>
          </div>
        `;
        card.querySelector("strong").textContent = bot.name;
        card.querySelector("p").textContent = `${bot.llm_model} · ${voice ? voice.name : bot.tts_voice}`;
        const selectButton = card.querySelector(".select-bot");
        selectButton.textContent = bot.id === selectedBotId ? "Selected" : "Select";
        selectButton.addEventListener("click", () => selectBot(bot.id));
        card.querySelector(".edit-bot").addEventListener("click", () => openEditor(bot));
        card.querySelector(".delete-bot").addEventListener("click", () => deleteBot(bot));
        return card;
      }),
    );
  }
  elements.sessionKeys.hidden = !selectedBot() || selectedBot().has_saved_keys;
  elements.start.disabled = !selectedBotId;
}

function selectedBot() {
  return bots.find((bot) => bot.id === selectedBotId);
}

function selectBot(botId) {
  selectedBotId = botId;
  renderBotList();
}

async function loadBots() {
  bots = await apiRequest("/api/bots");
  if (!selectedBot() && bots.length) selectedBotId = bots[0].id;
  renderBotList();
}

function syncKeyFieldVisibility() {
  const saving = elements.botSaveKeys.checked;
  const editingHasKeys = Boolean(
    editingBotId && bots.find((bot) => bot.id === editingBotId)?.has_saved_keys,
  );
  elements.botKeyFields.hidden = !saving;
  elements.byokHint.hidden = saving;
  elements.keepKeysHint.hidden = !(saving && editingHasKeys);
  const keysOptional = saving && editingHasKeys;
  elements.botDeepgramKey.required = saving && !keysOptional;
  elements.botLlmKey.required = saving && !keysOptional;
}

function openEditor(bot) {
  clearError();
  editingBotId = bot ? bot.id : null;
  elements.editorTitle.textContent = bot ? `Edit bot` : "New bot";
  elements.botName.value = bot ? bot.name : "";
  elements.botAsr.value = bot ? bot.asr_provider : "deepgram_flux";
  elements.botTts.value = bot ? bot.tts_provider : "deepgram_flux";
  fillVoiceSelect(elements.botVoice, bot ? bot.tts_voice : catalogs.defaults.flux_voice);
  updateVoiceCard(elements.botVoice, elements.botVoiceCard);
  fillProviderSelect(elements.botProvider, bot ? bot.llm_provider : catalogs.defaults.llm_provider);
  applyProviderPreset(botProviderRefs);
  if (bot) {
    elements.botBaseUrl.value = bot.llm_base_url;
    elements.botModel.value = bot.llm_model;
  }
  elements.botSystemPrompt.value = bot ? bot.system_prompt : catalogs.defaults.system_prompt;
  elements.botOpeningScript.value = bot ? bot.opening_script : catalogs.defaults.opening_script;
  elements.botSaveKeys.checked = bot ? bot.has_saved_keys : false;
  elements.botDeepgramKey.value = "";
  elements.botLlmKey.value = "";
  syncKeyFieldVisibility();
  elements.editor.hidden = false;
  elements.editor.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function closeEditor() {
  elements.editor.hidden = true;
  editingBotId = null;
}

async function saveBot(event) {
  event.preventDefault();
  clearError();
  const saving = elements.botSaveKeys.checked;
  const deepgramKey = elements.botDeepgramKey.value;
  const llmKey = elements.botLlmKey.value;
  if (saving && (deepgramKey || llmKey) && !(deepgramKey && llmKey)) {
    showError("Enter both API keys, or leave both fields blank to keep the saved keys.");
    return;
  }
  if (!elements.botForm.reportValidity()) return;

  const payload = {
    name: elements.botName.value.trim(),
    asr_provider: elements.botAsr.value,
    tts_provider: elements.botTts.value,
    tts_voice: elements.botVoice.value,
    llm_provider: elements.botProvider.value,
    llm_base_url: elements.botBaseUrl.value,
    llm_model: elements.botModel.value,
    system_prompt: elements.botSystemPrompt.value,
    opening_script: elements.botOpeningScript.value,
    save_keys: saving,
  };
  if (saving && deepgramKey && llmKey) {
    payload.deepgram_api_key = deepgramKey;
    payload.llm_api_key = llmKey;
  }

  try {
    const saved = editingBotId
      ? await apiRequest(`/api/bots/${editingBotId}`, { method: "PUT", body: payload })
      : await apiRequest("/api/bots", { method: "POST", body: payload });
    elements.botDeepgramKey.value = "";
    elements.botLlmKey.value = "";
    payload.deepgram_api_key = "";
    payload.llm_api_key = "";
    closeEditor();
    await loadBots();
    selectBot(saved.id);
  } catch (error) {
    showError(error instanceof Error ? error.message : "Could not save the bot.");
  }
}

async function deleteBot(bot) {
  clearError();
  const confirmed = window.confirm(
    `Delete bot "${bot.name}"? This also removes any saved API keys. This cannot be undone.`,
  );
  if (!confirmed) return;
  try {
    await apiRequest(`/api/bots/${bot.id}`, { method: "DELETE" });
    if (selectedBotId === bot.id) selectedBotId = undefined;
    await loadBots();
  } catch (error) {
    showError(error instanceof Error ? error.message : "Could not delete the bot.");
  }
}

// --- Session lifecycle --------------------------------------------------------

function websocketUrl(path) {
  const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${window.location.host}${path}`;
}

function ensureSecureContext() {
  const isLoopback = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
  if (window.location.protocol !== "https:" && !isLoopback) {
    showError("API keys require HTTPS outside localhost. Open the protected HTTPS demo URL.");
    return false;
  }
  return true;
}

function confirmUnverifiedReasoning(provider) {
  if (provider !== "custom") return true;
  return window.confirm(
    "This custom model has no verified reasoning-disable profile. It may add latency. Continue anyway?",
  );
}

function deviceErrorMessage(error) {
  const messages = {
    permissions: "Microphone permission is blocked. Allow it in browser and system settings.",
    "not-found": "No microphone was found. Connect an input device, then start a new session.",
    "in-use": "The microphone is already in use. Close other audio apps and try again.",
    constraints: "The selected microphone does not support the required audio settings.",
    "undefined-mediadevices": "This browser cannot access media devices. Use HTTPS or localhost.",
    unknown: "The microphone could not be initialized. Check the input device and retry.",
  };
  return messages[error?.type] || messages.unknown;
}

async function reportBrowserEvent(event) {
  if (!sessionId || !sessionToken || !sessionStartedAt) return;
  const elapsedMs = performance.now() - sessionStartedAt;
  try {
    await fetch(`/api/sessions/${sessionId}/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${sessionToken}`,
      },
      body: JSON.stringify({ event, elapsed_ms: elapsedMs }),
      keepalive: true,
    });
  } catch {
    // Telemetry must never interrupt the voice session.
  }
}

function createClient() {
  currentAssistantBubble = undefined;
  currentAssistantText = "";
  return new PipecatClient({
    transport: new WebSocketTransport({
      recorderSampleRate: catalogs.defaults.audio.input_sample_rate,
      playerSampleRate: catalogs.defaults.audio.output_sample_rate,
    }),
    enableMic: true,
    enableCam: false,
    disconnectOnBotDisconnect: true,
    callbacks: {
      onConnected: () => {
        elements.wsStatus.textContent = "Connected";
        elements.pipelineStatus.textContent = "Flux ready";
        setSessionState("connected", "Live");
      },
      onDisconnected: () => {
        elements.wsStatus.textContent = "Disconnected";
        elements.pipelineStatus.textContent = "Standby";
      },
      onTransportStateChanged: (state) => {
        elements.wsStatus.textContent = state[0].toUpperCase() + state.slice(1);
      },
      onBotReady: () => {
        setSpeaker("idle", "Listening for the conversation");
      },
      onDeviceError: (error) => {
        showError(deviceErrorMessage(error));
      },
      onError: () => {
        showError("A voice provider returned an error. Check both API keys, model access, and balance.");
        const failedSessionId = sessionId;
        window.setTimeout(async () => {
          if (!failedSessionId) return;
          try {
            const failed = await apiRequest(`/api/history/${failedSessionId}`);
            if (failed.diagnostic_id) {
              showError(`Provider error: ${failed.error_category}. Diagnostic ID: ${failed.diagnostic_id}`);
            }
          } catch {
            // Persistence may still be completing after the WebSocket error.
          }
        }, 750);
      },
      onMessageError: () => {
        showError("The voice connection received an invalid message. End and retry the session.");
      },
      onUserStartedSpeaking: () => {
        const interruptedBot = botSpeaking;
        botSpeaking = false;
        setSpeaker(
          "user",
          interruptedBot ? "You're speaking — Agent audio stopped" : "You're speaking",
        );
        elements.pipelineStatus.textContent = "Listening";
        if (interruptedBot) {
          reportBrowserEvent("browser_interruption");
          reportBrowserEvent("audio_stopped");
        }
        currentAssistantBubble = undefined;
        currentAssistantText = "";
      },
      onUserStoppedSpeaking: () => {
        userStoppedAt = performance.now();
        llmFirstTokenAt = undefined;
        setSpeaker("thinking", "Agent is thinking");
        elements.pipelineStatus.textContent = "ASR → LLM";
      },
      onBotStartedSpeaking: () => {
        const now = performance.now();
        botSpeaking = true;
        setSpeaker("agent", "Agent is speaking");
        elements.pipelineStatus.textContent = "Flux TTS playing";
        if (userStoppedAt) elements.e2eLatency.textContent = `${Math.round(now - userStoppedAt)} ms`;
        if (llmFirstTokenAt) {
          elements.synthesisLatency.textContent = `${Math.round(now - llmFirstTokenAt)} ms`;
        }
        reportBrowserEvent("first_playback");
      },
      onBotStoppedSpeaking: () => {
        botSpeaking = false;
        setSpeaker("idle", "Listening");
        elements.pipelineStatus.textContent = "Ready";
        currentAssistantBubble = undefined;
        currentAssistantText = "";
      },
      onUserTranscript: (data) => {
        const text = data.text.trim();
        if (!text) return;
        if (data.final) {
          interimUserBubble?.remove();
          interimUserBubble = undefined;
          addTranscript("user", text);
          return;
        }
        if (!interimUserBubble) interimUserBubble = addTranscript("user", text, { interim: true });
        interimUserBubble.querySelector("p").textContent = text;
      },
      onBotLlmText: (data) => {
        if (!llmFirstTokenAt) llmFirstTokenAt = performance.now();
        if (!currentAssistantBubble) currentAssistantBubble = addTranscript("agent", "");
        currentAssistantText += data.text;
        currentAssistantBubble.querySelector("p").textContent = currentAssistantText;
        elements.transcript.scrollTop = elements.transcript.scrollHeight;
      },
      onBotTtsText: (data) => {
        if (currentAssistantBubble || !data.text?.trim()) return;
        currentAssistantBubble = addTranscript("agent", data.text.trim());
        currentAssistantText = data.text.trim();
      },
      onMetrics: () => {
        // Human-facing latency uses actual browser callbacks above.
      },
    },
  });
}

async function connectSession(session) {
  sessionId = session.session_id;
  sessionToken = session.session_token;
  sessionStartedAt = performance.now();
  client = createClient();
  await client.initDevices();
  await client.connect({ wsUrl: websocketUrl(session.websocket_path) });
}

async function startBotSession() {
  clearError();
  const bot = selectedBot();
  if (!bot) {
    showError("Select a bot first, or create a new one.");
    return;
  }
  if (!ensureSecureContext()) return;
  if (!confirmUnverifiedReasoning(bot.llm_provider)) return;

  const payload = { bot_id: bot.id };
  if (!bot.has_saved_keys) {
    if (!elements.sessionDeepgramKey.value || !elements.sessionLlmKey.value) {
      showError("This bot has no saved keys. Enter both API keys for this session.");
      return;
    }
    payload.deepgram_api_key = elements.sessionDeepgramKey.value;
    payload.llm_api_key = elements.sessionLlmKey.value;
  }

  setFormLocked(true);
  setSessionState("connecting", "Connecting");
  setSpeaker("thinking", "Requesting microphone access");
  try {
    const session = await apiRequest("/api/sessions", { method: "POST", body: payload });
    elements.sessionDeepgramKey.value = "";
    elements.sessionLlmKey.value = "";
    payload.deepgram_api_key = "";
    payload.llm_api_key = "";
    await connectSession(session);
  } catch (error) {
    showError(error instanceof Error ? error.message : "Could not start the session.");
    await endSession({ preserveError: true });
  }
}

async function startQuickSession(event) {
  event.preventDefault();
  clearError();
  if (!ensureSecureContext()) return;
  if (!confirmUnverifiedReasoning(elements.provider.value)) return;
  if (!elements.quickForm.reportValidity()) return;
  setFormLocked(true);
  setSessionState("connecting", "Connecting");
  setSpeaker("thinking", "Requesting microphone access");

  const payload = {
    deepgram_api_key: elements.deepgramKey.value,
    llm_api_key: elements.llmKey.value,
    llm_provider: elements.provider.value,
    llm_base_url: elements.baseUrl.value,
    llm_model: elements.model.value,
    system_prompt: elements.systemPrompt.value,
    opening_script: elements.openingScript.value,
    flux_voice: elements.voice.value,
  };

  try {
    const session = await apiRequest("/api/sessions", { method: "POST", body: payload });
    elements.deepgramKey.value = "";
    elements.llmKey.value = "";
    payload.deepgram_api_key = "";
    payload.llm_api_key = "";
    await connectSession(session);
  } catch (error) {
    showError(error instanceof Error ? error.message : "Could not start the session.");
    await endSession({ preserveError: true });
  }
}

async function endSession({ preserveError = false } = {}) {
  try {
    await client?.disconnect();
  } catch {
    // The server still expires and clears the session lease.
  }
  client = undefined;
  sessionId = undefined;
  sessionToken = undefined;
  sessionStartedAt = undefined;
  userStoppedAt = undefined;
  llmFirstTokenAt = undefined;
  currentAssistantBubble = undefined;
  currentAssistantText = "";
  interimUserBubble = undefined;
  botSpeaking = false;
  setFormLocked(false);
  setSessionState("idle", "Ready to start");
  setSpeaker("idle", "Select a bot, then start a session");
  elements.wsStatus.textContent = "Disconnected";
  elements.pipelineStatus.textContent = "Standby";
  if (!preserveError) clearError();
  await loadHistory().catch(() => {});
}

// --- Wiring -------------------------------------------------------------------

document.querySelectorAll(".reveal").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.querySelector(`#${button.dataset.target}`);
    input.type = input.type === "password" ? "text" : "password";
    button.textContent = input.type === "password" ? "Show" : "Hide";
  });
});

elements.newBot.addEventListener("click", () => openEditor(null));
elements.cancelBot.addEventListener("click", closeEditor);
elements.botForm.addEventListener("submit", saveBot);
elements.botSaveKeys.addEventListener("change", syncKeyFieldVisibility);
elements.botProvider.addEventListener("change", () => applyProviderPreset(botProviderRefs));
elements.botVoice.addEventListener("change", () =>
  updateVoiceCard(elements.botVoice, elements.botVoiceCard),
);
elements.provider.addEventListener("change", () => applyProviderPreset(quickProviderRefs));
elements.voice.addEventListener("change", () => updateVoiceCard(elements.voice, elements.voiceCard));
elements.quickForm.addEventListener("submit", startQuickSession);
elements.start.addEventListener("click", startBotSession);
elements.end.addEventListener("click", () => endSession());
elements.testBotLlm.addEventListener("click", () => testLlm("bot"));
elements.testQuickLlm.addEventListener("click", () => testLlm("quick"));
elements.testSessionLlm.addEventListener("click", () => testLlm("session"));
elements.refreshHistory.addEventListener("click", () =>
  loadHistory().catch((error) => showError(error.message)),
);
elements.closeHistory.addEventListener("click", () => elements.historyDialog.close());

async function boot() {
  try {
    catalogs = await apiRequest("/api/catalogs");
  } catch {
    showError("The local Voice Agent server is unavailable. Start the backend and reload.");
    elements.start.disabled = true;
    elements.newBot.disabled = true;
    return;
  }

  fillProviderSelect(elements.provider, catalogs.defaults.llm_provider);
  applyProviderPreset(quickProviderRefs);
  fillVoiceSelect(elements.voice, catalogs.defaults.flux_voice);
  updateVoiceCard(elements.voice, elements.voiceCard);
  elements.systemPrompt.value = catalogs.defaults.system_prompt;
  elements.openingScript.value = catalogs.defaults.opening_script;
  elements.voiceDocs.href = catalogs.flux_voices.source_url;
  elements.voiceListen.href = catalogs.flux_voices.listen_url;
  elements.botVoiceDocs.href = catalogs.flux_voices.source_url;
  elements.botVoiceListen.href = catalogs.flux_voices.listen_url;

  try {
    await loadBots();
    await loadHistory();
  } catch {
    showError("Could not load your bots. Reload the page to try again.");
  }
}

boot();
