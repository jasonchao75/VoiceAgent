import { expect, test } from "@playwright/test";

async function openEvaluation(page, pageName) {
  await page.route("**/api/evaluation/bootstrap", (route) => route.abort());
  const suffix = pageName ? `?page=${pageName}&gate2=1` : "?gate2=1";
  await page.goto(`/evaluation.html${suffix}`);
  await expect(page.locator("#product-evaluation")).toHaveClass(/active/);
}

test("exposes the Evaluation product from the existing VoiceAgent shell", async ({ page }) => {
  await page.goto("/");
  const voiceLink = page.getByRole("link", { name: "VoiceAgent Demo home", exact: true }).first();
  const evaluationLink = page.getByRole("link", { name: "ASR Evaluation", exact: true });
  await expect(voiceLink).toHaveAttribute("aria-current", "page");
  await expect(evaluationLink).not.toHaveAttribute("aria-current");
  await expect(evaluationLink).toHaveAttribute(
    "href",
    "/evaluation.html",
  );
  await expect(evaluationLink.locator("svg path")).toHaveAttribute(
    "d",
    "M4 19V9m5 10V5m5 14v-7m5 7V3",
  );
  const states = await page.locator(".product-rail a > span").evaluateAll((items) =>
    items.map((item) => {
      const style = getComputedStyle(item);
      return {
        backgroundColor: style.backgroundColor,
        borderColor: style.borderColor,
      };
    }),
  );
  expect(states[0]).not.toEqual(states[1]);
  expect(states[0].borderColor).toBe("rgb(49, 88, 67)");
  expect(states[1].borderColor).toBe("rgba(0, 0, 0, 0)");

  await openEvaluation(page);
  const evaluationButton = page.getByRole("button", { name: "Evaluation", exact: true });
  await expect(evaluationButton).toHaveAttribute("aria-current", "page");
  await expect(evaluationButton).toHaveCSS("border-color", "rgb(49, 88, 67)");
});

test("matches the frozen batch overview and regression fixture", async ({ page }) => {
  await openEvaluation(page);
  await expect(page.getByRole("heading", { name: "Evaluation batches", exact: true })).toBeVisible();
  await expect(page.getByText("5.4%", { exact: true })).toBeVisible();
  await expect(page.getByText("24 / 441 valid user sentences", { exact: true })).toBeVisible();
  await expect(page.getByText("30 / 441", { exact: true })).toHaveCount(0);
  await expect(page.locator("#page-batches tbody tr")).toHaveCount(6);
});

