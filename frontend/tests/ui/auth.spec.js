import { expect, test } from "@playwright/test";

test("product login replaces native auth and keeps call metrics separate", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login\?/);
  await expect(page.getByText("VoiceAgent Demo", { exact: true }).first()).toBeVisible();
  await page.getByLabel("Username").fill("demo-user");
  await page.getByLabel("Password").fill("test-password-long-enough");
  await page.getByRole("button", { name: "Continue to VoiceAgent Demo" }).click();

  await expect(page.getByRole("button", { name: "Bot settings", exact: true })).toBeVisible();
  const telemetry = await page.evaluate(async () => {
    const response = await fetch("/api/sessions/not-active/metrics", {
      headers: { Authorization: "Bearer invalid-session-token" },
    });
    return { status: response.status, challenge: response.headers.get("www-authenticate") };
  });
  expect(telemetry).toEqual({ status: 401, challenge: null });
  await expect(page).not.toHaveURL(/\/login/);

  await page.getByRole("button", { name: "User menu" }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("login remains usable without horizontal overflow", async ({ page }) => {
  await page.goto("/login?expired=1&next=%2F");
  await expect(page.getByText(/session expired/i)).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  expect(overflow).toBe(false);
});
