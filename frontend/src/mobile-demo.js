import { PipecatClient } from "@pipecat-ai/client-js";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import "./mobile-demo.css";

const app = document.querySelector("#app");
const fixtureState = new URLSearchParams(location.search).get("fixture");
const publicId = location.pathname.split("/").filter(Boolean).at(-1);
const fixture = {
  public_id: "maya-a7k9",
  title: "Maya · Voice guide",
  description: "A responsive voice guide for natural, real-time conversations.",
  active: true,
};
const fixtureTurns = [
  ["agent", "Hi, I’m Maya. What would you like to explore today?"],
  ["user", "I want to understand what makes this voice agent feel responsive."],
  ["agent", "I listen continuously, respond quickly, and stop speaking when you interrupt."],
  ["user", "Can you explain how natural interruption works?"],
];

app.innerHTML = `
  <main class="demo-page">
    <section class="phone-shell" aria-label="VoiceAgent mobile demo">
      <section class="screen active" data-screen="ready" aria-labelledby="ready-title">
        <header class="topline"><span class="brand"><i></i><i></i><i></i><b>VoiceAgent</b></span><span class="secure">⌾ Private call</span></header>
        <div class="ready-content"><div class="avatar-wrap"><div class="avatar">V</div></div><p class="eyebrow">Ready to talk</p><h1 id="ready-title">Voice demo</h1><p id="demo-description" class="description"></p><div class="chips"><span>● Live voice</span><span>● Natural interruption</span><span>● English</span></div></div>
        <footer><button id="start-call" class="primary" type="button">Start voice call</button><p class="privacy"><strong>Before you start:</strong> your voice is stored for 7 days; transcripts and call metrics for 30 days.</p></footer>
      </section>

      <section class="screen" data-screen="connecting" aria-live="polite"><header class="topline"><span class="brand"><i></i><i></i><i></i><b>VoiceAgent</b></span><span class="secure">WebRTC</span></header><div class="center-state"><div class="loader"><span></span></div><h2>Connecting your call</h2><p>Preparing secure audio and checking your microphone. This usually takes a few seconds.</p></div><p class="privacy">Keep this page open while the call connects.</p></section>

      <section class="screen call-screen" data-screen="live" aria-labelledby="call-title">
        <header class="call-header"><button id="transcript-top" class="icon" type="button" aria-label="Open transcript">≡</button><div><strong id="call-title">Voice guide</strong><span><i></i><b id="timer">00:00</b></span></div><span></span></header>
        <div class="call-stage"><div id="live-orb" class="live-orb" data-mode="listening"><span></span></div><p id="mode-label" class="mode-label">Listening</p><p id="mode-hint" class="mode-hint">Go ahead — your guide can hear you.</p>
          <article class="caption-card"><div class="caption-meta"><span>Live captions</span><button id="view-transcript" type="button">View transcript</button></div><div class="caption-window"><div id="caption-history" class="caption-history"></div></div></article>
          <div id="quality-banner" class="quality" hidden>△ Network is unstable. Reconnecting…</div>
        </div>
        <footer class="call-controls"><button id="mute" type="button" aria-pressed="false"><span>♩</span>Mute</button><button id="end" class="end" type="button"><span>⌕</span>End</button><button id="captions" type="button" aria-pressed="true"><span>▤</span>Captions</button></footer>
      </section>

      <section class="screen" data-screen="ended"><div class="center-state"><div class="result">✓</div><h2>Call ended</h2><p>Your conversation has been saved to the Bot’s session history.</p><div class="stats"><div><span>Duration</span><strong id="final-duration">00:00</strong></div><div><span>Connection</span><strong>WebRTC</strong></div></div></div><button id="call-again" class="primary" type="button">Call again</button></section>
      <section class="screen" data-screen="error"><div class="center-state"><div class="result error">!</div><h2 id="error-title">Couldn’t connect</h2><p id="error-copy">Check microphone access and your network, then try again.</p></div><button id="retry" class="primary" type="button">Try again</button></section>

      <div id="sheet-backdrop" class="sheet-backdrop"></div><aside id="transcript-sheet" class="sheet" aria-label="Full transcript" aria-hidden="true"><div class="handle"></div><header><h3>Transcript</h3><button id="close-transcript" type="button">Close</button></header><div id="messages" class="messages"></div></aside>
    </section>
  </main>`;