test("keeps the production transcript and current proposal adjacent for review", async ({ page }) => {
  await openEvaluation(page, "review");
  await expect(page.getByRole("heading", { name: "Manual audio review", exact: true })).toBeVisible();

  const comparison = page.locator("#page-review .review-comparison");
  await expect(comparison.getByText("Production transcript", { exact: true })).toBeVisible();
  await expect(comparison.getByText("Current proposed label", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Good · Production transcript is correct" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Bad · Save corrected label" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Unclear audio", exact: true })).toBeVisible();

  const context = await page.locator("#page-review .evidence-grid .evidence.span2").innerText();
  expect(context).not.toMatch(/[\u4e00-\u9fff]/);

  await page.getByRole("button", { name: "Soniox" }).click();
  await expect(page.getByRole("button", { name: "Bad · Save corrected label" })).toBeEnabled();
  await expect(comparison.getByText("two two one", { exact: true })).toBeVisible();
});

test("uses per-conversation Excel uploads and keeps the dialog overflow-safe", async ({ page }) => {
  await openEvaluation(page);
  await page.locator("#new-run").click();
  const dialog = page.locator("#new-run-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/56 per-conversation Excel files/)).toBeVisible();
  await expect(dialog.getByText(/single combined workbook/i)).toHaveCount(0);
  await expect(dialog.getByRole("heading", { name: "Resources for this batch" })).toBeVisible();
  await expect(dialog.locator("#batch-resources-card .batch-asr-option")).toHaveCount(3);
  await expect(dialog.locator("#batch-resources-card .batch-llm-card")).toHaveCount(2);
  await expect(dialog.getByText("Candidate screening LLM", { exact: true })).toBeVisible();
  await expect(dialog.getByText("Evidence decision LLM", { exact: true })).toBeVisible();
  await expect(dialog.getByText("Cost protection", { exact: true })).toBeVisible();

  const overflow = await dialog.evaluate((element) => ({
    horizontal: element.scrollWidth > element.clientWidth,
    viewport: document.documentElement.scrollWidth > window.innerWidth,
  }));
  expect(overflow).toEqual({ horizontal: false, viewport: false });
});

test("matches the frozen report structure and keeps evaluation ASRs out of production analysis", async ({
  page,
}) => {
  await openEvaluation(page, "report");
  await expect(page.getByText("Evaluation funnel", { exact: true })).toBeVisible();
  await expect(page.getByText("Case tag distribution", { exact: true })).toBeVisible();
  await expect(page.getByText("Proposed tag details", { exact: true })).toBeVisible();

  const productionAnalysis = page.locator("#production-asr-analysis");
  await expect(productionAnalysis.getByText("Production ASR recognition analysis", { exact: true })).toBeVisible();
  await expect(productionAnalysis.getByRole("columnheader", { name: "Production ASR result" })).toBeVisible();
  await expect(productionAnalysis.getByRole("columnheader", { name: "Soniox" })).toHaveCount(0);
  await expect(productionAnalysis.getByRole("columnheader", { name: /Speechmatics/ })).toHaveCount(0);
  await expect(productionAnalysis.getByRole("columnheader", { name: "ElevenLabs" })).toHaveCount(0);

  const caseDetails = page.locator("#batch-case-details");
  await expect(caseDetails.getByText("All suspicious cases in this batch", { exact: true })).toBeVisible();
  await expect(caseDetails.locator("tbody tr")).toHaveCount(30);
  await expect(caseDetails.getByRole("columnheader", { name: "Audio" })).toBeVisible();
  await expect(page.getByText("Benchmark classification actions", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Next model-selection evaluation plan", { exact: true })).toHaveCount(0);
});

test("creates an AI-proposed scenario tag with its description", async ({ page }) => {
  await openEvaluation(page, "report");
  const proposal = page.locator('#proposed-tag-details tr[data-proposed-tag="overlap"]').first();
  await expect(proposal.getByText("Overlapping speech / agent leakage", { exact: true })).toBeVisible();
  await expect(proposal.locator(".tag-ai-description")).toHaveText(
    "Use when robot or agent speech overlaps the customer channel, is assigned to a customer event, or contaminates the customer transcript.",
  );

  const createButton = proposal.locator(".create-tag-group");
  await expect(createButton).toHaveAccessibleName("Create name + description & move 3");
  await createButton.click();
  await expect(createButton).toBeDisabled();
  await expect(createButton).toHaveText("Created with description · moved");
  const movedGroups = await page
    .locator('#proposed-tag-details tr[data-proposed-tag="overlap"] .case-group-select')
    .evaluateAll((selects) => selects.map((select) => select.value));
  expect(movedGroups).toEqual(["overlap", "overlap", "overlap"]);

  await page.locator('[data-page="tags"]').click();
  const createdTag = page.locator('#page-tags [data-generated-tag="overlap"]');
  await expect(createdTag.getByRole("heading", { name: "Overlapping speech / agent leakage" })).toBeVisible();
  await expect(createdTag.locator("p")).toHaveText(
    "Use when robot or agent speech overlaps the customer channel, is assigned to a customer event, or contaminates the customer transcript.",
  );
  await expect(createdTag).toContainText("3 samples · created from report suggestion");

  await page.getByRole("tab", { name: "中文" }).click();
  await expect(createdTag.getByRole("heading", { name: "重叠说话 / 机器人串音" })).toBeVisible();
  await expect(createdTag.locator("p")).toHaveText(
    "机器人或坐席语音与用户声道重叠、被错误归到用户事件，或混入用户转写时使用。",
  );
  await expect(page.locator("#page-tags .edit-tag")).toHaveCount(6);
  await createdTag.getByRole("button", { name: "编辑 重叠说话 / 机器人串音" }).click();
  await expect(page.locator("#tag-dialog-title")).toHaveText("编辑场景标签");
  await page.locator("#tag-name-zh").fill("重叠说话 / 坐席串音");
  await page.locator("#tag-description-zh").fill("用于用户声道混入坐席语音的样本。");
  await page.locator("#save-tag").click();
  await expect(createdTag.getByRole("heading", { name: "重叠说话 / 坐席串音" })).toBeVisible();
  await expect(createdTag.locator("p")).toHaveText("用于用户声道混入坐席语音的样本。");

  await createdTag.getByRole("button", { name: "删除 重叠说话 / 坐席串音" }).click();
  await expect(page.locator("#delete-tag-message")).toContainText("已被 3 个样本引用");
  await page.locator("#confirm-delete-tag").click();
  await expect(createdTag).toHaveCount(0);
  await expect(page.locator("#toast")).toContainText("历史快照仍保留");
});

test("expands report audio into pause, resume, and seek controls", async ({ page }) => {
  await openEvaluation(page, "report");
  const players = page.locator("#proposed-tag-details .inline-audio-player");
  const first = players.nth(0);
  const second = players.nth(1);
  const firstToggle = first.locator(".inline-audio-toggle");

  await expect(firstToggle).toHaveAttribute("aria-label", "Play audio clip");
  await firstToggle.click();
  await expect(first).toHaveClass(/expanded/);
  await expect(firstToggle).toHaveAttribute("aria-label", "Pause audio clip");
  await expect(first.locator("input[type=range]")).toBeVisible();
  await expect(first.locator(".inline-audio-time")).toContainText("/");

  await firstToggle.click();
  await expect(firstToggle).toHaveAttribute("aria-label", "Resume audio clip");
  await firstToggle.click();
  await expect(firstToggle).toHaveAttribute("aria-label", "Pause audio clip");

  await second.locator(".inline-audio-toggle").click();
  await expect(first).not.toHaveClass(/expanded/);
  await expect(firstToggle).toHaveAttribute("aria-label", "Play audio clip");
  await expect(second.locator(".inline-audio-toggle")).toHaveAttribute("aria-label", "Pause audio clip");
});

test("filters report case details by scenario tag and updates the count", async ({ page }) => {
  await openEvaluation(page, "report");
  const details = page.locator("#batch-case-details");
  const filter = details.getByRole("combobox", { name: "Scenario tag filter" });
  await expect(filter.locator("option")).toHaveCount(6);

  const firstPlayer = details
    .locator('tr:has-text("1030000000082501") .inline-audio-player')
    .first();
  await firstPlayer.locator(".inline-audio-toggle").click();
  await expect(firstPlayer).toHaveClass(/expanded/);

  await filter.selectOption("numbers");
  await expect(details.locator("tbody tr:visible")).toHaveCount(5);
  await expect(details.getByText("5 / 30 cases", { exact: true })).toBeVisible();
  await expect(details.getByText("Showing 5 of 30 cases for the selected scenario tag.", { exact: true })).toBeVisible();
  await expect(firstPlayer).not.toHaveClass(/expanded/);

  await filter.selectOption("all");
  await expect(details.locator("tbody tr:visible")).toHaveCount(30);
  await expect(details.getByText("30 total", { exact: true })).toBeVisible();
});

test("keeps the full two-pass prompts visible without confidence output", async ({ page }) => {
  await openEvaluation(page, "settings");
  await page.getByRole("button", { name: "Two-pass evaluation prompts", exact: true }).click();
  const prompts = page.locator("#evaluation-prompts .prompt-editor");
  await expect(prompts).toHaveCount(2);
  await expect(prompts.nth(0)).toHaveAttribute("readonly", "");
  await expect(prompts.nth(1)).toHaveAttribute("readonly", "");
  await expect(prompts.nth(0)).toHaveValue(/candidate\|pass\|data_issue/);
  await expect(prompts.nth(0)).toHaveValue(/\{\{conversation_history\}\}/);
  await expect(prompts.nth(0)).toHaveValue(/\{\{reference_dictionaries\}\}/);
  await expect(prompts.nth(1)).toHaveValue(/\{\{screening_strategy\}\}/);
  await expect(prompts.nth(0)).not.toHaveValue(/branch_dictionary/);
  await expect(prompts.nth(1)).not.toHaveValue(/branch_dictionary/);
  await expect(prompts.nth(1)).toHaveValue(/Good Case\|Bad Case\|Needs manual audio review/);
  await expect(prompts.nth(1)).toHaveValue(/description_en/);
  await expect(prompts.nth(1)).toHaveValue(/description_zh/);
  await expect(prompts.nth(0)).not.toHaveValue(/"confidence"\s*:/i);
  await expect(prompts.nth(1)).not.toHaveValue(/"confidence"\s*:/i);

  await expect(page.getByRole("button", { name: "Save as new version", exact: true }).first()).toBeHidden();
  await page.getByRole("button", { name: "Edit fixed template", exact: true }).first().click();
  await expect(prompts.nth(0)).not.toHaveAttribute("readonly", "");
  await page.getByRole("button", { name: "Save as new version", exact: true }).first().click();
  await expect(page.locator("#evaluation-prompts .card").first().getByText("Template v4", { exact: true })).toBeVisible();
  await expect(prompts.nth(0)).toHaveAttribute("readonly", "");
});

test("previews both assembled LLM requests from the context", async ({ page }) => {
  await openEvaluation(page, "settings");
  await page.getByRole("button", { name: "Preview requests", exact: true }).first().click();
  const preview = page.locator("#request-preview-dialog");
  await expect(preview).toBeVisible();
  await expect(preview.getByText("Prompt template · with variable slots", { exact: true })).toBeVisible();
  await expect(preview.getByText("Final rendered Prompt", { exact: true })).toBeVisible();
  await expect(preview.locator("#preview-template-message")).toContainText("{{conversation_history}}");
  await expect(preview.locator("#preview-rendered-message")).toContainText("利雅得银行分行转接");
  await expect(preview.locator("#preview-rendered-message")).toContainText("فرع العليا");
  await expect(preview.locator("#preview-rendered-message")).not.toContainText("{{conversation_history}}");
  await expect(preview.locator("#preview-rendered-message")).not.toContainText('"asr_results"');
  await preview.getByRole("button", { name: /Background and objective/ }).click();
  await expect(preview.locator("#preview-template-message mark")).toContainText("{{evaluation_context}}");
  await expect(preview.locator("#preview-rendered-message mark")).toContainText('"business_background_and_objective"');
  await preview.getByRole("button", { name: /Linked dictionaries/ }).click();
  await expect(preview.locator("#preview-template-message mark")).toContainText("{{reference_dictionaries}}");
  await expect(preview.locator("#preview-rendered-message mark")).toContainText('"entries"');
  await preview.getByRole("button", { name: "Pass 2 · Evidence decision", exact: true }).click();
  await expect(preview.locator("#preview-template-message")).toContainText("{{request_group_id}}");
  await expect(preview.locator("#preview-template-message")).toContainText("{{candidate_case}}");
  await expect(preview.locator("#preview-template-message")).toContainText('"results"');
  await expect(preview.locator("#preview-template-message")).toContainText('"positioning_quality"');
  await expect(preview.locator("#request-field-map-grid")).toContainText("request_group_id");
  await expect(preview.locator("#preview-rendered-message")).toContainText('"issue_id"');
  await expect(preview.locator("#preview-rendered-message")).toContainText('"provider": "Soniox"');
  await expect(preview).toHaveJSProperty("scrollWidth", await preview.evaluate((element) => element.clientWidth));
  await preview.getByRole("button", { name: "Close", exact: true }).click();

  await page.getByRole("button", { name: "Edit new version", exact: true }).first().click();
  const contextDialog = page.locator("#context-dialog");
  await contextDialog.getByLabel("Business background and objective").fill("Draft objective shown before saving.");
  await contextDialog.getByRole("button", { name: "Preview both LLM requests", exact: true }).click();
  await expect(preview.locator("#preview-rendered-message")).toContainText("Draft objective shown before saving.");
});

test("opens the prepared context and saves an immutable new version", async ({ page }) => {
  await openEvaluation(page, "settings");
  await page.getByRole("button", { name: "Edit new version", exact: true }).first().click();
  const dialog = page.locator("#context-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Context name")).toHaveValue("利雅得银行分行转接");
  await expect(dialog.getByLabel("Standard business flow")).toHaveValue(/语言选择.*三位分行代码.*确认转接/);
  await expect(dialog.getByLabel("Known ASR risks")).toHaveValue(/阿英混说.*三位数字/);
  await expect(dialog.getByText("{{conversation_history}}", { exact: true })).toBeVisible();
  await expect(dialog.getByText("{{reference_dictionaries}}", { exact: true })).toBeVisible();
  await expect(dialog.locator('.context-dictionary-ref[value="riyadbank_branches"]')).toBeChecked();
  await expect(dialog).toHaveJSProperty("scrollWidth", await dialog.evaluate((element) => element.clientWidth));

  await dialog.getByRole("button", { name: "Save as new version", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('#context-table-body tr[data-context-key="riyadbank"] .context-version')).toHaveText("v4");
});

test("maintains versioned generic reference dictionaries", async ({ page }) => {
  await openEvaluation(page, "settings");
  await page.getByRole("button", { name: "Reference dictionaries", exact: true }).click();
  const pane = page.locator("#reference-dictionaries");
  await expect(pane.getByText("RiyadBank branch entities", { exact: true })).toBeVisible();
  await expect(pane.getByText("riyadbank_branches", { exact: true })).toBeVisible();
  await expect(pane.getByText("{{reference_dictionaries}}", { exact: false })).toBeVisible();

  await pane.getByRole("button", { name: "Edit new version", exact: true }).click();
  const dialog = page.locator("#dictionary-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Stable key")).toHaveValue("riyadbank_branches");
  await expect(dialog.getByLabel("Dictionary entries · CSV or JSON")).toHaveValue(/canonical_value,alias,code,locale,metadata/);
  await dialog.getByRole("button", { name: "Save as new version", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(pane.locator(".dictionary-version")).toHaveText("v2");

  await pane.getByRole("button", { name: "+ New dictionary", exact: true }).click();
  await dialog.getByLabel("Dictionary name").fill("Customer tier aliases");
  await dialog.getByLabel("Stable key").fill("customer_tiers");
  await dialog.getByLabel("Purpose and matching guidance").fill("Known customer-tier names and aliases.");
  await dialog.getByLabel("Dictionary entries · CSV or JSON").fill("canonical_value,alias,code,locale,metadata\nDiamond,diamond,,en,{}");
  await dialog.getByRole("button", { name: "Save as new version", exact: true }).click();
  await expect(pane.getByText("customer_tiers", { exact: true })).toBeVisible();
});

test("tests ASR connections in place and gives explicit LLM diagnostic feedback", async ({ page }) => {
  let geminiRequest;
  await page.route("**/api/bots", async (route) => {
    await route.fulfill({ contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/catalogs", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        llm_providers: {
          providers: [
            { id: "google_gemini", recommended_models: ["gemini-2.5-flash-lite"] },
            { id: "openai", recommended_models: ["gpt-5-mini"] },
          ],
        },
      }),
    });
  });
  await page.route("**/api/evaluation/connections", async (route) => {
    await route.fulfill({ contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/evaluation/connections/*/test-and-save", async (route) => {
    const provider = new URL(route.request().url()).pathname.split("/").at(-2);
    const request = route.request().postDataJSON();
    if (provider === "gpt" && !request.api_key) {
      await route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Enter an API key before testing" }),
      });
      return;
    }
    if (provider === "gemini") geminiRequest = request;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        diagnostic_id: "diag-connection-card",
        success: true,
        category: "ok",
        summary: "Authenticated provider probe passed.",
        suggestion: "Ready.",
        provider,
        base_url_host: "generativelanguage.googleapis.com",
        model: "gemini-2.5-flash-lite",
        first_token_ms: 88.6,
        total_ms: 190.2,
        reasoning_status: "not_requested",
        connection: {
          provider,
          kind: ["soniox", "speechmatics", "elevenlabs"].includes(provider) ? "asr" : "llm",
          base_url:
            provider === "gemini"
              ? "https://generativelanguage.googleapis.com"
              : `https://api.${provider}.example`,
          status: "verified",
          diagnostic_id: "diag-connection-card",
          verified_at: "2026-09-16T12:00:00Z",
          updated_at: "2026-09-16T12:00:00Z",
          has_saved_key: true,
        },
      }),
    });
  });

  await openEvaluation(page, "connections");
  const asrCards = page.locator(".connection-card[data-asr-provider]");
  await expect(asrCards).toHaveCount(3);
  for (const card of await asrCards.all()) {
    await card.locator(".connection-key").fill("test-key-12345");
    await card.getByRole("button", { name: "Test & save" }).click();
    await expect(card.locator(".connection-status")).toHaveText("Saved · verified");
    await expect(card.locator(".connection-test-result")).toContainText("encrypted and saved");
  }

  const geminiCard = page.locator('.connection-card[data-model-provider="Gemini"]');
  await geminiCard.locator(".connection-key").fill("test-key-12345");
  await geminiCard.getByRole("button", { name: "Test & save" }).click();
  expect(geminiRequest).toEqual({
    api_key: "test-key-12345",
    base_url: "https://generativelanguage.googleapis.com",
    model_id: "gemini-2.5-flash-lite",
  });
  await expect(geminiCard.locator(".connection-status")).toHaveText("Saved · verified");
  await expect(geminiCard.locator(".connection-test-result")).toContainText("diag-connection-card");

  const openaiCard = page.locator('.connection-card[data-model-provider="GPT"]');
  await openaiCard.getByRole("button", { name: "Test & save" }).click();
  await expect(openaiCard.locator(".connection-status")).toHaveText("Failed");
  await expect(openaiCard.locator(".connection-test-result")).toContainText("Enter an API key");
  await expect(openaiCard.locator(".connection-key")).toBeFocused();
});

test("reloads encrypted Resource Connections without returning a key", async ({ page }) => {
  await page.route("**/api/evaluation/connections", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          provider: "gemini",
          kind: "llm",
          base_url: "https://generativelanguage.googleapis.com",
          status: "verified",
          diagnostic_id: "diag-persisted",
          last_model_id: "gemini-2.5-flash-lite",
          verified_at: "2026-09-16T12:00:00Z",
          updated_at: "2026-09-16T12:00:00Z",
          has_saved_key: true,
        },
      ]),
    });
  });
  await page.route("**/api/bots", async (route) => {
    await route.fulfill({ contentType: "application/json", body: "[]" });
  });

  await openEvaluation(page, "connections");
  const card = page.locator('.connection-card[data-model-provider="Gemini"]');
  await expect(card.locator(".connection-status")).toHaveText("Saved · verified");
  await expect(card.locator(".connection-key")).toHaveValue("");
  await expect(card.locator(".connection-key")).toHaveAttribute(
    "placeholder",
    "Saved securely · enter only to replace",
  );

  await page.reload();
  await expect(card.locator(".connection-status")).toHaveText("Saved · verified");
  await expect(card.locator(".connection-key")).toHaveValue("");
});

