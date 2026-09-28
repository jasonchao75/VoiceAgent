import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const evidenceDir = path.resolve(
  process.env.VOICE_AGENT_EVIDENCE_DIR
    || "../openspec/changes/add-streaming-asr-providers/verification",
);
const productFixture = JSON.parse(
  readFileSync(path.resolve("../tests/ui/fixtures/voice-bot-editor.json"), "utf8"),
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

test.beforeEach(async ({ page }) => {
  await page.route("**/api/bots", (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(productFixture.bots),
    });
  });
  await page.route("**/api/history?*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: productFixture.history.items,
        total: productFixture.history.items.length,
        limit: 25,
        offset: 0,
      }),
    }),
  );
  await page.route("**/api/history/*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(productFixture.history.detail),
    }),
  );
});

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
  await expect(drawer.getByText("Advanced · Deepgram Flux", { exact: true })).toBeVisible();
  await expect(drawer.locator("#asr-eot-threshold")).toBeVisible();
  await expect(drawer.locator("#asr-eot-timeout")).toBeVisible();
  await expect(drawer.locator("#asr-keyterms")).toBeVisible();
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
  await page.getByRole("button", { name: "Create bot" }).click();
  const asrCard = page.getByRole("button", { name: /TRANSCRIBER · ASR/ });
  await expect(asrCard).toContainText("Deepgram · Automatic");
  await expect(asrCard).not.toContainText("undefined");
  await asrCard.click();
  const drawer = page.locator(".component-drawer");
  const asrPanel = drawer.locator('[data-panel="asr"]');
  await asrPanel.locator("#bot-asr-model").selectOption("flux-general-multi");
  await expect(asrPanel.getByRole("group", { name: "Optional language hints" })).toBeVisible();
  await expect(asrPanel.locator(".check-chip")).toHaveCount(10);
  await expect(asrPanel.getByLabel("Deepgram API key")).toBeEditable();
  await drawer.locator("#bot-save-keys").uncheck();
  await expect(asrPanel.getByLabel("Deepgram API key")).toBeEditable();
});

test("account ASR catalogs stay isolated when switching Bots", async ({ page }) => {
  const base = productFixture.bots[0];
  const accountA = {
    ...base,
    id: "bot-account-a",
    name: "Account A bot",
    asr_provider: "speechmatics",
    asr_model: "enhanced",
    has_asr_key: true,
    asr_options: { language: "en", domain: null },
    asr_account_catalog: {
      id: "enhanced",
      name: "Realtime Enhanced",
      language_control: { kind: "single", values: ["en"], account_filtered: true },
      domains_by_language: { en: ["finance"] },
      turn_sources: ["provider_native", "off"],
      default_turn_source: "provider_native",
      advanced_title: "Speechmatics",
      advanced_fields: [
        { id: "asr-include-partials", name: "include_partials", label: "Include partials", kind: "boolean", default: true },
      ],
    },
  };
  const accountB = {
    ...accountA,
    id: "bot-account-b",
    name: "Account B bot",
    asr_account_catalog: null,
  };
  await page.route("**/api/bots", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify([accountA, accountB]),
  }));
  await page.route("**/api/asr/catalog", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 250));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(accountA.asr_account_catalog),
    });
  });
  await waitForProduct(page);
  await chooseBot(page, /Account A bot/);
  const backToSettings = page.getByRole("button", { name: "Back to bot settings" });
  if (await backToSettings.isVisible()) await backToSettings.click();
  await page.getByRole("button", { name: /TRANSCRIBER · ASR/ }).click();
  const drawer = page.locator(".component-drawer");
  await expect(drawer.getByLabel("Language", { exact: true }).locator("option")).toHaveCount(1);
  const refresh = drawer.locator("#asr-refresh-catalog");
  await expect(refresh).toBeEnabled();
  const idleBorder = await refresh.evaluate((element) => getComputedStyle(element).borderColor);
  await refresh.hover();
  await expect.poll(() => refresh.evaluate((element) => getComputedStyle(element).borderColor)).not.toBe(idleBorder);
  await refresh.click();
  await expect(refresh).toHaveAttribute("aria-busy", "true");
  await expect(refresh).toContainText("Refreshing catalog…");
  await expect(refresh).toContainText("Refresh account catalog");
  await expect(refresh).toBeEnabled();
  await drawer.getByRole("button", { name: "Collapse component drawer" }).click();

  await chooseBot(page, /Account B bot/);
  if (await backToSettings.isVisible()) await backToSettings.click();
  await page.getByRole("button", { name: /TRANSCRIBER · ASR/ }).click();
  await expect(drawer.getByLabel("Language", { exact: true }).locator('option[value="ar_en"]')).toHaveCount(1);
});

