import { expect, test } from "@playwright/test";
import path from "node:path";

const evidenceDir = path.resolve(
  "../openspec/changes/redesign-voice-bot-configuration-and-testing/verification/actual",
);

const voiceFixture = {
  voices: [
    {
      voice_id: "fixture-alexis",
      name: "Alexis — clear, professional and calm",
      labels: { language: "en", accent: "american", gender: "female" },
      description: "Deterministic UI fixture voice with an intentionally long description.",
      preview_url: null,
    },
    {
      voice_id: "fixture-omar",
      name: "Omar — Arabic conversational voice",
      labels: { language: "ar", accent: "modern standard", gender: "male" },
      description: "Deterministic Arabic fixture voice.",
      preview_url: null,
    },
  ],
  next_page_token: null,
  has_more: false,
};

async function waitForProduct(page) {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Bot settings", exact: true })).toBeVisible();
  await expect(page.locator(".bot-card").first()).toBeVisible();
}

async function chooseBot(page, pattern) {
  const card = page.locator(".bot-card").filter({ hasText: pattern }).first();
  await expect(card).toBeVisible();
  await card.click();
}

async function expectNoHorizontalOverflow(locator) {
  const dimensions = await locator.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

test("component drawers preserve approved ASR and LLM structure", async ({ page }, testInfo) => {
  await waitForProduct(page);

  await page.getByRole("button", { name: /TRANSCRIBER · ASR/ }).click();
  const drawer = page.locator(".component-drawer");
  await expect(drawer.getByText("Audio input", { exact: true })).toBeVisible();
  await expect(drawer.getByLabel("Audio input PCM 16 kHz")).toBeVisible();
  await drawer.getByText("ASR Advanced", { exact: true }).click();
  await expect(drawer.locator('#bot-asr-eot-threshold[type="range"]')).toBeVisible();
  await expect(drawer.locator("#bot-asr-eot-timeout")).toBeVisible();
  await expect(drawer.locator("#bot-asr-keyterms")).toBeVisible();
  await expectNoHorizontalOverflow(drawer);

  await drawer.getByRole("button", { name: "Collapse component drawer" }).click();
  await page.getByRole("button", { name: /MODEL · LLM/ }).click();
  await drawer.locator('[data-panel="llm"] details').first().locator("summary").click();
  await expect(drawer.getByText("Max response tokens", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Request timeout", { exact: true })).toBeVisible();
  await expect(drawer.getByRole("button", { name: "Test LLM connection" })).toBeVisible();
  await expectNoHorizontalOverflow(drawer);

  await page.screenshot({
    path: path.join(evidenceDir, `gate3.llm.${testInfo.project.name}.png`),
    animations: "disabled",
  });
});

test("TTS provider rules and voice picker are responsive", async ({ page }, testInfo) => {
  await page.route("**/api/tts/elevenlabs/voices", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(voiceFixture) }),
  );
  await waitForProduct(page);
  await chooseBot(page, /Elevenlabs/i);
  await page.getByRole("button", { name: /VOICE · TTS/ }).click();
  const drawer = page.locator(".component-drawer");
  const ttsPanel = drawer.locator('[data-panel="tts"]');
  const provider = ttsPanel.getByLabel("TTS provider");
  await expect(provider).toHaveValue("elevenlabs");
  await expect(ttsPanel.getByLabel("ElevenLabs API key")).toBeEditable();
  await expect(ttsPanel.getByRole("button", { name: /Change voice|Choose voice/ })).toBeVisible();

  await provider.selectOption("deepgram_flux");
  await expect(drawer.locator("#bot-tts-model")).toHaveValue("flux-general-en");
  await expect(ttsPanel.getByText("Custom voice ID", { exact: true })).toHaveCount(0);
  await expect(ttsPanel.getByRole("button", { name: /Choose voice|Change voice/ })).toBeEnabled();

  await provider.selectOption("elevenlabs");
  await ttsPanel.getByRole("button", { name: /Change voice|Choose voice/ }).click();
  const picker = page.locator("#voice-picker-dialog");
  await expect(picker).toBeVisible();
  await expectNoHorizontalOverflow(picker);
  await page.screenshot({
    path: path.join(evidenceDir, `gate3.voice-picker.${testInfo.project.name}.png`),
    animations: "disabled",
  });
  await picker.getByRole("button", { name: "Close" }).click();
});

test("Sessions remain a list and their detail drawer closes", async ({ page }, testInfo) => {
  await waitForProduct(page);
  await page.getByRole("button", { name: "Sessions" }).click();
  await expect(page.getByPlaceholder("YYYY-MM-DD")).toHaveCount(2);
  const rows = page.locator(".history-row");
  await expect(rows.first()).toBeVisible();
  await rows.first().click();
  const details = page.locator("#history-dialog");
  await expect(details).toBeVisible();
  await expect(details.getByRole("button", { name: "Close session details" })).toBeVisible();
  await expectNoHorizontalOverflow(details);
  await details.getByRole("button", { name: "Close session details" }).click();
  await expect(details).toBeHidden();
  await page.screenshot({
    path: path.join(evidenceDir, `gate3.sessions.${testInfo.project.name}.png`),
    animations: "disabled",
  });
});

test("Advanced is Bot-scoped and keeps the Bot selector", async ({ page }, testInfo) => {
  await waitForProduct(page);
  await page.getByRole("button", { name: "Advanced" }).click();
  await expect(page.locator(".bot-list")).toBeVisible();
  await expect(page.locator("#advanced-bot-context")).toContainText("Bot-specific settings for");
  await expect(page.getByLabel("Fallback script")).toBeVisible();
  await page.screenshot({
    path: path.join(evidenceDir, `gate3.advanced.${testInfo.project.name}.png`),
    animations: "disabled",
  });
});

test("Automatic ASR and credential states remain usable", async ({ page }) => {
  await waitForProduct(page);
  await page.getByRole("button", { name: /TRANSCRIBER · ASR/ }).click();
  const drawer = page.locator(".component-drawer");
  const asrPanel = drawer.locator('[data-panel="asr"]');
  await asrPanel.locator("#bot-asr-language").selectOption("flux-general-multi");
  await expect(asrPanel.getByRole("group", { name: "Optional language hints" })).toBeVisible();
  await expect(asrPanel.locator(".check-chip")).toHaveCount(10);
  await expect(asrPanel.getByLabel("Deepgram API key")).toBeEditable();
  await drawer.locator("#bot-save-keys").uncheck();
  await expect(asrPanel.getByLabel("Deepgram API key")).toBeEditable();
});

test("catalog failure is explicit and disables unsafe actions", async ({ page }) => {
  await page.route("**/api/catalogs", (route) =>
    route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"fixture outage"}' }),
  );
  await page.goto("/");
  await expect(page.locator("#error-banner")).toContainText("server is unavailable");
  await expect(page.locator("#new-bot-button")).toBeDisabled();
  await expect(page.locator("#start-button")).toBeDisabled();
});

test("interactive controls have names and overlays contain keyboard focus", async ({ page }) => {
  await page.route("**/api/tts/elevenlabs/voices", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(voiceFixture) }),
  );
  await waitForProduct(page);
  const duplicateIds = await page.locator("[id]").evaluateAll((elements) => {
    const counts = new Map();
    for (const element of elements) counts.set(element.id, (counts.get(element.id) || 0) + 1);
    return [...counts.entries()].filter(([, count]) => count > 1);
  });
  expect(duplicateIds).toEqual([]);
  await chooseBot(page, /Elevenlabs/i);
  await page.getByRole("button", { name: /VOICE · TTS/ }).click();
  await page.locator('[data-panel="tts"]').getByRole("button", { name: /Change voice|Choose voice/ }).click();
  const picker = page.locator("#voice-picker-dialog");
  await expect(picker).toBeVisible();
  await page.keyboard.press("Tab");
  const focusInside = await page.evaluate(() =>
    document.querySelector("#voice-picker-dialog")?.contains(document.activeElement),
  );
  expect(focusInside).toBe(true);
  await page.keyboard.press("Escape");
  await expect(picker).toBeHidden();
});