test("reuses the server catalog and live LLM diagnostic API", async ({ page }) => {
  let diagnosticRequest;
  await page.route("**/api/evaluation/connections", async (route) => {
    await route.fulfill({ contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/bots", async (route) => {
    await route.fulfill({ contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/catalogs", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        llm_providers: {
          providers: [
            {
              id: "google_gemini",
              recommended_models: ["gemini-2.5-flash-lite", "gemini-2.5-flash"],
            },
            {
              id: "openai",
              recommended_models: ["gpt-4.1-mini", "gpt-5-mini"],
            },
          ],
        },
      }),
    });
  });
  await page.route("**/api/llm/diagnostics", async (route) => {
    diagnosticRequest = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        diagnostic_id: "diag-live-001",
        success: true,
        category: "ok",
        summary: "The model returned a streamed text response.",
        suggestion: "Ready.",
        provider: "google_gemini",
        base_url_host: "generativelanguage.googleapis.com",
        model: "gemini-2.5-flash",
        first_token_ms: 128.4,
        total_ms: 284.2,
        reasoning_status: "not_requested",
      }),
    });
  });

  await openEvaluation(page, "connections");
  const geminiConnection = page.locator('.connection-card[data-model-provider="Gemini"]');
  await expect(geminiConnection.locator(".connection-status")).toHaveText("Not tested");
  await geminiConnection.locator(".connection-key").fill("test-key-12345");
  await page.locator('[data-page="costs"]').click();

  const firstPass = page.locator("#page-costs .pricing-table tbody tr").first();
  await firstPass.locator(".model-name-select").selectOption("gemini-2.5-flash");
  await firstPass.locator(".validate-model").click();

  expect(diagnosticRequest).toEqual({
    llm_provider: "google_gemini",
    llm_base_url: "https://generativelanguage.googleapis.com",
    llm_model: "gemini-2.5-flash",
    llm_api_key: "test-key-12345",
    reasoning_mode: "provider_default",
    register_for_evaluation_catalog: false,
  });
  await expect(firstPass.locator(".model-validation")).toContainText(
    "Live verification passed · first token 128.4 ms · diag-live-001",
  );
  await expect(firstPass.locator(".price-input").first()).toHaveValue("$0.10");
});

