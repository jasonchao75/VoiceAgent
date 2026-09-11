import { PipecatClient } from "@pipecat-ai/client-js";
import { WavMediaManager, WebSocketTransport } from "@pipecat-ai/websocket-transport";
import "./styles.css";

class OutputOnlyMediaManager extends WavMediaManager {
  async initialize() {
    if (this._initialized) return;
    await this._wavStreamPlayer.connect();
    this._initialized = true;
  }

  async connect() {
    await this.initialize();
  }

  async disconnect() {
    if (!this._initialized) return;
    await this._wavStreamPlayer.interrupt();
    this._initialized = false;
  }
}

const app = document.querySelector("#app");

app.innerHTML = `
  <main class="shell">
    <aside class="product-rail expanded"><button id="toggle-product-rail" type="button" aria-label="Collapse product rail">☰</button><a href="/" aria-label="VoiceAgent Demo home"><span>V</span><b>VoiceAgent Demo</b></a><div class="account-control"><button id="account-avatar" type="button" aria-haspopup="true" aria-expanded="false" aria-label="User menu">V</button><div class="account-menu"><span>Shared demo user</span><button id="logout-button" type="button">Log out</button></div></div></aside>
    <header class="topbar">
      <a class="brand" href="/" aria-label="VoiceAgent Demo home">
        <span class="brand-mark"><i></i><i></i><i></i></span>
        <span>VoiceAgent Demo</span>
      </a>
      <div class="environment"><span class="status-dot"></span>Local test environment</div>
    </header>
    <nav class="product-tabs" aria-label="VoiceAgent sections">
      <button class="active" type="button" data-page="settings">Bot settings</button>
      <button type="button" data-page="sessions">Sessions</button>
      <button type="button" data-page="advanced">Advanced</button>
    </nav>
    <aside id="session-expiry" class="session-expiry" role="status" hidden><span>Your login will expire in 5 minutes.</span><button id="continue-session" type="button">Stay signed in</button></aside>
    <section id="advanced-empty" class="advanced-empty" hidden>
      <p class="eyebrow">Bot behavior</p><h2>Advanced settings</h2>
      <p id="advanced-bot-context" class="advanced-bot-context">Select a Bot to configure its advanced behavior.</p>
      <label for="bot-fallback-script">Fallback script</label>
      <textarea id="bot-fallback-script" rows="4" maxlength="2000" placeholder="Sorry, I’m having trouble responding right now. Please try again."></textarea>
      <p class="hint">Played through TTS when the LLM does not complete before its configured request timeout.</p>
      <button id="save-advanced-settings" class="primary-button" type="button">Save advanced settings</button>
    </section>

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
          <div id="session-elevenlabs-key-field" hidden>
            <label for="session-elevenlabs-key">ElevenLabs API key</label>
            <div class="input-with-action">
              <input id="session-elevenlabs-key" type="password" autocomplete="new-password" />
              <button class="text-button reveal" type="button" data-target="session-elevenlabs-key">Show</button>
            </div>
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
                <option value="deepgram_flux">Deepgram</option>
              </select>
              <label for="bot-asr-model">Model</label>
              <select id="bot-asr-model" disabled></select>
              <label for="bot-asr-language">Language</label>
              <select id="bot-asr-language" disabled></select>
              <div id="bot-asr-hints-field" hidden>
                <label for="bot-asr-hints">Language hints</label>
                <select id="bot-asr-hints" class="asr-hints-select" multiple></select>
                <div id="bot-asr-hint-chips" class="language-grid" role="group" aria-label="Optional language hints"></div>
                <p class="hint">Optional. Automatic detects English, Spanish, French, German, Hindi, Russian, Portuguese, Japanese, Italian, and Dutch.</p>
              </div>
              <details class="voice-advanced">
                <summary>ASR Advanced</summary>
                <div class="voice-setting">
                  <div>
                    <label for="bot-asr-eot-threshold">EOT threshold</label>
                    <output id="bot-asr-eot-threshold-value">0.70</output>
                  </div>
                  <input id="bot-asr-eot-threshold" type="range" min="0.5" max="1" step="0.05" value="0.7" />
                  <small>Earlier turn completion ↔ More confidence</small>
                </div>
                <label for="bot-asr-eot-timeout">EOT timeout (ms)</label>
                <input id="bot-asr-eot-timeout" type="number" min="500" max="60000" step="100" value="5000" />
                <label for="bot-asr-keyterms">Keyterms · one plain phrase per line</label>
                <textarea id="bot-asr-keyterms" rows="4" placeholder="Riyad Bank&#10;customer service"></textarea>
                <label class="switch-row"><span><b>Profanity filter</b><small>Replace or remove recognized profanity.</small></span><input id="bot-asr-profanity" type="checkbox" /></label>
                <label class="switch-row"><span><b>Numerals</b><small>Convert spoken numbers to numeric form.</small></span><input id="bot-asr-numerals" type="checkbox" /></label>
                <label for="bot-asr-redact">Redact</label>
                <select id="bot-asr-redact"><option value="">Off</option><option value="numbers">Numbers</option><option value="aggressive_numbers">Aggressive numbers</option></select>
              </details>

              <label for="bot-tts">TTS provider</label>
              <select id="bot-tts">
                <option value="deepgram_flux">Deepgram Flux</option>
                <option value="elevenlabs">ElevenLabs</option>
              </select>

              <label for="bot-tts-aggregation">TTS text aggregation</label>
              <select id="bot-tts-aggregation">
                <option value="token">Token · Lowest latency</option>
                <option value="sentence">Sentence · More stable prosody</option>
              </select>
              <p class="hint">Token streams LLM output immediately; Sentence waits for a sentence boundary.</p>

              <label for="bot-voice">Voice</label>
              <select id="bot-voice" hidden></select>
              <button id="choose-bot-voice" class="voice-picker-trigger" type="button">Choose voice</button>
              <article id="bot-voice-card" class="voice-card"></article>
              <div class="link-row">
                <a id="bot-voice-docs-link" href="#" target="_blank" rel="noreferrer">Voice catalog ↗</a>
                <a id="bot-voice-listen-link" href="#" target="_blank" rel="noreferrer">Listen ↗</a>
              </div>
            </fieldset>

            <fieldset id="flux-tuning">
              <legend>Deepgram Flux voice tuning</legend>
              <div class="voice-setting"><div><label for="bot-flux-expressivity">Expressivity</label><output id="bot-flux-expressivity-value">0</output></div><input id="bot-flux-expressivity" type="range" min="-2" max="2" step="1" value="0"><small>Calm (-2) · Neutral (0) · Animated (2)</small></div>
              <label class="switch-row"><span><b>Model improvement opt-out</b><small>Do not use this session data for Deepgram model improvement.</small></span><input id="bot-flux-mip-opt-out" type="checkbox"></label>
              <div class="voice-setting"><div><label for="bot-flux-speed">Initial speed</label><output id="bot-flux-speed-value">1.00</output></div><input id="bot-flux-speed" type="range" min="0.5" max="1.5" step="0.05" value="1"><small>Extreme values may sound less natural.</small></div>
              <p class="hint">Expressivity changes delivery style, not quality. Positive values sound more animated and may need voice-by-voice auditioning.</p>
            </fieldset>

            <fieldset id="elevenlabs-tuning" hidden>
              <legend>ElevenLabs voice tuning</legend>
              <label for="bot-tts-model">Model</label>
              <select id="bot-tts-model"></select>
              <p id="bot-tts-model-hint" class="hint"></p>
              <details class="voice-advanced" open>
                <summary>Voice settings</summary>
                <div class="voice-setting"><div><label for="bot-tts-stability">Stability</label><output id="bot-tts-stability-value">0.50</output></div><input id="bot-tts-stability" type="range" min="0" max="1" step="0.05" value="0.5"><small id="bot-tts-stability-scale">More variable ↔ More stable</small></div>
                <div class="voice-setting"><div><label for="bot-tts-similarity">Clarity + Similarity</label><output id="bot-tts-similarity-value">0.80</output></div><input id="bot-tts-similarity" type="range" min="0" max="1" step="0.05" value="0.8"><small>Low ↔ High</small></div>
                <div class="voice-setting"><div><label for="bot-tts-style">Style exaggeration</label><output id="bot-tts-style-value">0.00</output></div><input id="bot-tts-style" type="range" min="0" max="1" step="0.05" value="0"><small>Natural / faster ↔ Exaggerated</small></div>
                <div class="voice-setting"><div><label for="bot-tts-speed">Initial speed</label><output id="bot-tts-speed-value">1.00</output></div><input id="bot-tts-speed" type="range" min="0.7" max="1.2" step="0.05" value="1"><small>Slower ↔ Faster</small></div>
                <label class="switch-row"><span><b>Use speaker boost</b><small>May improve similarity at some generation cost.</small></span><input id="bot-tts-speaker-boost" type="checkbox"></label>
                <label class="switch-row"><span><b>Auto mode <em id="bot-auto-mode-state">Off · derived</em></b><small id="bot-auto-mode-hint">Token input keeps ElevenLabs chunk scheduling enabled.</small></span><input id="bot-auto-mode" type="checkbox" disabled></label>
                <label for="bot-text-normalization">Text normalization</label>
                <select id="bot-text-normalization"><option value="auto">Auto · Recommended</option><option value="on">On · Force numbers/dates into spoken form</option><option value="off">Off · Synthesize original text</option></select>
              </details>
            </fieldset>

            <fieldset id="conversational-speed">
              <legend>Conversational speed control</legend>
              <label class="switch-row"><span><b>Allow in-call changes</b><small>Callers can ask the Agent to speak faster or slower for this session.</small></span><input id="bot-dynamic-speed" type="checkbox"></label>
              <label for="bot-speed-step">Adjustment step</label><select id="bot-speed-step"><option value="0.05">0.05</option><option value="0.1" selected>0.10</option><option value="0.15">0.15</option><option value="0.2">0.20</option><option value="0.25">0.25</option></select>
              <p id="dynamic-speed-hint" class="hint"></p>
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
              <div class="voice-setting llm-temperature-setting">
                <div><label for="bot-llm-temperature">Temperature</label><output id="bot-llm-temperature-value">0.7</output></div>
                <input id="bot-llm-temperature" type="range" min="0" max="2" step="0.1" value="0.7" />
                <small>Predictable ↔ Creative</small>
              </div>
              <details class="voice-advanced"><summary>Advanced</summary>
                <label for="bot-thinking">Thinking</label>
                <select id="bot-thinking"><option value="provider_default">Provider default · No override</option><option value="off">Off · Request no reasoning</option><option value="minimal">Minimal · Lowest reasoning effort</option></select>
                <p class="hint">Capability is verified by the connection diagnostic; model names are never guessed.</p>
                <label for="bot-llm-max-tokens">Max response tokens</label>
                <input id="bot-llm-max-tokens" type="number" min="1" max="32768" step="1" value="250" />
                <label for="bot-llm-request-timeout">Request timeout</label>
                <div class="input-suffix"><input id="bot-llm-request-timeout" type="number" min="3" max="60" step="1" value="15" /><span>seconds</span></div>
              </details>

              <label for="bot-system-prompt">System prompt</label>
              <textarea id="bot-system-prompt" rows="5" maxlength="30000" required></textarea>

              <label for="bot-opening-script">Opening message</label>
              <textarea id="bot-opening-script" rows="3" maxlength="2000"></textarea>
              <p class="hint">Leave blank for a user-first conversation.</p>
              <button id="test-bot-llm" class="secondary-button diagnostic-button" type="button">Test LLM connection</button>
              <div id="bot-diagnostic-result" class="diagnostic-result" hidden></div>
            </fieldset>

            <fieldset>
              <legend>API keys</legend>
              <div id="bot-key-fields">
                <div id="bot-deepgram-key-field">
                  <label for="bot-deepgram-key">Deepgram API key</label>
                  <div class="input-with-action">
                    <input id="bot-deepgram-key" type="password" autocomplete="new-password" />
                    <button class="text-button reveal" type="button" data-target="bot-deepgram-key">Show</button>
                  </div>
                  <div class="field-help">
                    <span>Encrypted before storage · never returned by the API</span>
                    <a href="https://console.deepgram.com/" target="_blank" rel="noreferrer">Get a key ↗</a>
                  </div>
                </div>
                <div id="bot-llm-key-field">
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

                <div id="bot-elevenlabs-key-field" hidden>
                  <label for="bot-elevenlabs-key">ElevenLabs API key</label>
                  <div class="input-with-action">
                    <input id="bot-elevenlabs-key" type="password" autocomplete="new-password" />
                    <button class="text-button reveal" type="button" data-target="bot-elevenlabs-key">Show</button>
                  </div>
                  <p class="hint">Required only when ElevenLabs is the TTS provider.</p>
                </div>
              </div>
              <label class="switch-row save-key-row" for="bot-save-keys">
                <span><b>Save API key</b><small>Encrypt and store entered credentials with this Bot.</small></span>
                <input id="bot-save-keys" type="checkbox" />
              </label>
              <p id="keep-keys-hint" class="hint" hidden>
                Keys are saved for this bot. Leave fields blank to keep them, or enter new keys to replace them.
              </p>
              <p id="byok-hint" class="hint">
                Unchecked: entered keys can be used by configuration tests, but are not submitted with or saved to the Bot.
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

        <section class="history-panel" hidden>
          <div class="list-head">
            <h2>Session history</h2>
            <button id="refresh-history" class="inline-button" type="button">Refresh</button>
          </div>
          <div class="history-filters">
            <input id="history-from" type="text" inputmode="numeric" placeholder="YYYY-MM-DD" pattern="\d{4}-\d{2}-\d{2}" aria-label="Sessions from date (YYYY-MM-DD)" />
            <input id="history-to" type="text" inputmode="numeric" placeholder="YYYY-MM-DD" pattern="\d{4}-\d{2}-\d{2}" aria-label="Sessions to date (YYYY-MM-DD)" />
            <select id="history-type" aria-label="Session type"><option value="">All sessions</option><option value="web_call">Web call</option><option value="chat_test">Chat test</option></select>
          </div>
          <div class="history-table-header" aria-hidden="true"><span>Session</span><span>Started</span><span>Type</span><span>Duration / Turns</span><span></span></div>
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
        <nav class="test-tabs" aria-label="Test bot mode">
          <button id="chat-test-tab" type="button">Chat test</button>
          <button id="web-call-tab" class="active" type="button">Web call test</button>
        </nav>

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
        <form id="chat-composer" class="chat-composer" hidden>
          <input id="chat-input" maxlength="10000" placeholder="Type a message…" disabled />
          <button id="send-chat" class="primary-button" type="submit" disabled>Send</button>
        </form>

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
          <button id="end-button" class="secondary-button" type="button" disabled>End test</button>
          <p id="privacy-note">User audio is saved for 7 days; transcripts and metrics for 30 days.</p>
        </footer>
      </section>
    </section>
    <aside id="history-dialog" class="history-dialog" aria-label="Session details" hidden>
      <header class="history-dialog-header"><strong>Session details</strong><button id="close-history" class="text-button dialog-close" type="button" aria-label="Close session details">×</button></header>
      <div id="history-detail"></div>
    </aside>
    <dialog id="voice-picker-dialog" class="voice-picker-dialog">
      <button id="close-voice-picker" class="text-button dialog-close" type="button">Close</button>
      <p class="eyebrow">TTS voice</p>
      <h2 id="voice-picker-title">Choose voice</h2>
      <p id="voice-picker-help" class="hint"></p>
      <div id="voice-discovery-key-field">
        <label for="voice-discovery-key">ElevenLabs API key for voice discovery</label>
        <input id="voice-discovery-key" type="password" autocomplete="new-password" />
        <p class="hint">Used for this request only unless “Save API keys” is enabled.</p>
      </div>
      <div class="voice-picker-filters">
        <input id="voice-search" placeholder="Search name or description" />
        <select id="voice-language"><option value="">All languages</option></select>
        <select id="voice-gender"><option value="">All genders</option></select>
      </div>
      <div id="voice-picker-error" class="error-banner" hidden></div>
      <div class="voice-picker-meta"><span id="voice-result-count">0 voices</span><span>Language and gender filters come from the current catalog.</span></div>
      <div id="voice-picker-list" class="voice-picker-list"></div>
      <button id="load-more-voices" class="secondary-button" type="button" hidden>Load more</button>
      <details id="manual-voice-panel">
        <summary>Enter Voice ID manually</summary>
        <div class="manual-voice-row">
          <input id="manual-voice-id" maxlength="100" placeholder="ElevenLabs Voice ID" />
          <button id="use-manual-voice" class="secondary-button" type="button">Use ID</button>
        </div>
      </details>
      <footer class="voice-picker-actions">
        <button id="cancel-voice-picker" class="secondary-button" type="button">Cancel</button>
        <button id="confirm-voice-picker" class="primary-button" type="button">Use selected voice</button>
      </footer>
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
  botAsrModel: document.querySelector("#bot-asr-model"),
  botAsrLanguage: document.querySelector("#bot-asr-language"),
  botAsrHintsField: document.querySelector("#bot-asr-hints-field"),
  botAsrHints: document.querySelector("#bot-asr-hints"),
  botAsrEotThreshold: document.querySelector("#bot-asr-eot-threshold"),
  botAsrEotThresholdValue: document.querySelector("#bot-asr-eot-threshold-value"),
  botAsrEotTimeout: document.querySelector("#bot-asr-eot-timeout"),
  botAsrKeyterms: document.querySelector("#bot-asr-keyterms"),
  botAsrProfanity: document.querySelector("#bot-asr-profanity"),
  botAsrNumerals: document.querySelector("#bot-asr-numerals"),
  botAsrRedact: document.querySelector("#bot-asr-redact"),
  botTts: document.querySelector("#bot-tts"),
  botTtsAggregation: document.querySelector("#bot-tts-aggregation"),
  botTtsModel: document.querySelector("#bot-tts-model"),
  fluxTuning: document.querySelector("#flux-tuning"),
  botFluxExpressivity: document.querySelector("#bot-flux-expressivity"),
  botFluxExpressivityValue: document.querySelector("#bot-flux-expressivity-value"),
  botFluxMipOptOut: document.querySelector("#bot-flux-mip-opt-out"),
  botFluxSpeed: document.querySelector("#bot-flux-speed"),
  botFluxSpeedValue: document.querySelector("#bot-flux-speed-value"),
  elevenlabsTuning: document.querySelector("#elevenlabs-tuning"),
  botTtsModelHint: document.querySelector("#bot-tts-model-hint"),
  botTtsStability: document.querySelector("#bot-tts-stability"),
  botTtsStabilityValue: document.querySelector("#bot-tts-stability-value"),
  botTtsStabilityScale: document.querySelector("#bot-tts-stability-scale"),
  botTtsSimilarity: document.querySelector("#bot-tts-similarity"),
  botTtsSimilarityValue: document.querySelector("#bot-tts-similarity-value"),
  botTtsStyle: document.querySelector("#bot-tts-style"),
  botTtsStyleValue: document.querySelector("#bot-tts-style-value"),
  botTtsSpeed: document.querySelector("#bot-tts-speed"),
  botTtsSpeedValue: document.querySelector("#bot-tts-speed-value"),
  botTtsSpeakerBoost: document.querySelector("#bot-tts-speaker-boost"),
  botDynamicSpeed: document.querySelector("#bot-dynamic-speed"),
  botSpeedStep: document.querySelector("#bot-speed-step"),
  dynamicSpeedHint: document.querySelector("#dynamic-speed-hint"),
  botAutoMode: document.querySelector("#bot-auto-mode"),
  botAutoModeState: document.querySelector("#bot-auto-mode-state"),
  botAutoModeHint: document.querySelector("#bot-auto-mode-hint"),
  botTextNormalization: document.querySelector("#bot-text-normalization"),
  botVoice: document.querySelector("#bot-voice"),
  chooseBotVoice: document.querySelector("#choose-bot-voice"),
  botVoiceCard: document.querySelector("#bot-voice-card"),
  botVoiceDocs: document.querySelector("#bot-voice-docs-link"),
  botVoiceListen: document.querySelector("#bot-voice-listen-link"),
  botProvider: document.querySelector("#bot-llm-provider"),
  botBaseUrl: document.querySelector("#bot-llm-base-url"),
  botModel: document.querySelector("#bot-llm-model"),
  botLlmTemperature: document.querySelector("#bot-llm-temperature"),
  botLlmTemperatureValue: document.querySelector("#bot-llm-temperature-value"),
  botThinking: document.querySelector("#bot-thinking"),
  botLlmMaxTokens: document.querySelector("#bot-llm-max-tokens"),
  botLlmRequestTimeout: document.querySelector("#bot-llm-request-timeout"),
  botModelOptions: document.querySelector("#bot-model-options"),
  botLlmKeyLink: document.querySelector("#bot-llm-key-link"),
  botLlmModelsLink: document.querySelector("#bot-llm-models-link"),
  botSystemPrompt: document.querySelector("#bot-system-prompt"),
  botOpeningScript: document.querySelector("#bot-opening-script"),
  botFallbackScript: document.querySelector("#bot-fallback-script"),
  testBotLlm: document.querySelector("#test-bot-llm"),
  botDiagnostic: document.querySelector("#bot-diagnostic-result"),
  botSaveKeys: document.querySelector("#bot-save-keys"),
  botKeyFields: document.querySelector("#bot-key-fields"),
  botDeepgramKeyField: document.querySelector("#bot-deepgram-key-field"),
  botDeepgramKey: document.querySelector("#bot-deepgram-key"),
  botLlmKeyField: document.querySelector("#bot-llm-key-field"),
  botLlmKey: document.querySelector("#bot-llm-key"),
  botElevenlabsKeyField: document.querySelector("#bot-elevenlabs-key-field"),
  botElevenlabsKey: document.querySelector("#bot-elevenlabs-key"),
  keepKeysHint: document.querySelector("#keep-keys-hint"),
  byokHint: document.querySelector("#byok-hint"),
  cancelBot: document.querySelector("#cancel-bot-button"),
  sessionKeys: document.querySelector("#session-keys"),
  sessionDeepgramKey: document.querySelector("#session-deepgram-key"),
  sessionLlmKey: document.querySelector("#session-llm-key"),
  sessionElevenlabsKeyField: document.querySelector("#session-elevenlabs-key-field"),
  sessionElevenlabsKey: document.querySelector("#session-elevenlabs-key"),
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
  chatTestTab: document.querySelector("#chat-test-tab"),
  webCallTab: document.querySelector("#web-call-tab"),
  chatComposer: document.querySelector("#chat-composer"),
  chatInput: document.querySelector("#chat-input"),
  sendChat: document.querySelector("#send-chat"),
  wsStatus: document.querySelector("#ws-status"),
  pipelineStatus: document.querySelector("#pipeline-status"),
  e2eLatency: document.querySelector("#e2e-latency"),
  synthesisLatency: document.querySelector("#synthesis-latency"),
  error: document.querySelector("#error-banner"),
  historyList: document.querySelector("#history-list"),
  historyFrom: document.querySelector("#history-from"),
  historyTo: document.querySelector("#history-to"),
  historyType: document.querySelector("#history-type"),
  refreshHistory: document.querySelector("#refresh-history"),
  historyDialog: document.querySelector("#history-dialog"),
  historyDetail: document.querySelector("#history-detail"),
  closeHistory: document.querySelector("#close-history"),
  voicePickerDialog: document.querySelector("#voice-picker-dialog"),
  closeVoicePicker: document.querySelector("#close-voice-picker"),
  voicePickerTitle: document.querySelector("#voice-picker-title"),
  voicePickerHelp: document.querySelector("#voice-picker-help"),
  voiceDiscoveryKeyField: document.querySelector("#voice-discovery-key-field"),
  voiceDiscoveryKey: document.querySelector("#voice-discovery-key"),
  voiceSearch: document.querySelector("#voice-search"),
  voiceLanguage: document.querySelector("#voice-language"),
  voiceGender: document.querySelector("#voice-gender"),
  voicePickerError: document.querySelector("#voice-picker-error"),
  voicePickerList: document.querySelector("#voice-picker-list"),
  voiceResultCount: document.querySelector("#voice-result-count"),
  cancelVoicePicker: document.querySelector("#cancel-voice-picker"),
  confirmVoicePicker: document.querySelector("#confirm-voice-picker"),
  loadMoreVoices: document.querySelector("#load-more-voices"),
  manualVoicePanel: document.querySelector("#manual-voice-panel"),
  manualVoiceId: document.querySelector("#manual-voice-id"),
  useManualVoice: document.querySelector("#use-manual-voice"),
  productRail: document.querySelector(".product-rail"),
  toggleProductRail: document.querySelector("#toggle-product-rail"),
  accountAvatar: document.querySelector("#account-avatar"),
  logoutButton: document.querySelector("#logout-button"),
  sessionExpiry: document.querySelector("#session-expiry"),
  continueSession: document.querySelector("#continue-session"),
};

let catalogs;
let bots = [];
let selectedBotId;
let editingBotId;
let discoveredVoices = [];
let pendingVoice;
let nextVoicePageToken;
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
let testMode = "web_call";
let clientReady = false;
let playbackReportPromise;
let historyItems = [];
let authWarningTimer;
let recentUserActivityAt = Date.now();

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
  elements.chatInput.disabled = !locked || testMode !== "chat_test";
  elements.sendChat.disabled = !locked || testMode !== "chat_test";
  elements.chatTestTab.disabled = locked;
  elements.webCallTab.disabled = locked;
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
  if (response.status === 401 && !path.startsWith("/api/sessions/")) {
    redirectToLogin();
    throw new Error("Website login required");
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const message = typeof error.detail === "string" ? error.detail : `Request failed (${response.status}).`;
    throw new Error(message);
  }
  if (response.status === 204) return undefined;
  return response.json();
}

function redirectToLogin() {
  const activePage = document.querySelector(".product-tabs button.active")?.dataset.page;
  if (activePage) sessionStorage.setItem("voiceagent-return-page", activePage);
  const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
  window.location.assign(`/login?expired=1&next=${next}`);
}

function scheduleAuthWarning(payload) {
  window.clearTimeout(authWarningTimer);
  elements.sessionExpiry.hidden = true;
  if (!payload?.auth_enabled || !payload.idle_expires_at) return;
  const warningDelay = Math.max(0, payload.idle_expires_at * 1000 - Date.now() - 300000);
  authWarningTimer = window.setTimeout(() => {
    elements.sessionExpiry.hidden = false;
  }, warningDelay);
}

async function refreshWebsiteSession() {
  const response = await fetch("/api/auth/session", { headers: { Accept: "application/json" } });
  if (response.status === 401) {
    redirectToLogin();
    return;
  }
  if (response.ok) scheduleAuthWarning(await response.json());
}

function initializeWebsiteSession() {
  for (const eventName of ["pointerdown", "keydown", "input"]) {
    document.addEventListener(eventName, () => { recentUserActivityAt = Date.now(); }, { passive: true });
  }
  window.setInterval(() => {
    if (Date.now() - recentUserActivityAt < 300000) refreshWebsiteSession().catch(() => {});
  }, 300000);
  elements.continueSession.addEventListener("click", () => refreshWebsiteSession().catch(() => {}));
  elements.accountAvatar.addEventListener("click", () => {
    const expanded = elements.accountAvatar.getAttribute("aria-expanded") !== "true";
    elements.accountAvatar.setAttribute("aria-expanded", String(expanded));
  });
  elements.logoutButton.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    window.location.assign("/login");
  });
  refreshWebsiteSession().catch(() => {});
}

function diagnosticPayload(kind) {
  if (kind === "bot") {
    const bot = editingBotId && bots.find((item) => item.id === editingBotId);
    if (bot?.has_saved_keys && !elements.botLlmKey.value) {
      return {
        bot_id: bot.id,
        reasoning_mode: elements.botThinking.value,
        llm_temperature: Number(elements.botLlmTemperature.value),
      };
    }
    return {
      llm_provider: elements.botProvider.value,
      llm_base_url: elements.botBaseUrl.value,
      llm_model: elements.botModel.value,
      llm_temperature: Number(elements.botLlmTemperature.value),
      reasoning_mode: elements.botThinking.value,
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

function loadAsrCatalog(bot) {
  const provider = catalogs.asr_providers?.providers?.[0];
  const model = provider?.models?.[0];
  if (!provider || !model) {
    elements.botAsrModel.disabled = true;
    elements.botAsrLanguage.disabled = true;
    showError("ASR capabilities could not be loaded. Reload to retry.");
    return;
  }
  elements.botAsr.replaceChildren(new Option(provider.name, provider.id));
  elements.botAsrModel.replaceChildren(new Option(model.name, model.id));
  elements.botAsrLanguage.replaceChildren(
    ...model.languages.map((language) => new Option(language.name, language.provider_model)),
  );
  elements.botAsrHints.replaceChildren(
    ...model.language_hints.map((language) => new Option(language.toUpperCase(), language)),
  );
  elements.botAsrModel.disabled = false;
  elements.botAsrLanguage.disabled = false;
  elements.botAsrLanguage.value = bot?.asr_model || "flux-general-en";
  const selectedHints = new Set(bot?.asr_language_hints || []);
  for (const option of elements.botAsrHints.options) option.selected = selectedHints.has(option.value);
  const hintChips = document.querySelector("#bot-asr-hint-chips");
  hintChips.replaceChildren(...[...elements.botAsrHints.options].map((option) => {
    const chip = document.createElement("label");
    chip.className = "check-chip";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = option.selected;
    checkbox.addEventListener("change", () => { option.selected = checkbox.checked; });
    chip.append(checkbox, document.createTextNode(option.textContent));
    return chip;
  }));
  syncAsrLanguage();
}

function syncAsrLanguage() {
  elements.botAsrHintsField.hidden = elements.botAsrLanguage.value !== "flux-general-multi";
}

function initializeComponentEditor() {
  if (elements.botForm.dataset.componentized) return;
  elements.botForm.dataset.componentized = "true";
  const cards = document.createElement("div");
  cards.className = "pipeline-cards";
  cards.innerHTML = [
    ["asr", "TRANSCRIBER · ASR", "Flux General English", "Deepgram · English", ["Mode", "Streaming", "Language", "English", "Audio input", "PCM · 16 kHz"]],
    ["llm", "MODEL · LLM", "Configured model", "OpenAI-compatible", ["Endpoint", "Custom", "Thinking", "Default", "Response", "Streaming"]],
    ["tts", "VOICE · TTS", "Configured voice", "Configured provider", ["Speed", "1.00", "Dynamic speed", "Off", "Aggregation", "Token"]],
  ].map(([id, type, title, provider, stats]) => `<button class="pipeline-card ${id}" type="button" data-component="${id}"><span class="card-type"><i class="component-dot"></i>${type}</span><i class="edit-icon">↗</i><h3>${title}</h3><p>${provider}</p><div class="card-stats">${[0, 2, 4].map((index) => `<span><small>${stats[index]}</small><b>${stats[index + 1]}</b></span>`).join("")}</div></button>`).join("");
  const drawer = document.createElement("aside");
  drawer.className = "component-drawer";
  drawer.hidden = true;
  drawer.innerHTML = `<header><div><span class="eyebrow">Pipeline component</span><h2 id="component-drawer-title"></h2></div><button type="button" aria-label="Collapse component drawer">→</button></header><div data-panel="asr"></div><div data-panel="llm"></div><div data-panel="tts"></div><div class="component-credentials"></div>`;
  const firstFieldset = elements.botAsr.closest("fieldset");
  firstFieldset.before(cards);
  firstFieldset.after(drawer);
  const panels = Object.fromEntries([...drawer.querySelectorAll("[data-panel]")].map((node) => [node.dataset.panel, node]));
  const move = (id, panel) => {
    const control = document.querySelector(`#${id}`);
    const label = document.querySelector(`label[for="${id}"]`);
    if (label) panel.append(label);
    if (control) panel.append(control);
  };
  for (const id of ["bot-asr", "bot-asr-model"]) move(id, panels.asr);
  const asrInputGrid = document.createElement("div");
  asrInputGrid.className = "component-grid-2 asr-input-grid";
  const asrLanguageField = document.createElement("div");
  asrLanguageField.className = "component-field";
  move("bot-asr-language", asrLanguageField);
  const asrAudioField = document.createElement("div");
  asrAudioField.className = "component-field";
  asrAudioField.innerHTML = `
    <label>Audio input</label>
    <div class="readonly-control" aria-label="Audio input PCM 16 kHz">PCM · 16 kHz</div>
    <p class="hint">Current WebCall input contract · fixed at 16 kHz.</p>
  `;
  asrInputGrid.append(asrLanguageField, asrAudioField);
  panels.asr.append(asrInputGrid);
  panels.asr.append(elements.botAsrHintsField, elements.botAsrRedact.closest("details"));
  for (const id of ["bot-llm-provider", "bot-llm-base-url", "bot-llm-model"]) move(id, panels.llm);
  panels.llm.append(elements.botLlmTemperature.closest(".voice-setting"));
  panels.llm.append(elements.botModelOptions, elements.botThinking.closest("details"), elements.testBotLlm, elements.botDiagnostic);
  move("bot-tts", panels.tts);
  const elevenModel = document.createElement("div");
  elevenModel.id = "eleven-model-basic";
  move("bot-tts-model", elevenModel);
  elevenModel.append(elements.botTtsModelHint);
  panels.tts.append(elevenModel);
  move("bot-voice", panels.tts);
  const voiceLinks = elements.botVoiceDocs.closest(".link-row");
  voiceLinks.hidden = true;
  panels.tts.append(elements.chooseBotVoice, elements.botVoiceCard, voiceLinks);
  const initialSpeed = document.createElement("div");
  initialSpeed.id = "tts-initial-speed";
  const fluxSpeed = elements.botFluxSpeed.closest(".voice-setting");
  const elevenSpeed = elements.botTtsSpeed.closest(".voice-setting");
  fluxSpeed.dataset.providerSpeed = "deepgram_flux";
  elevenSpeed.dataset.providerSpeed = "elevenlabs";
  initialSpeed.append(fluxSpeed, elevenSpeed);
  panels.tts.append(initialSpeed);
  const ttsAdvanced = document.createElement("details");
  ttsAdvanced.className = "voice-advanced tts-advanced";
  ttsAdvanced.innerHTML = "<summary>Advanced</summary>";
  const aggregationHint = elements.botTtsAggregation.nextElementSibling;
  move("bot-tts-aggregation", ttsAdvanced);
  if (aggregationHint?.classList.contains("hint")) ttsAdvanced.append(aggregationHint);
  ttsAdvanced.append(document.querySelector("#conversational-speed"), elements.fluxTuning, elements.elevenlabsTuning);
  panels.tts.append(ttsAdvanced);
  const promptFieldset = elements.botSystemPrompt.closest("fieldset");
  const pipeline = document.createElement("section");
  pipeline.className = "pipeline-section";
  pipeline.innerHTML = '<div class="pipeline-heading"><h3>Voice pipeline</h3><p>Choose each component separately. Click a card to configure it.</p></div>';
  pipeline.append(cards);
  const identity = document.createElement("section");
  identity.className = "bot-identity prototype-section";
  identity.innerHTML = "<h3>Bot identity</h3>";
  move("bot-name", identity);
  const firstMessage = document.createElement("section");
  firstMessage.className = "prototype-section";
  firstMessage.innerHTML = "<h3>First message</h3>";
  move("bot-opening-script", firstMessage);
  const systemPrompt = document.createElement("section");
  systemPrompt.className = "prototype-section";
  systemPrompt.innerHTML = "<h3>System prompt</h3>";
  move("bot-system-prompt", systemPrompt);
  firstFieldset.before(pipeline, identity, firstMessage, systemPrompt);
  promptFieldset.hidden = true;
  firstFieldset.hidden = true;
  const keyFieldset = elements.botSaveKeys.closest("fieldset");
  keyFieldset.classList.add("credential-card");
  drawer.querySelector(".component-credentials").append(keyFieldset);
  const syncDrawerCredentials = (component) => {
    const credentialLegend = keyFieldset.querySelector("legend");
    credentialLegend.hidden = true;
    keyFieldset.setAttribute("aria-label", `${component.toUpperCase()} credentials`);
    elements.botDeepgramKeyField.hidden = component !== "asr" && !(
      component === "tts" && elements.botTts.value === "deepgram_flux"
    );
    elements.botLlmKeyField.hidden = component !== "llm";
    elements.botElevenlabsKeyField.hidden = component !== "tts" || elements.botTts.value !== "elevenlabs";
    if (component === "tts") {
      const voiceLabel = panels.tts.querySelector('label[for="bot-voice"]');
      panels.tts.insertBefore(keyFieldset, voiceLabel);
    } else if (component === "llm") {
      panels.llm.insertBefore(keyFieldset, elements.testBotLlm);
    } else {
      panels.asr.append(keyFieldset);
    }
  };
  const close = () => {
    drawer.hidden = true;
    elements.botForm.classList.remove("drawer-open");
    cards.querySelectorAll("button").forEach((button) => button.classList.remove("active"));
  };
  drawer.querySelector("header button").addEventListener("click", close);
  cards.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => {
    if (!drawer.hidden && button.classList.contains("active")) return close();
    cards.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
    Object.entries(panels).forEach(([name, panel]) => { panel.hidden = name !== button.dataset.component; });
    drawer.querySelector("#component-drawer-title").textContent = `${button.dataset.component.toUpperCase()} configuration`;
    drawer.dataset.component = button.dataset.component;
    syncDrawerCredentials(button.dataset.component);
    drawer.hidden = false;
    elements.botForm.classList.add("drawer-open");
  }));
}