test("provider catalog drives model, language, Turn, and advanced branches", async ({ page }, testInfo) => {
  if (testInfo.project.name === "narrow-chromium") {
    await page.setViewportSize({ width: 390, height: 844 });
  }
  await waitForProduct(page);
  await page.getByRole("button", { name: /TRANSCRIBER · ASR/ }).click();
  const panel = page.locator('[data-panel="asr"]');
  const provider = panel.getByLabel("ASR provider");
  const model = panel.getByLabel("Model");

  await provider.selectOption("deepgram");
  await model.selectOption("nova-3");
  await expect(panel.getByLabel("Turn detection source")).toHaveValue("off");
  await expect(panel.getByLabel("Turn detection source")).toBeDisabled();
  await expect(panel.getByLabel("Endpointing silence (ms)")).toHaveValue("300");
  await page.screenshot({ path: path.join(evidenceDir, `actual-gate-2-deepgram-nova.${testInfo.project.name}.png`), animations: "disabled" });

  await provider.selectOption("speechmatics");
  await expect(model).toHaveValue("enhanced");
  await expect(panel.locator("#asr-refresh-catalog")).toHaveClass(/catalog-refresh-button/);
  await expect(panel.locator("#asr-refresh-catalog")).toBeDisabled();
  await panel.getByLabel("Language", { exact: true }).selectOption("ar_en");
  await expect(panel.getByLabel("Domain")).toHaveValue("");
  await expect(panel.getByLabel("Domain").locator('option[value="medical"]')).toHaveCount(1);
  await panel.getByLabel("Domain").selectOption("medical");
  await panel.getByRole("button", { name: "Add vocabulary" }).click();
  await panel.getByLabel("Vocabulary phrase").fill("Riyad Bank");
  await panel.getByLabel("Sounds like, comma separated").fill("riyad bank, riad bank");
  await panel.getByLabel("Language", { exact: true }).selectOption("en");
  await expect(panel.getByLabel("Domain")).toHaveValue("medical");
  await expect(panel.getByLabel("Vocabulary phrase")).toHaveValue("Riyad Bank");
  await expect(panel.getByLabel("Sounds like, comma separated")).toHaveValue("riyad bank, riad bank");
  await panel.getByLabel("Turn detection source").selectOption("off");
  await expect(panel.getByLabel("Turn mode")).toHaveValue("fixed");
  await expect(panel.getByLabel("Turn mode")).toBeDisabled();
  await panel.getByLabel("Permitted punctuation marks").selectOption("custom");
  await expect(panel.getByLabel("Custom marks · one character per line")).toBeVisible();
  await page.screenshot({ path: path.join(evidenceDir, `actual-gate-2-speechmatics.${testInfo.project.name}.png`), animations: "disabled" });

  await provider.selectOption("soniox");
  await panel.getByLabel("Add language hint").fill("Arabic");
  await expect(panel.getByLabel("Language ar (Arabic)", { exact: true })).toBeVisible();
  await panel.getByLabel("Add language hint").fill("ar");
  await panel.getByLabel("Language ar (Arabic)", { exact: true }).check();
  await expect(panel.getByLabel("Language ar (Arabic)", { exact: true })).toBeChecked();
  await panel.getByRole("button", { name: "Clear all" }).click();
  await expect(panel.getByLabel("Language ar (Arabic)", { exact: true })).not.toBeChecked();
  await page.screenshot({ path: path.join(evidenceDir, `actual-gate-2-soniox.${testInfo.project.name}.png`), animations: "disabled" });

  await provider.selectOption("assemblyai");
  await panel.getByLabel("Language ar (Arabic)", { exact: true }).check();
  expect(await panel.locator('#bot-asr-hints option[value="ar"]').evaluate((option) => option.selected)).toBe(true);
  await expect(panel.getByLabel("Language ar (Arabic)", { exact: true })).toHaveCount(1);
  await expect(panel.getByLabel("Language de (German)", { exact: true })).toHaveCount(1);
  await panel.getByLabel("Mode", { exact: true }).selectOption("min_latency");
  await expect(panel.getByLabel("Maximum turn silence (ms)")).toHaveValue("640");
  await panel.getByLabel("Maximum turn silence (ms)").fill("700");
  await expect(panel.locator("#asr-assembly-mode-note")).toContainText("modified values");
  await expect(panel.getByLabel("AssemblyAI API key")).toBeEditable();
  await expectNoHorizontalOverflow(page.locator(".component-drawer"));
  await page.screenshot({ path: path.join(evidenceDir, `actual-gate-2-assemblyai.${testInfo.project.name}.png`), animations: "disabled" });
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