test("recognizes Gemini 3.8 Flash and reuses a saved provider connection", async ({ page }) => {
  let diagnosticRequest;
  await page.route("**/api/evaluation/connections", async (route) => {
    await route.fulfill({ contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/catalogs", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        llm_providers: {
          providers: [
            {
              id: "google_gemini",
              recommended_models: ["gemini-2.5-flash", "gemini-3.8-flash"],
            },
            { id: "openai", recommended_models: ["gpt-5-mini"] },
          ],
        },
      }),
    });
  });
  await page.route("**/api/bots", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "bot-gemini-38",
          name: "Gemini 3.8 Bot",
          llm_provider: "google_gemini",
          llm_base_url: "https://generativelanguage.googleapis.com",
          llm_model: "gemini-2.5-flash-lite",
          has_saved_keys: true,
        },
      ]),
    });
  });
  await page.route("**/api/llm/diagnostics", async (route) => {
    diagnosticRequest = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        diagnostic_id: "diag-gemini-38",
        success: true,
        category: "ok",
        summary: "The model returned a streamed text response.",
        suggestion: "Ready.",
        provider: "google_gemini",
        base_url_host: "generativelanguage.googleapis.com",
        model: "gemini-3.8-flash",
        first_token_ms: 96.2,
        total_ms: 211.7,
        reasoning_status: "unverified",
      }),
    });
  });

  await openEvaluation(page, "costs");
  const firstPass = page.locator("#page-costs .pricing-table tbody tr").first();
  await expect(firstPass.locator(".model-provider")).toContainText("Saved connection");
  await expect(firstPass.locator('.model-name-select option[value="gemini-3.8-flash"]')).toHaveText(
    "Gemini/gemini-3.8-flash · Saved connection",
  );
  await firstPass.locator(".model-name-select").selectOption("__custom__");
  await firstPass.locator(".custom-model").fill("Gemini/gemini-3.8-flash");
  await firstPass.locator(".validate-model").click();

  expect(diagnosticRequest).toEqual({
    bot_id: "bot-gemini-38",
    llm_model: "gemini-3.8-flash",
    reasoning_mode: "provider_default",
    register_for_evaluation_catalog: true,
  });
  await expect(firstPass.locator(".model-validation")).toContainText(
    "Live verification passed · first token 96.2 ms · diag-gemini-38",
  );
});

