import { expect, test } from "@playwright/test";
import path from "node:path";

const config = {
  name: "Checkpoint B Maya",
  asr_provider: "deepgram",
  asr_model: "flux-general-en",
  tts_provider: "deepgram_flux",
  tts_voice: "flux-alexis-en",
  llm_provider: "openai",
  llm_base_url: "https://api.openai.com/v1",
  llm_model: "gpt-4.1-mini",
  system_prompt: "Help the caller.",
  opening_script: "Hello!",
  save_asr_key: true,
  save_tts_key: true,
  save_llm_key: true,
  asr_api_key: "asr-browser-test-key-0001",
  tts_api_key: "tts-browser-test-key-0001",
  llm_api_key: "llm-browser-test-key-0001",
};

test("formal Share route publishes and controls a real persisted demo", async ({ page, request }, testInfo) => {
  const origin = process.env.VOICE_AGENT_UI_URL || "http://127.0.0.1:8000";
  const created = await request.post("/api/bots", { data: config, headers: { Origin: origin } });
  expect(created.ok()).toBeTruthy();
  const bot = await created.json();
  try {
    await page.goto("/");
    await page.getByRole("button", { name: "Share", exact: true }).click();
    await expect(page.getByRole("heading", { name: `Share ${config.name}` })).toBeVisible();
    await expect(page.getByText("Not published")).toBeVisible();
    await page.getByLabel("Public title").fill("Maya · Real API");
    await page.getByLabel("Public description").fill("Checkpoint B publication path.");
    await page.getByRole("button", { name: "Publish demo" }).click();
    await expect(page.getByText("Published", { exact: true })).toBeVisible();
    const publicLink = await page.locator("#share-link").inputValue();
    expect(new URL(publicLink).origin).toBe(origin);
    expect(new URL(publicLink).pathname).toMatch(/^\/demo\//);
    await expect(page.locator("#share-qr svg")).toBeVisible();

    const metadata = await request.get(new URL(publicLink).pathname.replace("/demo/", "/api/public/demos/"));
    expect(metadata.ok()).toBeTruthy();
    expect((await metadata.json()).title).toBe("Maya · Real API");
    await page.getByLabel("Public title").fill("Maya · Draft only");
    await expect(page.getByText("Unpublished changes", { exact: true })).toBeVisible();
    expect((await (await request.get(new URL(publicLink).pathname.replace("/demo/", "/api/public/demos/"))).json()).title).toBe("Maya · Real API");

    await page.getByRole("button", { name: "Disable link" }).click();
    await expect(page.getByRole("button", { name: "Enable link" })).toBeVisible();
    await page.getByRole("button", { name: "Enable link" }).click();
    await expect(page.getByRole("button", { name: "Disable link" })).toBeVisible();
    await page.screenshot({
      path: path.resolve(`../openspec/changes/add-mobile-webrtc-demo-sharing/verification/checkpoint-b/real-admin.${testInfo.project.name}.png`),
      animations: "disabled",
    });
    await page.goto(new URL(publicLink).pathname);
    await expect(page.getByRole("heading", { name: "Maya · Real API" })).toBeVisible();
    await page.screenshot({
      path: path.resolve(`../openspec/changes/add-mobile-webrtc-demo-sharing/verification/checkpoint-b/real-mobile.${testInfo.project.name}.png`),
      animations: "disabled",
    });
  } finally {
    await request.delete(`/api/bots/${bot.id}`, { headers: { Origin: origin } });
  }
});