function initializePrototypeLayout() {
  const configPanel = document.querySelector(".config-panel");
  const workspace = document.querySelector(".workspace");
  const editor = elements.editor;
  const history = document.querySelector(".history-panel");
  const advanced = document.querySelector("#advanced-empty");
  document.querySelector(".panel-heading").hidden = true;
  document.querySelector(".quick-start").hidden = true;
  elements.sessionKeys.hidden = true;
  configPanel.insertAdjacentHTML("afterbegin", '<div class="prototype-side-title">Voice bots <small id="bot-count">0</small></div><div class="bot-search"><span>⌕</span><input id="bot-search-input" placeholder="Search bots" /></div>');
  configPanel.querySelector(".bot-panel").prepend(configPanel.querySelector(".bot-search"));
  configPanel.querySelector(".list-head h2").hidden = true;
  elements.newBot.textContent = "Create bot";
  document.querySelector("#save-bot-button").textContent = "Save bot settings";
  elements.cancelBot.textContent = "Discard changes";
  editor.classList.add("settings-page");
  workspace.prepend(editor);
  workspace.append(history);
  workspace.append(advanced);
  const conversation = document.querySelector(".conversation-panel");
  const conversationHeader = conversation.querySelector(".conversation-header");
  const headerCopy = conversationHeader.querySelector("div");
  const lifecycleControls = conversation.querySelector(".controls");
  const lifecycleButtons = document.createElement("div");
  lifecycleButtons.className = "test-lifecycle-controls";
  lifecycleButtons.append(elements.start, elements.end);
  const testBackButton = Object.assign(document.createElement("button"), {
    className: "secondary-button test-back-button",
    type: "button",
    textContent: "‹",
    ariaLabel: "Back to bot settings",
  });
  testBackButton.addEventListener("click", () => document.querySelector('[data-page="settings"]').click());
  conversationHeader.prepend(testBackButton);
  conversationHeader.append(lifecycleButtons);
  headerCopy.querySelector(".eyebrow").textContent = "Live ASR → LLM → TTS test with real-time captions.";
  lifecycleControls.classList.add("test-retention-note");
  conversation.querySelector(".test-tabs").hidden = true;
  document.querySelector(".topbar").innerHTML = '<div class="prototype-title"><b id="current-bot-title">Select a bot</b><span>Draft <i>Saved locally</i></span></div><div class="top-actions"><details class="test-menu"><summary>Test bot⌄</summary><button type="button" data-test-mode="chat">Chat test<small>Text → LLM → TTS</small></button><button type="button" data-test-mode="web">Web call test<small>ASR → LLM → TTS</small></button></details><button class="publish-button" type="button">Publish</button></div>';
  document.querySelector("#bot-search-input").addEventListener("input", renderBotList);
  document.querySelectorAll("[data-test-mode]").forEach((button) => button.addEventListener("click", () => {
    document.querySelector(".test-menu").open = false;
    editor.hidden = true;
    history.hidden = true;
    document.querySelector(".conversation-panel").hidden = false;
    (button.dataset.testMode === "chat" ? elements.chatTestTab : elements.webCallTab).click();
  }));
}