test("adds a successfully verified custom model to both new-batch selectors", async ({ page }) => {
  let diagnosticRequest;
  await page.route("**/api/evaluation/llm-models", async (route) => {
    await route.fulfill({ contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/bots", async (route) => {
    await route.fulfill({ contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/catalogs", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        llm_providers: {
          providers: [
            { id: "google_gemini", recommended_models: ["gemini-2.5-flash"] },
            { id: "openai", recommended_models: ["gpt-5-mini"] },
          ],
        },
      }),
    });
  });
  await page.route("**/api/llm/diagnostics", async (route) => {
    diagnosticRequest = route.request().postDataJSON();
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        diagnostic_id: "diag-deepseek-custom",
        success: true,
        category: "ok",
        summary: "Connected.",
        suggestion: "Ready.",
        provider: "custom",
        base_url_host: "api.deepseek.com",
        model: "deepseek-custom-2026",
        first_token_ms: 42,
        total_ms: 90,
        reasoning_status: "unverified",
        evaluation_catalog_registered: true,
        evaluation_provider: "DeepSeek",
      }),
    });
  });

  await openEvaluation(page, "connections");
  await page
    .locator('.connection-card[data-model-provider="DeepSeek"] .connection-key')
    .fill("test-key-12345");
  await page.locator('[data-page="costs"]').click();
  const firstPass = page.locator("#page-costs .pricing-table tbody tr").first();
  await firstPass.locator(".model-provider").selectOption("DeepSeek");
  await firstPass.locator(".model-name-select").selectOption("__custom__");
  await firstPass.locator(".custom-model").fill("DeepSeek/deepseek-custom-2026");
  await firstPass.locator(".validate-model").click();

  expect(diagnosticRequest).toEqual({
    llm_provider: "custom",
    llm_base_url: "https://api.deepseek.com",
    llm_model: "deepseek-custom-2026",
    llm_api_key: "test-key-12345",
    reasoning_mode: "provider_default",
    register_for_evaluation_catalog: true,
  });
  await expect(firstPass.locator(".model-validation")).toContainText(
    "added to evaluation model catalog",
  );

  await page.locator('[data-page="batches"]').click();
  await page.locator("#new-run").click();
  const cards = page.locator("#new-run-dialog .batch-llm-card");
  for (const card of await cards.all()) {
    await card.locator(".batch-llm-provider").selectOption("DeepSeek");
    await expect(
      card.locator(".batch-llm-model option").filter({ hasText: "deepseek-custom-2026" }),
    ).toHaveCount(1);
  }
});

