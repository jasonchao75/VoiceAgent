import { expect, test } from "@playwright/test";
import path from "node:path";
import { readFileSync } from "node:fs";

const evidenceDir = path.resolve(
  "../openspec/changes/add-mobile-webrtc-demo-sharing/verification/checkpoint-a",
);

for (const width of [320, 375, 390, 430]) {
  test(`mobile fixture keeps the ${width}px viewport overflow-safe`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 760 });
    await page.goto("/demo.html?fixture=live");
    await expect(page.getByRole("heading", { name: "Maya · Voice guide" })).toBeVisible();
    await expect(page.locator("#caption-history .caption-turn")).toHaveCount(4);
    await expect(page.locator("#caption-history .caption-turn small", { hasText: /^Maya$/ })).toHaveCount(2);
    await expect(page.locator("#caption-history .caption-turn small", { hasText: /^You$/ })).toHaveCount(2);
    const transcriptButton = page.getByRole("button", { name: "View transcript" });
    await expect(transcriptButton).toBeVisible();
    expect((await transcriptButton.boundingBox()).height).toBeGreaterThanOrEqual(36);
    const overflow = await page.evaluate(() => ({
      document: document.documentElement.scrollWidth > innerWidth,
      phone: document.querySelector(".phone-shell").scrollWidth > document.querySelector(".phone-shell").clientWidth,
    }));
    expect(overflow).toEqual({ document: false, phone: false });
    if (width === 390) {
      await page.screenshot({
        path: path.join(evidenceDir, `mobile-live.${testInfo.project.name}.png`),
        animations: "disabled",
      });
    }
    await transcriptButton.click();
    await expect(page.locator("#transcript-sheet")).toHaveAttribute("aria-hidden", "false");
    await expect(page.locator("#messages .message")).toHaveCount(4);
    const sheetOverflow = await page.locator("#transcript-sheet").evaluate((element) => element.scrollWidth > element.clientWidth);
    expect(sheetOverflow).toBe(false);
    if (width === 390) {
      await page.screenshot({
        path: path.join(evidenceDir, `mobile-transcript.${testInfo.project.name}.png`),
        animations: "disabled",
      });
    }
  });
}

test("mobile fixture exposes reconnecting and ended states", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/demo.html?fixture=reconnecting");
  await expect(page.getByText("Network is unstable. Reconnecting…")).toBeVisible();
  await expect(page.locator("#live-orb")).toHaveAttribute("data-mode", "reconnecting");
  await page.screenshot({
    path: path.join(evidenceDir, `mobile-reconnecting.${testInfo.project.name}.png`),
    animations: "disabled",
  });
  await page.getByRole("button", { name: "End" }).click();
  await expect(page.getByRole("heading", { name: "Call ended" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Call again" })).toBeVisible();
});

for (const [state, heading] of [
  ["ready", "Maya · Voice guide"],
  ["connecting", "Connecting your call"],
  ["error", "Couldn’t connect"],
  ["ended", "Call ended"],
]) {
  test(`mobile fixture exposes ${state} state`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/demo.html?fixture=${state}`);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  });
}

test("microphone denial does not allocate a public session", async ({ page, context }) => {
  let sessionRequests = 0;
  const events = [];
  await context.clearPermissions();
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
      configurable: true,
      value: async () => { throw new DOMException("Permission denied", "NotAllowedError"); },
    });
  });
  await page.route("**/api/public/demos/demo.html", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ public_id: "demo.html", title: "Permission test", description: "", active: true, available: true }),
  }));
  await page.route("**/api/public/demos/demo.html/sessions", (route) => {
    sessionRequests += 1;
    return route.fulfill({ status: 500, body: "must not be called" });
  });
  await page.route("**/api/public/demos/demo.html/events", async (route) => {
    events.push(route.request().postDataJSON());
    await route.fulfill({ status: 204 });
  });
  await page.goto("/demo.html");
  await page.getByRole("button", { name: "Start voice call" }).click();
  await expect(page.getByRole("heading", { name: "Couldn’t connect" })).toBeVisible();
  await expect(page.getByText(/browser settings, allow Microphone access/)).toBeVisible();
  expect(sessionRequests).toBe(0);
  await expect.poll(() => events.some((item) => (
    item.event === "mobile_mic_permission" && item.result === "denied"
  ))).toBe(true);
  expect(events.filter((item) => item.event === "mobile_demo_view").length).toBeGreaterThanOrEqual(1);
  expect(events.filter((item) => item.event === "mobile_call_start_click")).toHaveLength(1);
  expect(events.filter((item) => item.event === "mobile_mic_permission")).toHaveLength(1);
});

test("mobile transcript consumes spoken TTS text including the opening message", () => {
  const source = readFileSync(path.resolve("src/mobile-demo.js"), "utf8");
  expect(source).toContain("onBotTtsText:");
  expect(source).not.toContain("onBotLlmText:");
  expect(source).toContain('reportSessionEvent("mobile_webrtc_connected"');
  expect(source).toContain("candidate_type: candidateType");
});

test("all unavailable metadata states use one safe visitor message", async ({ page }) => {
  await page.route("**/api/public/demos/demo.html", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ public_id: "demo.html", title: "Hidden", description: "", active: false, available: false }),
  }));
  await page.goto("/demo.html");
  await expect(page.getByRole("heading", { name: "Demo unavailable" })).toBeVisible();
  await expect(page.getByText("This demo is no longer available.", { exact: true })).toBeVisible();
  await expect(page.locator('[data-screen="error"]')).toHaveAttribute("aria-hidden", "false");
  await expect(page.locator('[data-screen="error"]')).toHaveJSProperty("inert", false);
  await expect(page.locator('[data-screen="ready"]')).toHaveAttribute("aria-hidden", "true");
  await expect(page.locator('[data-screen="ready"]')).toHaveJSProperty("inert", true);
  await expect(page.getByRole("button", { name: "Start voice call" })).toHaveCount(0);
});