function updatePipelineSummaries(bot) {
  if (!bot) return;
  const cards = document.querySelectorAll(".pipeline-card");
  const asr = cards[0];
  const llm = cards[1];
  const tts = cards[2];
  const automatic = bot.asr_model === "flux-general-multi";
  asr.querySelector("h3").textContent = automatic ? "Flux General Multilingual" : "Flux General English";
  asr.querySelector("p").textContent = `Deepgram · ${automatic ? "Automatic" : "English"}`;
  asr.querySelector(".card-stats span:nth-child(2) b").textContent = automatic ? "Automatic" : "English";
  llm.querySelector("h3").textContent = bot.llm_model;
  llm.querySelector("p").textContent = `${bot.llm_provider} · OpenAI-compatible`;
  llm.querySelector(".card-stats span:nth-child(2) b").textContent = (bot.reasoning_mode || "provider_default").replace("provider_default", "Default");
  const voice = voiceEntry(bot.tts_voice);
  tts.querySelector("h3").textContent = voice?.name || bot.tts_voice;
  tts.querySelector("p").textContent = bot.tts_provider === "elevenlabs" ? `ElevenLabs · ${bot.tts_model}` : "Deepgram · Flux TTS v2";
  tts.querySelector(".card-stats span:nth-child(1) b").textContent = Number(bot.tts_speed).toFixed(2);
  tts.querySelector(".card-stats span:nth-child(2) b").textContent = bot.tts_dynamic_speed_enabled ? "On" : "Off";
  tts.querySelector(".card-stats span:nth-child(3) b").textContent = bot.tts_text_aggregation === "sentence" ? "Sentence" : "Token";
}