test("supports filtered and selected Benchmark downloads with traceable sample detail", async ({ page }) => {
  await openEvaluation(page, "library");
  await expect(page.locator("#benchmark-page-summary")).toHaveText("Page 1 · 20 per page · 3 total");
  await expect(page.locator("#download-benchmarks")).toBeDisabled();
  await expect(page.locator("#download-filtered-benchmarks")).toHaveText("Download all filtered (3)");
  await page.locator("#benchmark-case-type-filter").selectOption("good");
  await expect(page.locator("#page-library tbody tr:visible")).toHaveCount(1);
  await page.locator("#benchmark-case-type-filter").selectOption("all");
  await page.locator("#select-all-benchmarks").check();
  await expect(page.locator("#download-benchmarks")).toHaveText("Download selected (3)");
  await page.locator("#benchmark-language-filter").selectOption("en");
  await expect(page.locator("#page-library tbody tr:visible")).toHaveCount(2);
  await expect(page.locator("#benchmark-page-summary")).toHaveText("Page 1 · 20 per page · 2 total");
  await expect(page.locator("#download-filtered-benchmarks")).toHaveText("Download all filtered (2)");
  await page.locator("#download-filtered-benchmarks").click();
  await expect(page.locator("#toast")).toHaveText("Preparing all 2 filtered samples across every page.");
  await page.locator("#benchmark-language-filter").selectOption("all");
  await page.locator(".sample-detail").first().click();
  await expect(page.locator("#sample-dialog")).toBeVisible();
  await expect(page.locator("#sample-dialog").getByText("BM-AR-00026", { exact: true })).toBeVisible();
  await page.locator("#sample-dialog").getByRole("button", { name: "Edit sample" }).click();
  await expect(page.locator("#sample-dialog .benchmark-edit-form")).toBeVisible();
  await expect(page.locator("#sample-dialog").getByRole("button", { name: "Save new revision" })).toBeVisible();
});

