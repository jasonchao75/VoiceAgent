/** Keep prototype-only behavior aligned with provider-aware production rules. */
document.addEventListener("DOMContentLoaded", () => {
  const providerSelect = document.querySelector("#provider");
  const apiKeyFieldset = [...document.querySelectorAll("fieldset")].find(
    (fieldset) => fieldset.querySelector("legend")?.textContent === "API keys",
  );
  const elevenLabsLabel = [...apiKeyFieldset.querySelectorAll("label")].find(
    (label) => label.textContent.includes("ElevenLabs API key"),
  );
  const elevenLabsInput = elevenLabsLabel.nextElementSibling;
  const elevenLabsHint = elevenLabsInput.nextElementSibling;
  const pipelineFieldset = providerSelect.closest("fieldset");

  const aggregationLabel = document.createElement("label");
  aggregationLabel.htmlFor = "textAggregation";
  aggregationLabel.textContent = "TTS text aggregation";
  const aggregationSelect = document.createElement("select");
  aggregationSelect.id = "textAggregation";
  aggregationSelect.innerHTML = `
    <option value="token">Token · Lowest latency</option>
    <option value="sentence">Sentence · More stable prosody</option>
  `;
  const aggregationHint = document.createElement("p");
  aggregationHint.className = "hint";
  aggregationHint.textContent = "Token streams LLM output immediately; Sentence waits for a sentence boundary. Supported by both TTS providers.";
  const voiceLabel = [...pipelineFieldset.querySelectorAll("label")].find(
    (label) => label.textContent.trim() === "Voice",
  );
  pipelineFieldset.insertBefore(aggregationLabel, voiceLabel);
  pipelineFieldset.insertBefore(aggregationSelect, voiceLabel);
  pipelineFieldset.insertBefore(aggregationHint, voiceLabel);

  const tuningFieldset = document.createElement("fieldset");
  tuningFieldset.id = "elevenlabsTuning";
  tuningFieldset.innerHTML = `
    <legend>ElevenLabs voice tuning</legend>
    <label for="ttsModel">Model</label>
    <select id="ttsModel">
      <option value="eleven_flash_v2_5">Flash v2.5 · Ultra-low latency</option>
      <option value="eleven_turbo_v2_5">Turbo v2.5 · Balanced</option>
      <option value="eleven_multilingual_v2">Multilingual v2 · Stable long-form</option>
      <option value="eleven_v3">Eleven v3 · Most expressive</option>
    </select>
    <p class="hint" id="modelHint">Recommended for realtime conversation.</p>
    <details class="voice-advanced" open>
      <summary>Voice settings</summary>
      <div class="voice-setting"><div><label for="stability">Stability</label><output id="stabilityValue">0.50</output></div><input id="stability" type="range" min="0" max="1" step="0.05" value="0.5"><small id="stabilityScale">More variable ↔ More stable</small></div>
      <div class="voice-setting"><div><label for="similarity">Clarity + Similarity</label><output id="similarityValue">0.80</output></div><input id="similarity" type="range" min="0" max="1" step="0.05" value="0.8"><small>Low ↔ High</small></div>
      <div class="voice-setting"><div><label for="style">Style exaggeration</label><output id="styleValue">0.00</output></div><input id="style" type="range" min="0" max="1" step="0.05" value="0"><small>Natural / faster ↔ Exaggerated</small></div>
      <div class="voice-setting"><div><label for="speed">Speed</label><output id="speedValue">1.00</output></div><input id="speed" type="range" min="0.7" max="1.2" step="0.05" value="1"><small>Slower ↔ Faster</small></div>
      <label class="switch-row"><span><b>Use speaker boost</b><small>May improve similarity at some generation cost.</small></span><input id="speakerBoost" type="checkbox"></label>
      <label class="switch-row"><span><b>Auto mode <em id="autoModeState">Off · derived</em></b><small id="autoModeHint">Token input keeps ElevenLabs chunk scheduling enabled.</small></span><input id="autoMode" type="checkbox" disabled></label>
      <label for="textNormalization" style="margin-top:16px">Text normalization</label>
      <select id="textNormalization">
        <option value="auto">Auto · Recommended</option>
        <option value="on">On · Force numbers/dates into spoken form</option>
        <option value="off">Off · Synthesize original text</option>
      </select>
      <p class="hint">Independent from Auto mode. Flash may restrict forced normalization by account plan; provider errors are shown without silent fallback.</p>
    </details>
  `;
  pipelineFieldset.insertAdjacentElement("afterend", tuningFieldset);

  const prototypeStyle = document.createElement("style");
  prototypeStyle.textContent = `
    .voice-advanced { margin-top: 14px; border-top: 1px solid #2a342f; padding-top: 12px; }
    .voice-advanced summary { cursor: pointer; color: #dbe5df; font-weight: 700; }
    .voice-setting { margin-top: 14px; }
    .voice-setting > div, .switch-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .voice-setting label { margin: 0; }
    .voice-setting output { min-width: 42px; border: 1px solid #34423a; border-radius: 7px; padding: 3px 7px; color: #9fffd1; text-align: center; }
    .voice-setting input[type="range"] { padding: 0; accent-color: #51e39c; }
    .voice-setting small, .switch-row small { display: block; color: #829088; font-size: 10px; }
    .switch-row { margin-top: 16px; cursor: pointer; }
    .switch-row b { display: block; font-size: 12px; }
    .switch-row em { color: #9fffd1; font-size: 10px; font-style: normal; font-weight: 500; }
    .switch-row input { width: auto; accent-color: #51e39c; }
    .voice-setting.is-disabled { opacity: .45; }
  `;
  document.head.appendChild(prototypeStyle);

  ["stability", "similarity", "style", "speed"].forEach((id) => {
    const input = document.querySelector(`#${id}`);
    const output = document.querySelector(`#${id}Value`);
    input.addEventListener("input", () => { output.value = Number(input.value).toFixed(2); });
  });

  const modelSelect = document.querySelector("#ttsModel");
  modelSelect.addEventListener("change", () => {
    const hints = {
      eleven_flash_v2_5: "Recommended for realtime conversation.",
      eleven_turbo_v2_5: "Balanced latency and quality.",
      eleven_multilingual_v2: "Most stable for longer generations; higher latency.",
      eleven_v3: "Most expressive; use Stability 0 / 0.5 / 1 as Creative / Natural / Robust.",
    };
    const isV3 = modelSelect.value === "eleven_v3";
    const stability = document.querySelector("#stability");
    const similarity = document.querySelector("#similarity");
    const speakerBoost = document.querySelector("#speakerBoost");
    document.querySelector("#modelHint").textContent = hints[modelSelect.value];
    document.querySelector("#stabilityScale").textContent = isV3
      ? "Creative (0) · Natural (0.5) · Robust (1)"
      : "More variable ↔ More stable";
    stability.step = isV3 ? "0.5" : "0.05";
    if (isV3) {
      stability.value = String([0, 0.5, 1].reduce((closest, value) =>
        Math.abs(value - Number(stability.value)) < Math.abs(closest - Number(stability.value))
          ? value
          : closest,
      0.5));
      document.querySelector("#stabilityValue").value = Number(stability.value).toFixed(2);
    }
    similarity.disabled = isV3;
    speakerBoost.disabled = isV3;
    similarity.closest(".voice-setting").classList.toggle("is-disabled", isV3);
    speakerBoost.closest(".switch-row").classList.toggle("is-disabled", isV3);
  });

  aggregationSelect.addEventListener("change", () => {
    const sentenceMode = aggregationSelect.value === "sentence";
    const autoMode = document.querySelector("#autoMode");
    autoMode.checked = sentenceMode;
    document.querySelector("#autoModeState").textContent = sentenceMode
      ? "On · derived"
      : "Off · derived";
    document.querySelector("#autoModeHint").textContent = sentenceMode
      ? "Complete-sentence input skips ElevenLabs chunk scheduling for lower latency."
      : "Token input keeps ElevenLabs chunk scheduling enabled.";
  });

  const commonKeys = document.createElement("div");
  commonKeys.innerHTML = `
    <label>Deepgram API key</label>
    <input type="password" value="••••••••••••••">
    <p class="hint">Required for Deepgram ASR · encrypted before storage</p>
    <label>LLM API key</label>
    <input type="password" value="••••••••••••••">
    <p class="hint">Required for the selected LLM · encrypted before storage</p>
  `;
  apiKeyFieldset.insertBefore(commonKeys, elevenLabsLabel);

  function refreshProviderFields() {
    const usesElevenLabs = providerSelect.value === "elevenlabs";
    elevenLabsLabel.classList.toggle("hidden", !usesElevenLabs);
    elevenLabsInput.classList.toggle("hidden", !usesElevenLabs);
    elevenLabsHint.classList.toggle("hidden", !usesElevenLabs);
    tuningFieldset.classList.toggle("hidden", !usesElevenLabs);

    [["language", 3, "All languages"], ["gender", 5, "All genders"]].forEach(
      ([id, index, placeholder]) => {
        const select = document.querySelector(`#${id}`);
        const values = [...new Set(C[p].map((voice) => voice[index] || "Unspecified"))].sort();
        select.innerHTML = `<option value="all">${placeholder}</option>${values
          .map((value) => `<option>${value}</option>`)
          .join("")}`;
      },
    );
  }

  providerSelect.addEventListener("change", refreshProviderFields);
  refreshProviderFields();
});