function escapeHtml(text) {
  if (text == null) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderDiagnosticResult(result) {
  const container = document.createElement("div");
  container.className = "diagnostic-detail";

  const badgeClass = result.success ? "success" : "danger";
  const badgeLabel = result.success ? "Connected" : "Failed";

  const header = document.createElement("div");
  header.className = "diagnostic-header";
  header.innerHTML = `
    <span class="diagnostic-badge ${badgeClass}">${badgeLabel}</span>
    <span class="diagnostic-provider">${escapeHtml(result.provider)}/${escapeHtml(result.model)}</span>
    <span class="diagnostic-host">@${escapeHtml(result.base_url_host)}</span>
  `;
  container.appendChild(header);

  const metrics = document.createElement("dl");
  metrics.className = "diagnostic-metrics";
  const firstToken = result.first_token_ms != null ? `${result.first_token_ms} ms` : "—";
  const reasoningTokens = result.reasoning_tokens != null ? ` (${result.reasoning_tokens} tokens)` : "";
  metrics.innerHTML = `
    <div><dt>First token</dt><dd>${escapeHtml(firstToken)}</dd></div>
    <div><dt>Total</dt><dd>${escapeHtml(result.total_ms)} ms</dd></div>
    <div><dt>Reasoning</dt><dd>${escapeHtml(result.reasoning_status)}${reasoningTokens}</dd></div>
    ${result.reasoning_control ? `<div><dt>Control</dt><dd>${escapeHtml(result.reasoning_control)}</dd></div>` : ""}
  `;
  container.appendChild(metrics);

  const message = document.createElement("div");
  message.className = "diagnostic-message";
  message.innerHTML = `
    <p><strong>${escapeHtml(result.summary)}</strong></p>
    <p>${escapeHtml(result.suggestion)}</p>
  `;
  container.appendChild(message);

  const debug = document.createElement("details");
  debug.className = "diagnostic-debug";
  debug.open = !result.success;
  const summary = document.createElement("summary");
  summary.textContent = "Debug details";
  debug.appendChild(summary);

  const debugList = document.createElement("dl");
  debugList.className = "diagnostic-debug-list";
  const debugRows = [
    `<div><dt>Category</dt><dd>${escapeHtml(result.category)}</dd></div>`,
    result.http_status != null
      ? `<div><dt>HTTP status</dt><dd>${escapeHtml(result.http_status)}</dd></div>`
      : "",
    result.error_type
      ? `<div><dt>Error type</dt><dd>${escapeHtml(result.error_type)}</dd></div>`
      : "",
    result.provider_error_code
      ? `<div><dt>Provider code</dt><dd>${escapeHtml(result.provider_error_code)}</dd></div>`
      : "",
  ].filter(Boolean);
  debugList.innerHTML = debugRows.join("");
  debug.appendChild(debugList);

  const idRow = document.createElement("div");
  idRow.className = "diagnostic-id-row";
  const idCode = document.createElement("code");
  idCode.textContent = result.diagnostic_id;
  const copyButton = document.createElement("button");
  copyButton.className = "text-button copy-id";
  copyButton.type = "button";
  copyButton.textContent = "Copy";
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(result.diagnostic_id);
      copyButton.textContent = "Copied";
      window.setTimeout(() => {
        copyButton.textContent = "Copy";
      }, 1200);
    } catch {
      copyButton.textContent = "Error";
    }
  });
  idRow.append(idCode, copyButton);
  debug.appendChild(idRow);

  container.appendChild(debug);
  return container;
}

