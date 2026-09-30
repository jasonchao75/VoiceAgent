import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import encodeQR from "qr";
import decodeQR from "qr/decode.js";

const fixture = JSON.parse(readFileSync(path.resolve("../tests/ui/fixtures/voice-bot-editor.json"), "utf8"));
const runtime = JSON.parse(readFileSync(path.resolve("../configs/runtime/agent.json"), "utf8"));
const voices = JSON.parse(readFileSync(path.resolve("../configs/runtime/flux_voices.json"), "utf8"));
const llms = JSON.parse(readFileSync(path.resolve("../configs/runtime/llm_providers.json"), "utf8"));
const evidenceDir = path.resolve("../openspec/changes/add-mobile-webrtc-demo-sharing/verification/checkpoint-a");
const catalog = {
  defaults: {
    llm_provider: runtime.llm.provider,
    llm_base_url: runtime.llm.base_url,
    llm_model: runtime.llm.model,
    reasoning_mode: runtime.llm.reasoning_mode,
    system_prompt: runtime.system_prompt,
    opening_script: runtime.opening_script,
    flux_voice: runtime.tts.voice,
    audio: runtime.audio,
  },
  flux_voices: voices,
  llm_providers: llms,
  asr_providers: {
    providers: [{
      id: "deepgram", name: "Deepgram", models: ["flux-general-en", "flux-general-multi"].map((id) => ({
        id, name: id, language_control: { kind: id.endsWith("multi") ? "hints" : "fixed", values: ["en"] },
        turn_sources: ["provider_native"], default_turn_source: "provider_native", advanced_title: "Deepgram Flux", advanced_fields: [],
      })),
    }],
  },
};

function decodeGeneratedQr(value) {
  const matrix = encodeQR(value, "raw", { ecc: "medium", border: 3 });
  const scale = 8;
  const width = matrix.length * scale;
  const data = new Uint8ClampedArray(width * width * 4);
  for (let y = 0; y < width; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const black = matrix[Math.floor(y / scale)][Math.floor(x / scale)];
      const offset = (y * width + x) * 4;
      data[offset] = black ? 0 : 255;
      data[offset + 1] = black ? 0 : 255;
      data[offset + 2] = black ? 0 : 255;
      data[offset + 3] = 255;
    }
  }
  return decodeQR({ width, height: width, data }, { effort: Infinity, timeLimit: Infinity });
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/catalogs", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(catalog) }));
  await page.route("**/api/bots", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(fixture.bots) }));
  await page.route("**/api/history?*", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ items: [], total: 0, limit: 25, offset: 0 }) }));
});

test("Share uses the production route DOM and generates one real demo URL", async ({ page }, testInfo) => {
  await page.goto("/?share_fixture=1");
  await page.getByRole("button", { name: "Share", exact: true }).click();
  await expect(page.getByRole("heading", { name: /^Share / })).toBeVisible();
  await expect(page.getByLabel("Public title")).toHaveValue(/Voice guide/);
  const link = await page.locator("#share-link").inputValue();
  expect(new URL(link).origin).toBe(new URL(page.url()).origin);
  expect(new URL(link).pathname).toMatch(/^\/demo\//);
  expect(decodeGeneratedQr(link)).toBe(link);
  await expect(page.locator("#share-qr svg")).toBeVisible();
  await expect(page.locator("#share-qr")).toHaveAttribute("data-link", link);
  await expect(page.getByRole("link", { name: "Open demo page" })).toHaveAttribute("href", link);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download QR" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/-demo-qr\.png$/);
  expect(await download.createReadStream()).not.toBeNull();
  await page.getByLabel("Public description").fill("A private draft change.");
  await expect(page.getByText("Unpublished changes", { exact: true })).toBeVisible();
  expect(await page.locator("#share-link").inputValue()).toBe(link);
  await page.screenshot({ path: path.join(evidenceDir, `admin-share.${testInfo.project.name}.png`), animations: "disabled" });
});

test("Share remains overflow-safe and exposes link states", async ({ page }) => {
  await page.goto("/?share_fixture=1");
  await page.getByRole("button", { name: "Share", exact: true }).click();
  const share = page.locator("#share-page");
  const overflow = await share.evaluate((element) => ({
    panel: element.scrollWidth > element.clientWidth,
    document: document.documentElement.scrollWidth > innerWidth,
  }));
  expect(overflow).toEqual({ panel: false, document: false });
  await page.getByRole("button", { name: "Disable link" }).click();
  await expect(page.getByRole("button", { name: "Enable link" })).toBeVisible();
  await expect(page.locator("#share-qr")).toHaveClass(/disabled/);
  await page.getByRole("button", { name: "Enable link" }).click();
  await expect(page.getByRole("button", { name: "Disable link" })).toBeVisible();
});
