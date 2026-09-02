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
          <p class="eyebrow">Agent configuration</p>
          <h1>Build the voice</h1>
          <p>Keys are sent once to start this session and are never saved.</p>
        </div>

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
            <textarea id="system-prompt" rows="5" required></textarea>

            <label for="opening-script">Opening script</label>
            <textarea id="opening-script" rows="3"></textarea>
            <p class="hint">Leave blank for a user-first conversation.</p>
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
        </form>
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
          <p id="speaker-label" class="speaker-label">Configure your agent, then start a session</p>
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
          <p id="privacy-note">Microphone access is requested only after you press Start.</p>
        </footer>
      </section>
    </section>
  </main>
`;

const elements = {
  form: document.querySelector("#session-form"),
  deepgramKey: document.querySelector("#deepgram-key"),
  llmKey: document.querySelector("#llm-key"),
  provider: document.querySelector("#llm-provider"),
  baseUrl: document.querySelector("#llm-base-url"),
  model: document.querySelector("#llm-model"),
  modelOptions: document.querySelector("#model-options"),
  systemPrompt: document.querySelector("#system-prompt"),
  openingScript: document.querySelector("#opening-script"),
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
};

let catalogs;
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
  for (const control of elements.form.elements) control.disabled = locked;
  elements.start.disabled = locked;
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

function updateVoiceDetails() {
  const voice = catalogs.flux_voices.voices.find(
    (entry) => entry.model_id === elements.voice.value,
  );
  if (!voice) return;
  elements.voiceCard.innerHTML = `
    <div><strong>${voice.name}</strong><code>${voice.model_id}</code></div>
    <p>${voice.accent} · ${voice.gender} · ${voice.age}</p>
    <p>${voice.traits.join(", ")}</p>
    <small>Best for ${voice.use_cases.join(", ")}</small>
  `;
}

function updateProvider({ preserveModel = false } = {}) {
  const provider = catalogs.llm_providers.providers.find(
    (entry) => entry.id === elements.provider.value,
  );
  if (!provider) return;
  elements.baseUrl.value = provider.base_url;
  elements.baseUrl.readOnly = provider.id !== "custom";
  if (!preserveModel) elements.model.value = provider.default_model;
  elements.modelOptions.replaceChildren(
    ...provider.recommended_models.map((model) => {
      const option = document.createElement("option");
      option.value = model;
      return option;
    }),
  );
  elements.llmKeyLink.href = provider.api_key_url;
  elements.llmModelsLink.href = provider.models_url;
}

async function loadCatalogs() {
  const response = await fetch("/api/catalogs", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Could not load the server configuration.");
  catalogs = await response.json();

  elements.provider.replaceChildren(
    ...catalogs.llm_providers.providers.map((provider) => {
      const option = document.createElement("option");
      option.value = provider.id;
      option.textContent = provider.name;
      return option;
    }),
  );
  elements.voice.replaceChildren(
    ...catalogs.flux_voices.voices.map((voice) => {
      const option = document.createElement("option");
      option.value = voice.model_id;
      option.textContent = `${voice.name} — ${voice.accent}, ${voice.traits.slice(0, 2).join(" & ")}`;
      return option;
    }),
  );

  elements.provider.value = catalogs.defaults.llm_provider;
  elements.systemPrompt.value = catalogs.defaults.system_prompt;
  elements.openingScript.value = catalogs.defaults.opening_script;
  elements.voice.value = catalogs.defaults.flux_voice;
  elements.voiceDocs.href = catalogs.flux_voices.source_url;
  elements.voiceListen.href = catalogs.flux_voices.listen_url;
  updateProvider();
  updateVoiceDetails();
}

function websocketUrl(path) {
  const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${window.location.host}${path}`;
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

async function startSession() {
  clearError();
  const isLoopback = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
  if (window.location.protocol !== "https:" && !isLoopback) {
    showError("BYOK requires HTTPS outside localhost. Open the protected HTTPS demo URL.");
    return;
  }
  if (!elements.form.reportValidity()) return;
  setFormLocked(true);
  setSessionState("connecting", "Connecting");
  setSpeaker("thinking", "Requesting microphone access");

  const request = {
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
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
    request.deepgram_api_key = "";
    request.llm_api_key = "";
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(typeof error.detail === "string" ? error.detail : "Session creation failed.");
    }
    const session = await response.json();
    elements.deepgramKey.value = "";
    elements.llmKey.value = "";
    sessionId = session.session_id;
    sessionToken = session.session_token;
    sessionStartedAt = performance.now();
    client = createClient();
    await client.initDevices();
    await client.connect({ wsUrl: websocketUrl(session.websocket_path) });
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
  setSpeaker("idle", "Configure your agent, then start a session");
  elements.wsStatus.textContent = "Disconnected";
  elements.pipelineStatus.textContent = "Standby";
  if (!preserveError) clearError();
}

document.querySelectorAll(".reveal").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.querySelector(`#${button.dataset.target}`);
    input.type = input.type === "password" ? "text" : "password";
    button.textContent = input.type === "password" ? "Show" : "Hide";
  });
});
elements.provider.addEventListener("change", () => updateProvider());
elements.voice.addEventListener("change", updateVoiceDetails);
elements.start.addEventListener("click", startSession);
elements.end.addEventListener("click", () => endSession());

loadCatalogs().catch(() => {
  showError("The local Voice Agent server is unavailable. Start the backend and reload.");
  elements.start.disabled = true;
});