async function testLlm(kind) {
  clearError();
  const output = kind === "bot" ? elements.botDiagnostic : kind === "session" ? elements.sessionDiagnostic : elements.quickDiagnostic;
  const button = kind === "bot" ? elements.testBotLlm : kind === "session" ? elements.testSessionLlm : elements.testQuickLlm;
  button.disabled = true;
  output.hidden = false;
  output.dataset.success = "";
  output.textContent = "Testing a minimal request…";
  try {
    const result = await apiRequest("/api/llm/diagnostics", {
      method: "POST",
      body: kind === "session"
        ? { bot_id: selectedBotId, llm_api_key: elements.sessionLlmKey.value }
        : diagnosticPayload(kind),
    });
    output.dataset.success = String(result.success);
    output.replaceChildren(renderDiagnosticResult(result));
  } catch (error) {
    output.dataset.success = "false";
    output.textContent = error instanceof Error ? error.message : "Diagnostic failed.";
  } finally {
    button.disabled = false;
  }
}

async function loadHistory() {
  const data = await apiRequest("/api/history?limit=25&offset=0");
  historyItems = data.items;
  renderHistory();
}

function renderHistory() {
  const from = elements.historyFrom.value ? new Date(`${elements.historyFrom.value}T00:00:00`) : null;
  const to = elements.historyTo.value ? new Date(`${elements.historyTo.value}T23:59:59`) : null;
  const items = historyItems.filter((call) => {
    const started = new Date(call.started_at);
    return (!from || started >= from) && (!to || started <= to) && (!elements.historyType.value || call.session_type === elements.historyType.value);
  });
  if (!items.length) {
    elements.historyList.innerHTML = '<p class="empty-bots">No calls recorded yet.</p>';
    return;
  }
  elements.historyList.replaceChildren(...items.map((call) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "history-row";
    const durationSeconds = call.duration_ms === null ? null : Math.round(call.duration_ms / 1000);
    const duration = durationSeconds === null ? "Pending" : `${String(Math.floor(durationSeconds / 60)).padStart(2, "0")}:${String(durationSeconds % 60).padStart(2, "0")}`;
    const type = call.session_type === "chat_test" ? "Chat test" : "Web call";
    const turns = call.turn_count ?? call.turns_count ?? "—";
    const pipeline = call.session_type === "chat_test" ? "LLM + TTS" : "ASR + LLM + TTS";
    const started = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(call.started_at));
    button.innerHTML = `<span><strong>${escapeHtml(call.id)}</strong><small>${escapeHtml(call.bot_name || "One-off session")}</small></span><span><strong>${escapeHtml(started)}</strong><small>${escapeHtml(call.status)}</small></span><span><strong>${type}</strong><small>${pipeline}</small></span><span><strong>${duration}</strong><small>${turns === "—" ? "Turn count unavailable" : `${turns} turns`}</small></span><span class="history-view">View</span>`;
    button.addEventListener("click", () => showHistory(call.id));
    return button;
  }));
}

function closeHistoryDrawer() {
  elements.historyDialog.querySelectorAll("audio").forEach((audio) => audio.pause());
  elements.historyDialog.hidden = true;
}

async function showHistory(callId) {
  const call = await apiRequest(`/api/history/${callId}`);
  elements.historyDetail.replaceChildren();
  const heading = document.createElement("h2");
  heading.textContent = call.bot_name || "One-off session";
  const meta = document.createElement("p");
  meta.textContent = `${new Date(call.started_at).toLocaleString()} · ${call.llm_provider}/${call.llm_model} · ${call.tts_provider}/${call.tts_model} · ${call.tts_text_aggregation} input · ${call.status}`;
  elements.historyDetail.append(heading, meta);
  if (call.has_recording) {
    const recordingMeta = document.createElement("p");
    recordingMeta.className = "hint";
    recordingMeta.textContent = `${call.audio_format.toUpperCase()} · mono · ${call.sample_rate / 1000} kHz · user uplink only · Agent TTS is not retained`;
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.src = `/api/history/${call.id}/recording`;
    elements.historyDetail.append(recordingMeta, audio);
  } else {
    const unavailable = document.createElement("p");
    unavailable.className = "recording-unavailable";
    unavailable.textContent = call.recording_status === "not_applicable"
      ? "Chat test uses text input and has no user recording."
      : `User recording unavailable: ${call.recording_status.replaceAll("_", " ")}.`;
    elements.historyDetail.append(unavailable);
  }
  const metricHelp = document.createElement("p");
  metricHelp.className = "hint";
  metricHelp.textContent = "TTS initial measures pipeline handoff to the TTS request; TTS TTFT measures first synthesized audio. In sentence mode, TTS initial therefore includes the wait for the first complete sentence.";
  elements.historyDetail.append(metricHelp);
  let interactionIndex = 0;
  for (const turn of call.turns) {
    addHistoryTurn(turn);
    if (turn.role !== "assistant") continue;
    const metric = call.metrics[interactionIndex++];
    if (!metric) continue;
    const row = document.createElement("p");
    row.className = "history-metric";
    const reasons = {
      word_timing_unavailable: "ASR word timing unavailable",
      audio_clock_mismatch: "ASR audio clock mismatch",
      interrupted_before_llm_first_token: "interrupted before LLM first token",
      session_ended_before_llm_first_token: "session ended before LLM first token",
      interrupted_before_tts_audio: "interrupted before TTS audio",
      session_ended_before_tts_audio: "session ended before TTS audio",
      interrupted_before_playback: "interrupted before playback",
      session_ended_before_playback: "session ended before playback",
    };
    const fmt = (value, reason) => {
      if (value !== null && value !== undefined) return `${value} ms`;
      return `not available (${reasons[reason] || "event not observed"})`;
    };
    row.textContent = `Turn ${metric.turn_index + 1}: ASR final ${fmt(metric.asr_final_latency_ms, metric.asr_final_reason)} · LLM splicing ${fmt(metric.llm_request_splicing_ms, metric.incomplete_reason)} · LLM TTFT ${fmt(metric.llm_first_token_ms, metric.incomplete_reason)} · TTS initial ${fmt(metric.tts_initial_ms, metric.incomplete_reason)} · TTS TTFT ${fmt(metric.tts_first_audio_ms, metric.incomplete_reason)} · playback ${fmt(metric.playback_ms, metric.incomplete_reason)} · e2e latency ${fmt(metric.turn_to_playback_ms, metric.incomplete_reason)} · reasoning ${metric.reasoning_status}/${metric.reasoning_tokens ?? "not reported"}`;
    elements.historyDetail.append(row);
  }
  const remove = document.createElement("button");
  remove.className = "card-button danger";
  remove.textContent = "Delete call";
  remove.addEventListener("click", async () => {
    if (!window.confirm("Delete this call, transcript, metrics, and recording?")) return;
    await apiRequest(`/api/history/${call.id}`, { method: "DELETE" });
    closeHistoryDrawer();
    await loadHistory();
  });
  elements.historyDetail.append(remove);
  elements.historyDialog.hidden = false;
}

