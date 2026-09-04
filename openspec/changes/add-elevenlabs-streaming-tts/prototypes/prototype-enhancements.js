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