const refs = Object.fromEntries([...document.querySelectorAll("[id]")].map((item) => [item.id, item]));
let metadata;
let client;
let transport;
let startedAt;
let timerId;
let connectionMonitorId;
let endingCall = false;
let attemptStartedAt;
let sessionId;
let sessionToken;
let connectionStage = "permission";
let turns = [];
let currentAgent = "";
const unavailableCopy = "This demo is no longer available.";
const pageLoadedAt = performance.now();

function showScreen(name) {
  document.querySelectorAll("[data-screen]").forEach((screen) => screen.classList.toggle("active", screen.dataset.screen === name));
}

function renderTurns() {
  const recent = turns.slice(-4);
  refs["caption-history"].replaceChildren(...recent.map(([role, text]) => {
    const item = document.createElement("div"); item.className = "caption-turn";
    const who = document.createElement("small"); who.textContent = role === "agent" ? "Maya" : "You";
    const copy = document.createElement("p"); copy.textContent = text;
    item.append(who, copy); return item;
  }));
  refs.messages.replaceChildren(...turns.map(([role, text]) => {
    const item = document.createElement("article"); item.className = `message ${role}`;
    const who = document.createElement("small"); who.textContent = role === "agent" ? "Maya" : "You";
    const copy = document.createElement("p"); copy.textContent = text;
    item.append(who, copy); return item;
  }));
  refs.messages.scrollTop = refs.messages.scrollHeight;
}

function addTurn(role, text, { append = false } = {}) {
  const clean = text?.trim(); if (!clean) return;
  if (append && turns.at(-1)?.[0] === role) turns[turns.length - 1][1] += text;
  else turns.push([role, clean]);
  renderTurns();
}

function setMode(mode, label, hint) {
  refs["live-orb"].dataset.mode = mode;
  refs["mode-label"].textContent = label;
  refs["mode-hint"].textContent = hint;
}

function formatDuration() {
  const seconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function beginTimer() { startedAt = Date.now(); refs.timer.textContent = "00:00"; timerId = setInterval(() => { refs.timer.textContent = formatDuration(); }, 1000); }
function stopTimer() { clearInterval(timerId); clearInterval(connectionMonitorId); refs["final-duration"].textContent = startedAt ? formatDuration() : "00:00"; }
function openTranscript(open) { refs["transcript-sheet"].classList.toggle("open", open); refs["sheet-backdrop"].classList.toggle("open", open); refs["transcript-sheet"].setAttribute("aria-hidden", String(!open)); }

async function loadMetadata() {
  if (fixtureState) return fixture;
  const response = await fetch(`/api/public/demos/${encodeURIComponent(publicId || "")}`, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(unavailableCopy);
  return response.json();
}

async function reportPublicEvent(event, result) {
  if (fixtureState || !metadata?.public_id) return;
  try {
    await fetch(`/api/public/demos/${encodeURIComponent(metadata.public_id)}/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event,
        elapsed_ms: performance.now() - pageLoadedAt,
        ...(result ? { result } : {}),
      }),
      keepalive: true,
    });
  } catch {
    // Telemetry never blocks the public call flow.
  }
}

function safeNetworkType() {
  const value = navigator.connection?.effectiveType;
  return ["slow-2g", "2g", "3g", "4g"].includes(value) ? value : "unknown";
}

async function selectedCandidateType() {
  try {
    const stats = await transport?.pc?.getStats();
    if (!stats) return "unknown";
    const pair = [...stats.values()].find((item) => (
      item.type === "candidate-pair"
      && item.state === "succeeded"
      && (item.selected || item.nominated)
    ));
    const candidate = pair ? stats.get(pair.localCandidateId) : undefined;
    return ["host", "srflx", "prflx", "relay"].includes(candidate?.candidateType)
      ? candidate.candidateType
      : "unknown";
  } catch {
    return "unknown";
  }
}

async function reportSessionEvent(event, details = {}) {
  if (!sessionId || !sessionToken || !attemptStartedAt) return;
  try {
    await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${sessionToken}`,
      },
      body: JSON.stringify({
        event,
        elapsed_ms: performance.now() - attemptStartedAt,
        ...details,
      }),
      keepalive: true,
    });
  } catch {
    // Telemetry never blocks media cleanup or recovery.
  }
}