function addHistoryTurn(turn) {
  const item = document.createElement("article");
  item.className = `message ${turn.role === "user" ? "user" : "agent"}`;
  const text = document.createElement("p");
  text.textContent = turn.text;
  item.append(text);
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

function resetLiveTestView() {
  const message = testMode === "chat_test"
    ? "Opening message and text replies will play through the configured TTS."
    : "Caller and Agent captions will appear here in real time.";
  elements.transcript.innerHTML = `<div class="empty-state"><span>Transcript</span><p>${message}</p></div>`;
  elements.e2eLatency.textContent = "—";
  elements.synthesisLatency.textContent = "—";
  elements.chatInput.value = "";
  userStoppedAt = undefined;
  llmFirstTokenAt = undefined;
  currentAssistantBubble = undefined;
  currentAssistantText = "";
  interimUserBubble = undefined;
  playbackReportPromise = undefined;
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

function syncTtsFields() {
  const elevenlabs = elements.botTts.value === "elevenlabs";
  const modelLabels = {
    "flux-general-en": "Flux TTS · v2",
    eleven_flash_v2_5: "Eleven Flash v2.5 · Lowest latency",
    eleven_turbo_v2_5: "Eleven Turbo v2.5 · Balanced",
    eleven_multilingual_v2: "Eleven Multilingual v2",
    eleven_v3: "Eleven v3 · Most expressive",
  };
  elements.botTtsModel.replaceChildren(
    ...(
      elevenlabs
        ? ["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2", "eleven_v3"]
        : ["flux-general-en"]
    ).map((model) => new Option(modelLabels[model] || model, model)),
  );
  elements.botElevenlabsKeyField.hidden = !elevenlabs;
  if (document.querySelector(".component-drawer")?.dataset.component === "tts") {
    elements.botDeepgramKeyField.hidden = elevenlabs;
    elements.botElevenlabsKeyField.hidden = !elevenlabs;
  }
  const elevenModel = document.querySelector("#eleven-model-basic");
  if (elevenModel) elevenModel.hidden = false;
  const fluxSpeed = document.querySelector('[data-provider-speed="deepgram_flux"]');
  const elevenSpeed = document.querySelector('[data-provider-speed="elevenlabs"]');
  if (fluxSpeed) fluxSpeed.hidden = elevenlabs;
  if (elevenSpeed) elevenSpeed.hidden = !elevenlabs;
  elements.fluxTuning.hidden = elevenlabs;
  elements.elevenlabsTuning.hidden = !elevenlabs;
  elements.sessionElevenlabsKeyField.hidden = !(
    selectedBot()?.tts_provider === "elevenlabs" && !selectedBot()?.has_saved_keys
  );
  elements.manualVoicePanel.hidden = !elevenlabs;
  elements.voiceDiscoveryKeyField.hidden = true;
  if (!elevenlabs && !voiceEntry(elements.botVoice.value)) {
    fillVoiceSelect(elements.botVoice, catalogs.defaults.flux_voice);
  }
  updateBotVoiceDisplay();
  syncElevenlabsSettings();
  syncFluxSettings();
  syncKeyFieldVisibility();
  syncTtsVoiceAvailability();
}

function syncTtsVoiceAvailability() {
  const requiresKey = elements.botTts.value === "elevenlabs";
  const editingHasKeys = Boolean(
    editingBotId && bots.find((bot) => bot.id === editingBotId)?.has_saved_keys,
  );
  const available = !requiresKey || Boolean(elements.botElevenlabsKey.value) || editingHasKeys;
  elements.chooseBotVoice.disabled = !available;
  elements.chooseBotVoice.textContent = !available
    ? "Enter ElevenLabs API key to choose a voice"
    : (voiceEntry(elements.botVoice.value)?.name
      ? `${voiceEntry(elements.botVoice.value).name} — Change voice`
      : "Choose voice");
}

function syncFluxSettings() {
  elements.botFluxExpressivityValue.value = elements.botFluxExpressivity.value;
  elements.botFluxSpeedValue.value = Number(elements.botFluxSpeed.value).toFixed(2);
}

function syncElevenlabsSettings() {
  const model = elements.botTtsModel.value;
  const isV3 = model === "eleven_v3";
  const hints = {
    eleven_flash_v2_5: "Recommended for realtime conversation.",
    eleven_turbo_v2_5: "Balanced latency and quality.",
    eleven_multilingual_v2: "Stable for longer generations; higher latency.",
    eleven_v3: "Most expressive; Stability uses Creative, Natural, or Robust.",
  };
  elements.botTtsModelHint.textContent = hints[model] || "";
  elements.botTtsStability.step = isV3 ? "0.5" : "0.05";
  if (isV3) {
    const current = Number(elements.botTtsStability.value);
    elements.botTtsStability.value = String([0, 0.5, 1].reduce((best, value) =>
      Math.abs(value - current) < Math.abs(best - current) ? value : best, 0.5));
  }
  elements.botTtsStabilityScale.textContent = isV3
    ? "Creative (0) · Natural (0.5) · Robust (1)"
    : "More variable ↔ More stable";
  elements.botTtsSimilarity.disabled = isV3;
  elements.botTtsSpeakerBoost.disabled = isV3;
  elements.botTtsSimilarity.closest(".voice-setting").classList.toggle("is-disabled", isV3);
  elements.botTtsSpeakerBoost.closest(".switch-row").classList.toggle("is-disabled", isV3);
  elements.botDynamicSpeed.disabled = isV3;
  elements.botSpeedStep.disabled = isV3 || !elements.botDynamicSpeed.checked;
  if (isV3) elements.botDynamicSpeed.checked = false;
  elements.dynamicSpeedHint.textContent = isV3
    ? "Eleven v3 does not support precise in-call speed changes."
    : "Session-only state; the saved Initial speed is never overwritten.";
  const sentence = elements.botTtsAggregation.value === "sentence";
  elements.botAutoMode.checked = sentence;
  elements.botAutoModeState.textContent = sentence ? "On · derived" : "Off · derived";
  elements.botAutoModeHint.textContent = sentence
    ? "Complete-sentence input skips ElevenLabs chunk scheduling."
    : "Token input keeps ElevenLabs chunk scheduling enabled.";
  for (const [input, output] of [
    [elements.botTtsStability, elements.botTtsStabilityValue],
    [elements.botTtsSimilarity, elements.botTtsSimilarityValue],
    [elements.botTtsStyle, elements.botTtsStyleValue],
    [elements.botTtsSpeed, elements.botTtsSpeedValue],
  ]) output.value = Number(input.value).toFixed(2);
}

function updateBotVoiceDisplay() {
  const voice = voiceEntry(elements.botVoice.value);
  const name = voice?.name || elements.botVoice.selectedOptions[0]?.textContent || elements.botVoice.value;
  elements.chooseBotVoice.textContent = name ? `${name} — Change voice` : "Choose voice";
  updateVoiceCard(elements.botVoice, elements.botVoiceCard);
  elements.botVoiceCard.hidden = !voice;
}

function normalizedDeepgramVoices() {
  return catalogs.flux_voices.voices.map((voice) => ({
    voice_id: voice.model_id,
    name: voice.name,
    category: "Built-in",
    labels: { language: "English", accent: voice.accent, gender: voice.gender },
    description: [...voice.traits, ...voice.use_cases].join(" "),
  }));
}

function fillDynamicFilter(select, placeholder, values) {
  select.replaceChildren(new Option(placeholder, ""), ...values.map((value) => new Option(value, value)));
}

function renderVoicePicker() {
  const query = elements.voiceSearch.value.trim().toLowerCase();
  const visible = discoveredVoices.filter((voice) => {
    const searchable = `${voice.name} ${voice.description || ""} ${Object.values(voice.labels).join(" ")}`.toLowerCase();
    return (
      searchable.includes(query) &&
      (!elements.voiceLanguage.value || voice.labels.language === elements.voiceLanguage.value) &&
      (!elements.voiceGender.value || voice.labels.gender === elements.voiceGender.value)
    );
  });
  elements.voiceResultCount.textContent = `${visible.length} voice${visible.length === 1 ? "" : "s"}`;
  elements.voicePickerList.replaceChildren(
    ...visible.map((voice) => {
      const card = document.createElement("article");
      card.className = "voice-picker-option";
      card.tabIndex = 0;
      card.setAttribute("role", "radio");
      card.setAttribute("aria-checked", String(voice.voice_id === pendingVoice?.voice_id));
      card.dataset.selected = String(voice.voice_id === pendingVoice?.voice_id);
      card.innerHTML = `<i class="voice-radio"></i><b class="voice-initial" aria-hidden="true"></b><div class="voice-option-copy"><strong></strong><span></span><em></em></div>`;
      card.querySelector(".voice-initial").textContent = voice.name.trim().charAt(0).toUpperCase() || "?";
      card.querySelector("strong").textContent = voice.name;
      card.querySelector("span").textContent = [voice.labels.language, voice.labels.accent, voice.labels.gender].filter(Boolean).join(" · ");
      card.querySelector("em").textContent = voice.description || voice.category;
      const choose = () => {
        pendingVoice = voice;
        renderVoicePicker();
      };
      card.addEventListener("click", choose);
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          choose();
        }
      });
      if (voice.preview_url) {
        const preview = document.createElement("button");
        preview.type = "button";
        preview.className = "voice-preview";
        preview.setAttribute("aria-label", `Preview ${voice.name}`);
        preview.textContent = "▶";
        preview.addEventListener("click", (event) => {
          event.stopPropagation();
          new Audio(voice.preview_url).play().catch(() => {});
        });
        card.append(preview);
      }
      return card;
    }),
  );
  elements.confirmVoicePicker.disabled = !pendingVoice;
}

function selectVoice(voice) {
  elements.botVoice.replaceChildren(new Option(voice.name, voice.voice_id, true, true));
  updateBotVoiceDisplay();
  elements.voicePickerDialog.close();
}

async function loadElevenlabsVoices({ append = false } = {}) {
  const apiKey = elements.botElevenlabsKey.value || elements.voiceDiscoveryKey.value;
  const editingBot = bots.find((bot) => bot.id === editingBotId);
  if (!apiKey && !editingBot?.has_saved_keys) {
    throw new Error("Enter the ElevenLabs API key before loading voices.");
  }
  const response = await apiRequest("/api/tts/elevenlabs/voices", {
    method: "POST",
    body: {
      api_key: apiKey || null,
      bot_id: apiKey ? null : editingBotId,
      search: elements.voiceSearch.value.trim(),
      page_token: append ? nextVoicePageToken : null,
    },
  });
  discoveredVoices = append ? [...discoveredVoices, ...response.voices] : response.voices;
  nextVoicePageToken = response.next_page_token;
  elements.loadMoreVoices.hidden = !response.has_more;
}

async function openVoicePicker() {
  elements.voicePickerError.hidden = true;
  elements.voiceSearch.value = "";
  pendingVoice = undefined;
  if (elements.botTts.value === "deepgram_flux") {
    discoveredVoices = normalizedDeepgramVoices();
    elements.voicePickerTitle.textContent = "Choose a Deepgram Flux voice";
    elements.voicePickerHelp.textContent = "Search the built-in catalog.";
    elements.loadMoreVoices.hidden = true;
  } else {
    elements.voicePickerTitle.textContent = "Choose an ElevenLabs voice";
    elements.voicePickerHelp.textContent = "Loaded dynamically from your ElevenLabs account.";
    try {
      await loadElevenlabsVoices();
    } catch (error) {
      discoveredVoices = [];
      elements.voicePickerError.textContent = error.message;
      elements.voicePickerError.hidden = false;
    }
  }
  const labelValues = (key) => [
    ...new Set(discoveredVoices.map((voice) => voice.labels[key] || "Unspecified")),
  ].sort();
  fillDynamicFilter(elements.voiceLanguage, "All languages", labelValues("language"));
  fillDynamicFilter(elements.voiceGender, "All genders", labelValues("gender"));
  pendingVoice = discoveredVoices.find((voice) => voice.voice_id === elements.botVoice.value);
  renderVoicePicker();
  elements.voicePickerDialog.showModal();
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
  const query = document.querySelector("#bot-search-input")?.value.trim().toLowerCase() || "";
  const visibleBots = bots.filter((bot) => bot.name.toLowerCase().includes(query));
  const count = document.querySelector("#bot-count");
  if (count) count.textContent = String(bots.length);
  if (!visibleBots.length) {
    elements.botList.innerHTML = `<p class="empty-bots">No bots yet. Create your first bot to skip re-entering the configuration every time.</p>`;
  } else {
    elements.botList.replaceChildren(
      ...visibleBots.map((bot) => {
        const voice = voiceEntry(bot.tts_voice);
        const card = document.createElement("article");
        card.className = "bot-card";
        card.dataset.selected = String(bot.id === selectedBotId);
        card.innerHTML = `
          <header>
            <strong></strong>
            <span class="badge">v1</span>
          </header>
          <p></p>
        `;
        card.querySelector("strong").textContent = bot.name;
        card.querySelector("p").textContent = `Deepgram · ${bot.llm_provider} · ${bot.tts_provider === "elevenlabs" ? "ElevenLabs" : (voice?.name || "Flux")}`;
        card.tabIndex = 0;
        card.addEventListener("click", () => selectBot(bot.id));
        card.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") selectBot(bot.id);
        });
        return card;
      }),
    );
  }
  elements.sessionKeys.hidden = !selectedBot() || selectedBot().has_saved_keys;
  elements.sessionElevenlabsKeyField.hidden = !(
    selectedBot()?.tts_provider === "elevenlabs" && !selectedBot()?.has_saved_keys
  );
  elements.start.disabled = !selectedBotId;
}

function selectedBot() {
  return bots.find((bot) => bot.id === selectedBotId);
}

function selectBot(botId) {
  selectedBotId = botId;
  renderBotList();
  const bot = selectedBot();
  if (bot) openEditor(bot);
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
  elements.botKeyFields.hidden = false;
  elements.byokHint.hidden = saving;
  elements.keepKeysHint.hidden = !(saving && editingHasKeys);
  const keysOptional = saving && editingHasKeys;
  elements.botDeepgramKey.required = saving && !keysOptional;
  elements.botLlmKey.required = saving && !keysOptional;
  elements.botElevenlabsKey.required =
    saving && elements.botTts.value === "elevenlabs" && !keysOptional;
}

function syncAsrAdvancedFields() {
  elements.botAsrEotThresholdValue.value = Number(
    elements.botAsrEotThreshold.value,
  ).toFixed(2);
}