test("keeps the production fixture page within the viewport", async ({ page }) => {
  await openEvaluation(page, "report");
  let overflow = await page.locator("#product-evaluation").evaluate((element) => ({
    horizontal: element.scrollWidth > element.clientWidth,
    document: document.documentElement.scrollWidth > window.innerWidth,
  }));
  expect(overflow).toEqual({ horizontal: false, document: false });
  await page.locator('[data-page="tags"]').click();
  overflow = await page.locator("#product-evaluation").evaluate((element) => ({
    horizontal: element.scrollWidth > element.clientWidth,
    document: document.documentElement.scrollWidth > window.innerWidth,
  }));
  expect(overflow).toEqual({ horizontal: false, document: false });
});

test("keeps critical overlays within the 390px minimum viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openEvaluation(page);
  await page.locator("#new-run").click();
  const newRun = page.locator("#new-run-dialog");
  await expect(newRun).toBeVisible();
  let overflow = await newRun.evaluate((element) => ({
    horizontal: element.scrollWidth > element.clientWidth,
    document: document.documentElement.scrollWidth > window.innerWidth,
  }));
  expect(overflow).toEqual({ horizontal: false, document: false });
  await newRun.locator("[data-close]").first().click();

  await page.locator('[data-page="settings"]').click();
  await page
    .locator("#context-table-body tr")
    .first()
    .getByRole("button", { name: "Preview requests" })
    .click();
  const preview = page.locator("#request-preview-dialog");
  await expect(preview).toBeVisible();
  overflow = await preview.evaluate((element) => ({
    horizontal: element.scrollWidth > element.clientWidth,
    document: document.documentElement.scrollWidth > window.innerWidth,
  }));
  expect(overflow).toEqual({ horizontal: false, document: false });
});