function showReconnectState(active) {
  refs["quality-banner"].hidden = !active;
  if (active) setMode("reconnecting", "Reconnecting", "Keeping your call alive…");
  else setMode("listening", "Listening", "Go ahead — your guide can hear you.");
}

function monitorConnection() {
  clearInterval(connectionMonitorId);
  connectionMonitorId = setInterval(() => {
    const state = transport?.pc?.iceConnectionState;
    const reconnecting = Boolean(transport?.isReconnecting) || state === "disconnected" || state === "failed";
    if (reconnecting !== !refs["quality-banner"].hidden) showReconnectState(reconnecting);
  }, 250);
}

function createClient() {
  transport = new SmallWebRTCTransport();
  return new PipecatClient({ transport, enableMic: true, enableCam: false, disconnectOnBotDisconnect: true, callbacks: {
    onConnected: () => {
      connectionStage = "live";
      showScreen("live"); if (!startedAt) beginTimer(); showReconnectState(false); monitorConnection();
      void selectedCandidateType().then((candidateType) => reportSessionEvent("mobile_webrtc_connected", {
        candidate_type: candidateType,
        network_type: safeNetworkType(),
      }));
    },
    onDisconnected: () => { if (startedAt && !endingCall) void failCall("Call interrupted", "Check your network and try the call again.", "call_interrupted", "disconnect"); },
    onTransportStateChanged: (state) => {
      if (startedAt && state === "connecting") showReconnectState(true);
      if (startedAt && (state === "connected" || state === "ready")) showReconnectState(false);
    },
    onBotReady: () => setMode("listening", "Listening", "Go ahead — your guide can hear you."),
    onUserStartedSpeaking: () => setMode("listening", "Listening", "You’re speaking — Maya is listening."),
    onUserStoppedSpeaking: () => setMode("thinking", "Thinking", "Maya is preparing a response."),
    onBotStartedSpeaking: () => setMode("speaking", "Speaking", "You can interrupt naturally at any time."),
    onBotStoppedSpeaking: () => { currentAgent = ""; setMode("listening", "Listening", "Go ahead — your guide can hear you."); },
    onUserTranscript: (data) => { if (data.final) addTurn("user", data.text); },
    onBotTtsText: (data) => { addTurn("agent", data.text, { append: Boolean(currentAgent) }); currentAgent += data.text; },
    onDeviceError: () => { if (startedAt) void failCall("Microphone unavailable", "Allow microphone access in your browser, then try again.", "microphone_unavailable", "provider"); },
    onError: () => { if (startedAt) void failCall("Call interrupted", "Check your network and try the call again.", "call_interrupted", "provider"); },
  }});
}