function openEditor(bot) {
  clearError();
  editingBotId = bot ? bot.id : null;
  elements.editorTitle.textContent = bot ? `Edit bot` : "New bot";
  const title = document.querySelector("#current-bot-title");
  if (title) title.textContent = bot?.name || "New bot";
  elements.botName.value = bot ? bot.name : "";
  loadAsrCatalog(bot);
  elements.botAsrEotThreshold.value = bot?.asr_eot_threshold ?? 0.7;
  syncAsrAdvancedFields();
  elements.botAsrEotTimeout.value = bot?.asr_eot_timeout_ms ?? 5000;
  elements.botAsrKeyterms.value = (bot?.asr_keyterms || []).join("\n");
  elements.botAsrProfanity.checked = bot?.asr_profanity_filter ?? false;
  elements.botAsrNumerals.checked = bot?.asr_numerals ?? false;
  elements.botAsrRedact.value = bot?.asr_redact ?? "";
  elements.botTts.value = bot ? bot.tts_provider : "deepgram_flux";
  elements.botTtsAggregation.value = bot
    ? (bot.tts_text_aggregation || (bot.tts_provider === "elevenlabs" ? "sentence" : "token"))
    : "token";
  syncTtsFields();
  elements.botTtsModel.value = bot ? bot.tts_model : "flux-general-en";
  elements.botTtsSpeed.value = bot?.tts_speed ?? 1;
  elements.botFluxSpeed.value = bot?.tts_speed ?? 1;
  elements.botFluxExpressivity.value = bot?.tts_expressivity ?? 0;
  elements.botFluxMipOptOut.checked = bot?.tts_model_improvement_opt_out ?? false;
  elements.botTtsStability.value = bot?.tts_stability ?? 0.5;
  elements.botTtsSimilarity.value = bot?.tts_similarity_boost ?? 0.8;
  elements.botTtsStyle.value = bot?.tts_style ?? 0;
  elements.botTtsSpeakerBoost.checked = bot?.tts_use_speaker_boost ?? false;
  elements.botDynamicSpeed.checked = bot?.tts_dynamic_speed_enabled ?? false;
  elements.botSpeedStep.value = String(bot?.tts_speed_step ?? 0.1);
  elements.botTextNormalization.value = bot?.tts_text_normalization ?? "auto";
  syncElevenlabsSettings();
  syncFluxSettings();
  if (bot?.tts_provider === "elevenlabs") {
    elements.botVoice.replaceChildren(new Option(bot.tts_voice, bot.tts_voice, true, true));
  } else {
    fillVoiceSelect(elements.botVoice, bot ? bot.tts_voice : catalogs.defaults.flux_voice);
  }
  updateBotVoiceDisplay();
  fillProviderSelect(elements.botProvider, bot ? bot.llm_provider : catalogs.defaults.llm_provider);
  applyProviderPreset(botProviderRefs);
  if (bot) {
    elements.botBaseUrl.value = bot.llm_base_url;
    elements.botModel.value = bot.llm_model;
  }
  elements.botThinking.value = bot?.reasoning_mode ?? "provider_default";
  elements.botLlmTemperature.value = bot?.llm_temperature ?? 0.7;
  elements.botLlmTemperatureValue.value = Number(elements.botLlmTemperature.value).toFixed(1);
  elements.botLlmMaxTokens.value = bot?.llm_max_response_tokens ?? 250;
  elements.botLlmRequestTimeout.value = bot?.llm_request_timeout_seconds ?? 15;
  elements.botSystemPrompt.value = bot ? bot.system_prompt : catalogs.defaults.system_prompt;
  elements.botOpeningScript.value = bot ? bot.opening_script : catalogs.defaults.opening_script;
  elements.botFallbackScript.value = bot?.fallback_script ?? "";
  syncAdvancedBotContext();
  elements.botSaveKeys.checked = bot ? bot.has_saved_keys : false;
  elements.botDeepgramKey.value = "";
  elements.botLlmKey.value = "";
  elements.botElevenlabsKey.value = "";
  syncKeyFieldVisibility();
  elements.editor.hidden = false;
  elements.editor.dataset.open = "true";
  document.querySelector(".conversation-panel").hidden = true;
  document.querySelector(".history-panel").hidden = true;
  updatePipelineSummaries(bot || {
    asr_model: "flux-general-en", llm_model: catalogs.defaults.llm_model,
    llm_provider: catalogs.defaults.llm_provider, reasoning_mode: "provider_default",
    tts_voice: catalogs.defaults.flux_voice, tts_provider: "deepgram_flux",
    tts_model: "flux-general-en", tts_speed: 1, tts_dynamic_speed_enabled: false,
    tts_text_aggregation: "token",
  });
}

function closeEditor() {
  elements.editor.hidden = true;
  elements.editor.dataset.open = "false";
  editingBotId = null;
  syncAdvancedBotContext();
}

function syncAdvancedBotContext() {
  const bot = editingBotId && bots.find((item) => item.id === editingBotId);
  const context = document.querySelector("#advanced-bot-context");
  const save = document.querySelector("#save-advanced-settings");
  context.textContent = bot
    ? `Bot-specific settings for ${bot.name}.`
    : "Select a Bot to configure its advanced behavior.";
  save.disabled = !bot;
}

async function saveBot(event) {
  event.preventDefault();
  clearError();
  const saving = elements.botSaveKeys.checked;
  const deepgramKey = elements.botDeepgramKey.value;
  const llmKey = elements.botLlmKey.value;
  const elevenlabsKey = elements.botElevenlabsKey.value || elements.voiceDiscoveryKey.value;
  if (saving && elevenlabsKey && !elements.botElevenlabsKey.value) {
    elements.botElevenlabsKey.value = elevenlabsKey;
  }
  const requiredKeys = [deepgramKey, llmKey];
  if (elements.botTts.value === "elevenlabs") requiredKeys.push(elevenlabsKey);
  if (saving && requiredKeys.some(Boolean) && !requiredKeys.every(Boolean)) {
    showError("Enter all API keys required by the selected providers, or leave them blank to keep saved keys.");
    return;
  }
  if (!elements.botVoice.value) {
    showError("Choose a TTS voice before saving the bot.");
    return;
  }
  if (!elements.botForm.reportValidity()) return;

  const payload = {
    name: elements.botName.value.trim(),
    asr_provider: elements.botAsr.value,
    asr_model: elements.botAsrLanguage.value,
    asr_language_hints: [...elements.botAsrHints.selectedOptions].map((option) => option.value),
    asr_eot_threshold: Number(elements.botAsrEotThreshold.value),
    asr_eot_timeout_ms: Number(elements.botAsrEotTimeout.value),
    asr_keyterms: elements.botAsrKeyterms.value.split("\n").map((term) => term.trim()).filter(Boolean),
    asr_profanity_filter: elements.botAsrProfanity.checked,
    asr_numerals: elements.botAsrNumerals.checked,
    asr_redact: elements.botAsrRedact.value || null,
    tts_provider: elements.botTts.value,
    tts_voice: elements.botVoice.value,
    tts_model: elements.botTtsModel.value,
    tts_text_aggregation: elements.botTtsAggregation.value,
    tts_speed: Number(elements.botTts.value === "elevenlabs" ? elements.botTtsSpeed.value : elements.botFluxSpeed.value),
    tts_dynamic_speed_enabled: elements.botDynamicSpeed.checked,
    tts_speed_step: Number(elements.botSpeedStep.value),
    tts_expressivity: Number(elements.botFluxExpressivity.value),
    tts_model_improvement_opt_out: elements.botFluxMipOptOut.checked,
    tts_stability: Number(elements.botTtsStability.value),
    tts_similarity_boost: Number(elements.botTtsSimilarity.value),
    tts_style: Number(elements.botTtsStyle.value),
    tts_use_speaker_boost: elements.botTtsSpeakerBoost.checked,
    tts_text_normalization: elements.botTextNormalization.value,
    llm_provider: elements.botProvider.value,
    llm_base_url: elements.botBaseUrl.value,
    llm_model: elements.botModel.value,
    llm_temperature: Number(elements.botLlmTemperature.value),
    reasoning_mode: elements.botThinking.value,
    llm_max_response_tokens: Number(elements.botLlmMaxTokens.value),
    llm_request_timeout_seconds: Number(elements.botLlmRequestTimeout.value),
    system_prompt: elements.botSystemPrompt.value,
    opening_script: elements.botOpeningScript.value,
    fallback_script: elements.botFallbackScript.value,
    save_keys: saving,
  };
  if (saving && deepgramKey && llmKey) {
    payload.deepgram_api_key = deepgramKey;
    payload.llm_api_key = llmKey;
    if (elevenlabsKey) payload.elevenlabs_api_key = elevenlabsKey;
  }

  try {
    const saved = editingBotId
      ? await apiRequest(`/api/bots/${editingBotId}`, { method: "PUT", body: payload })
      : await apiRequest("/api/bots", { method: "POST", body: payload });
    elements.botDeepgramKey.value = "";
    elements.botLlmKey.value = "";
    elements.botElevenlabsKey.value = "";
    elements.voiceDiscoveryKey.value = "";
    payload.deepgram_api_key = "";
    payload.llm_api_key = "";
    payload.elevenlabs_api_key = "";
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

async function reportBrowserEvent(event, text) {
  if (!sessionId || !sessionToken || !sessionStartedAt) return;
  const elapsedMs = performance.now() - sessionStartedAt;
  try {
    await fetch(`/api/sessions/${sessionId}/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${sessionToken}`,
      },
      body: JSON.stringify({ event, elapsed_ms: elapsedMs, ...(text ? { text } : {}) }),
      keepalive: true,
    });
  } catch {
    // Telemetry must never interrupt the voice session.
  }
}

async function addLiveMetricCard(bubble) {
  if (!bubble || bubble.querySelector(".live-turn-metrics")) return;
  if (!userStoppedAt || !sessionId || !sessionToken) return;
  try {
    await playbackReportPromise;
  } catch {
    // The metric request below will expose the missing playback reason.
  }
  const response = await fetch(`/api/sessions/${sessionId}/metrics`, {
    headers: { Accept: "application/json", Authorization: `Bearer ${sessionToken}` },
  });
  if (!response.ok) return;
  const payload = await response.json();
  const metric = payload.metrics?.at(-1);
  if (!metric) return;
  const reasons = {
    word_timing_unavailable: "ASR word timing unavailable",
    audio_clock_mismatch: "ASR audio clock mismatch",
    interrupted_before_llm_first_token: "interrupted before LLM first token",
    session_ended_before_llm_first_token: "session ended before LLM first token",
    interrupted_before_tts_audio: "interrupted before TTS audio",
    session_ended_before_tts_audio: "session ended before TTS audio",
    interrupted_before_playback: "interrupted before playback",
    session_ended_before_playback: "session ended before playback",
  };
  const fmt = (value, reason) => value !== null && value !== undefined
    ? `${value} ms`
    : `not available (${reasons[reason] || "event not observed"})`;
  const parts = [];
  if (payload.session_type !== "chat_test") {
    parts.push(`ASR final ${fmt(metric.asr_final_latency_ms, metric.asr_final_reason)}`);
  }
  parts.push(
    `LLM splicing ${fmt(metric.llm_request_splicing_ms, metric.incomplete_reason)}`,
    `LLM TTFT ${fmt(metric.llm_first_token_ms, metric.incomplete_reason)}`,
    `TTS initial ${fmt(metric.tts_initial_ms, metric.incomplete_reason)}`,
    `TTS TTFT ${fmt(metric.tts_first_audio_ms, metric.incomplete_reason)}`,
    `playback ${fmt(metric.playback_ms, metric.incomplete_reason)}`,
    `e2e latency ${fmt(metric.turn_to_playback_ms, metric.incomplete_reason)}`,
    `reasoning ${metric.reasoning_status}/${metric.reasoning_tokens ?? "not reported"}`,
  );
  const card = document.createElement("div");
  card.className = "history-metric live-turn-metrics";
  card.textContent = `Turn ${metric.turn_index + 1}: ${parts.join(" · ")}`;
  bubble.append(card);
}