async function startCall() {
  if (fixtureState) { turns = fixtureTurns.map((turn) => [...turn]); renderTurns(); showScreen("live"); beginTimer(); if (fixtureState === "reconnecting") { refs["quality-banner"].hidden = false; setMode("reconnecting", "Reconnecting", "Keeping your call alive…"); } return; }
  showScreen("connecting");
  endingCall = false;
  attemptStartedAt = performance.now();
  sessionId = undefined;
  sessionToken = undefined;
  connectionStage = "permission";
  void reportPublicEvent("mobile_call_start_click");
  try {
    client = createClient();
    try {
      const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      permissionStream.getTracks().forEach((track) => track.stop());
      await client.initDevices();
      void reportPublicEvent("mobile_mic_permission", "granted");
    } catch (error) {
      const denied = error?.name === "NotAllowedError"
        || error?.name === "SecurityError"
        || error?.type === "permissions";
      void reportPublicEvent("mobile_mic_permission", denied ? "denied" : "unavailable");
      throw new Error(denied
        ? "Open this site’s browser settings, allow Microphone access, then try again."
        : "Check that a microphone is connected and available, then try again.");
    }
    connectionStage = "session";
    const response = await fetch(`/api/public/demos/${encodeURIComponent(metadata.public_id)}/sessions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (!response.ok) throw new Error(response.status === 429 ? "This demo is busy. Please try again shortly." : unavailableCopy);
    const session = await response.json();
    sessionId = session.session_id;
    sessionToken = decodeURIComponent(session.connection_url.split("/").at(-1));
    connectionStage = "signaling";
    transport.iceServers = session.ice_servers || [];
    await client.connect({ connection_url: session.connection_url });
  } catch (error) {
    const category = connectionStage === "permission" ? "microphone_unavailable"
      : connectionStage === "session" ? "session_unavailable" : "connection_failed";
    await failCall("Couldn’t connect", error.message, category, "connection");
  }
}

async function releaseClient() { endingCall = true; try { await client?.disconnect(); } catch {} client = undefined; transport = undefined; }
async function finishCall() { stopTimer(); await reportSessionEvent("mobile_call_end", { end_reason: "user" }); await releaseClient(); startedAt = undefined; sessionId = undefined; sessionToken = undefined; showScreen("ended"); }
async function failCall(title, copy, safeErrorCategory = "connection_failed", endReason = "connection") { stopTimer(); await reportSessionEvent("mobile_call_error", { safe_error_category: safeErrorCategory, stage: connectionStage, end_reason: endReason }); await releaseClient(); startedAt = undefined; sessionId = undefined; sessionToken = undefined; showError(title, copy); }
function showError(title, copy) { stopTimer(); startedAt = undefined; refs["error-title"].textContent = title; refs["error-copy"].textContent = copy; showScreen("error"); }

function applyFixtureState() {
  if (!fixtureState || fixtureState === "ready") return;
  if (fixtureState === "connecting") { showScreen("connecting"); return; }
  if (fixtureState === "error") { showError("Couldn’t connect", "Check microphone access and your network, then try again."); return; }
  if (fixtureState === "ended") { refs["final-duration"].textContent = "02:05"; showScreen("ended"); return; }
  startCall();
}

refs["start-call"].addEventListener("click", startCall); refs.end.addEventListener("click", finishCall); refs["call-again"].addEventListener("click", () => { turns = []; renderTurns(); showScreen("ready"); }); refs.retry.addEventListener("click", startCall);
refs["view-transcript"].addEventListener("click", () => openTranscript(true)); refs["transcript-top"].addEventListener("click", () => openTranscript(true)); refs["close-transcript"].addEventListener("click", () => openTranscript(false)); refs["sheet-backdrop"].addEventListener("click", () => openTranscript(false));
refs.mute.addEventListener("click", () => { const next = refs.mute.getAttribute("aria-pressed") !== "true"; refs.mute.setAttribute("aria-pressed", String(next)); transport?.enableMic(!next); }); refs.captions.addEventListener("click", () => { const next = refs.captions.getAttribute("aria-pressed") !== "true"; refs.captions.setAttribute("aria-pressed", String(next)); document.querySelector(".caption-card").hidden = !next; });

loadMetadata().then((value) => { metadata = value; if (!metadata.active || metadata.available === false) throw new Error(unavailableCopy); refs["ready-title"].textContent = metadata.title; refs["call-title"].textContent = metadata.title; refs["demo-description"].textContent = metadata.description || ""; refs["demo-description"].hidden = !metadata.description; document.title = `${metadata.title} · VoiceAgent`; void reportPublicEvent("mobile_demo_view"); applyFixtureState(); }).catch(() => showError("Demo unavailable", unavailableCopy));