function createClient() {
  clientReady = false;
  currentAssistantBubble = undefined;
  currentAssistantText = "";
  const transportOptions = {
      recorderSampleRate: catalogs.defaults.audio.input_sample_rate,
      playerSampleRate: catalogs.defaults.audio.output_sample_rate,
    };
  if (testMode === "chat_test") {
    transportOptions.mediaManager = new OutputOnlyMediaManager(
      undefined,
      catalogs.defaults.audio.input_sample_rate,
    );
  }
  return new PipecatClient({
    transport: new WebSocketTransport(transportOptions),
    enableMic: testMode === "web_call",
    enableCam: false,
    disconnectOnBotDisconnect: true,
    callbacks: {
      onConnected: () => {
        elements.wsStatus.textContent = "Connected";
        elements.pipelineStatus.textContent = "Flux ready";
        setSessionState("connected", "Live");
      },
      onDisconnected: () => {
        clientReady = false;
        client = undefined;
        elements.wsStatus.textContent = "Disconnected";
        elements.pipelineStatus.textContent = "Standby";
        setFormLocked(false);
        setSessionState("idle", "Ready to start");
        elements.chatInput.disabled = true;
        elements.sendChat.disabled = true;
      },
      onTransportStateChanged: (state) => {
        elements.wsStatus.textContent = state[0].toUpperCase() + state.slice(1);
      },
      onBotReady: () => {
        clientReady = true;
        if (testMode === "chat_test") {
          elements.chatInput.disabled = false;
          elements.sendChat.disabled = false;
        }
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
        elements.pipelineStatus.textContent = `${selectedBot()?.tts_provider === "elevenlabs" ? "ElevenLabs" : "Flux"} TTS playing`;
        if (userStoppedAt) elements.e2eLatency.textContent = `${Math.round(now - userStoppedAt)} ms`;
        if (llmFirstTokenAt) {
          elements.synthesisLatency.textContent = `${Math.round(now - llmFirstTokenAt)} ms`;
        }
        playbackReportPromise = reportBrowserEvent("first_playback");
      },
      onBotStoppedSpeaking: async () => {
        botSpeaking = false;
        setSpeaker("idle", "Listening");
        elements.pipelineStatus.textContent = "Ready";
        await addLiveMetricCard(currentAssistantBubble);
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
  if (testMode === "web_call") await client.initDevices();
  await Promise.race([
    client.connect({ wsUrl: websocketUrl(session.websocket_path) }),
    new Promise((_, reject) => {
      window.setTimeout(() => reject(new Error("Connection timed out. End the test and retry.")), 15000);
    }),
  ]);
}

async function startBotSession() {
  clearError();
  const bot = selectedBot();
  if (!bot) {
    showError("Select a bot first, or create a new one.");
    return;
  }
  if (!ensureSecureContext()) return;
  const payload = { bot_id: bot.id, session_type: testMode };
  if (!bot.has_saved_keys) {
    if (!elements.sessionDeepgramKey.value || !elements.sessionLlmKey.value) {
      showError("This bot has no saved keys. Enter both API keys for this session.");
      return;
    }
    payload.deepgram_api_key = elements.sessionDeepgramKey.value;
    payload.llm_api_key = elements.sessionLlmKey.value;
    if (bot.tts_provider === "elevenlabs") {
      if (!elements.sessionElevenlabsKey.value) {
        showError("This bot uses ElevenLabs. Enter its API key for this session.");
        return;
      }
      payload.elevenlabs_api_key = elements.sessionElevenlabsKey.value;
    }
  }

  resetLiveTestView();
  setFormLocked(true);
  setSessionState("connecting", "Connecting");
  setSpeaker("thinking", testMode === "chat_test" ? "Connecting text test" : "Requesting microphone access");
  if (testMode === "chat_test") {
    elements.chatInput.disabled = true;
    elements.sendChat.disabled = true;
  }
  try {
    const session = await apiRequest("/api/sessions", { method: "POST", body: payload });
    elements.sessionDeepgramKey.value = "";
    elements.sessionLlmKey.value = "";
    elements.sessionElevenlabsKey.value = "";
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
  clientReady = false;
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
  playbackReportPromise = undefined;
  setFormLocked(false);
  setSessionState("idle", "Ready to start");
  setSpeaker("idle", "Select a bot, then start a session");
  elements.wsStatus.textContent = "Disconnected";
  elements.pipelineStatus.textContent = "Standby";
  if (!preserveError) clearError();
  await loadHistory().catch(() => {});
}

// --- Wiring -------------------------------------------------------------------

elements.toggleProductRail.addEventListener("click", () => {
  elements.productRail.classList.toggle("expanded");
  elements.toggleProductRail.setAttribute(
    "aria-label",
    elements.productRail.classList.contains("expanded") ? "Collapse product rail" : "Expand product rail",
  );
});

document.querySelectorAll(".product-tabs button").forEach((button) => {
  button.addEventListener("click", () => {
    if (!elements.historyDialog.hidden) closeHistoryDrawer();
    document.querySelector(".component-drawer:not([hidden])")?.querySelector("header button")?.click();
    document.querySelectorAll(".product-tabs button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    const page = button.dataset.page;
    document.querySelector(".workspace").hidden = false;
    document.querySelector("#advanced-empty").hidden = page !== "advanced";
    document.querySelector(".history-panel").hidden = page !== "sessions";
    elements.editor.hidden = page !== "settings" || elements.editor.dataset.open !== "true";
    document.querySelector(".conversation-panel").hidden = true;
    if (page === "advanced") syncAdvancedBotContext();
    if (page === "sessions") loadHistory().catch((error) => showError(error.message));
  });
});

function selectTestMode(mode) {
  testMode = mode;
  const chat = mode === "chat_test";
  elements.chatTestTab.classList.toggle("active", chat);
  elements.webCallTab.classList.toggle("active", !chat);
  elements.chatComposer.hidden = !chat;
  elements.start.textContent = "Start test";
  const conversationHeader = document.querySelector(".conversation-header");
  conversationHeader.querySelector("h2").textContent = chat ? "Chat test" : "Web call test";
  conversationHeader.querySelector(".eyebrow").textContent = chat
    ? "Text → LLM → TTS test with Agent audio playback."
    : "Live ASR → LLM → TTS test with real-time captions.";
  elements.speaker.textContent = chat
    ? "Start to test text → LLM → TTS"
    : "Select a bot, then start a Web call";
  elements.transcript.querySelector(".empty-state p")?.replaceChildren(
    chat
      ? "Opening message and text replies will play through the configured TTS."
      : "Caller and Agent captions will appear here in real time.",
  );
}

elements.chatTestTab.addEventListener("click", () => selectTestMode("chat_test"));
elements.webCallTab.addEventListener("click", () => selectTestMode("web_call"));
elements.chatComposer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = elements.chatInput.value.trim();
  if (!text) return;
  if (!client || !clientReady) {
    showError("Chat test is not connected. Start the test and wait until it is ready.");
    return;
  }
  const interrupted = botSpeaking;
  if (interrupted) reportBrowserEvent("browser_interruption");
  addTranscript("user", text);
  await reportBrowserEvent("chat_text", text);
  elements.chatInput.value = "";
  userStoppedAt = performance.now();
  llmFirstTokenAt = undefined;
  currentAssistantBubble = undefined;
  currentAssistantText = "";
  try {
    await client.sendText(text, { run_immediately: true, audio_response: true });
  } catch (error) {
    showError(error instanceof Error ? error.message : "Could not send the chat message.");
  }
});

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
document.querySelector("#save-advanced-settings").addEventListener("click", () => {
  if (!editingBotId) {
    showError("Create or select a Bot before saving advanced settings.");
    return;
  }
  elements.botForm.requestSubmit();
});
elements.botSaveKeys.addEventListener("change", syncKeyFieldVisibility);
elements.botElevenlabsKey.addEventListener("input", syncTtsVoiceAvailability);
elements.botTts.addEventListener("change", () => {
  elements.botVoice.replaceChildren();
  syncTtsFields();
});
elements.botTtsModel.addEventListener("change", syncElevenlabsSettings);
elements.botAsrLanguage.addEventListener("change", syncAsrLanguage);
elements.botAsrEotThreshold.addEventListener("input", syncAsrAdvancedFields);
elements.botLlmTemperature.addEventListener("input", () => {
  elements.botLlmTemperatureValue.value = Number(elements.botLlmTemperature.value).toFixed(1);
});
elements.botDynamicSpeed.addEventListener("change", syncElevenlabsSettings);
elements.botTtsAggregation.addEventListener("change", syncElevenlabsSettings);
elements.botFluxExpressivity.addEventListener("input", syncFluxSettings);
elements.botFluxSpeed.addEventListener("input", syncFluxSettings);
for (const input of [
  elements.botTtsStability,
  elements.botTtsSimilarity,
  elements.botTtsStyle,
  elements.botTtsSpeed,
]) input.addEventListener("input", syncElevenlabsSettings);
elements.chooseBotVoice.addEventListener("click", openVoicePicker);
elements.closeVoicePicker.addEventListener("click", () => elements.voicePickerDialog.close());
elements.cancelVoicePicker.addEventListener("click", () => elements.voicePickerDialog.close());
elements.confirmVoicePicker.addEventListener("click", () => {
  if (pendingVoice) selectVoice(pendingVoice);
});
elements.voiceSearch.addEventListener("input", renderVoicePicker);
elements.voiceLanguage.addEventListener("change", renderVoicePicker);
elements.voiceGender.addEventListener("change", renderVoicePicker);
elements.loadMoreVoices.addEventListener("click", async () => {
  await loadElevenlabsVoices({ append: true });
  renderVoicePicker();
});
elements.useManualVoice.addEventListener("click", () => {
  const voiceId = elements.manualVoiceId.value.trim();
  if (voiceId) {
    pendingVoice = { voice_id: voiceId, name: voiceId };
    renderVoicePicker();
  }
});
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
for (const filter of [elements.historyFrom, elements.historyTo, elements.historyType]) {
  filter.addEventListener("change", renderHistory);
}
elements.closeHistory.addEventListener("click", (event) => {
  event.preventDefault();
  closeHistoryDrawer();
});

async function boot() {
  initializeWebsiteSession();
  initializeComponentEditor();
  initializePrototypeLayout();
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
    if (selectedBot()) openEditor(selectedBot());
    else openEditor(null);
    const returnPage = sessionStorage.getItem("voiceagent-return-page");
    if (returnPage) {
      sessionStorage.removeItem("voiceagent-return-page");
      document.querySelector(`.product-tabs button[data-page="${returnPage}"]`)?.click();
    }
  } catch {
    showError("Could not load your bots. Reload the page to try again.");
  }
}

boot();
