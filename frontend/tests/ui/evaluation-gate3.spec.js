import path from "node:path";
import { expect, test } from "@playwright/test";

const evaluationEvidenceDir = path.resolve(
  "../openspec/changes/add-asr-automated-evaluation/verification",
);

async function openRuntime(page, pageName = "") {
  const suffix = pageName ? `?page=${pageName}` : "";
  await page.goto(`/evaluation.html${suffix}`);
  await expect(page.locator(".env")).toHaveAttribute("title", /56\/56\/56/);
}

test("keeps historical timeline defects as reference-only warnings", async ({ page }) => {
  const emptyBootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  emptyBootstrap.batches = [];
  emptyBootstrap.reviews = [];
  emptyBootstrap.benchmarks = { ...emptyBootstrap.benchmarks, items: [], total: 0 };
  emptyBootstrap.summary = {
    ...emptyBootstrap.summary,
    batch_count: 0,
    pending_reviews: 0,
    pending_conversations: 0,
    suspected_rate: null,
    suspected_numerator: null,
    denominator: null,
    benchmark_count: 0,
    benchmark_ai_count: 0,
    benchmark_manual_count: 0,
  };
  emptyBootstrap.asr_capabilities = emptyBootstrap.asr_capabilities.map((item) => ({
    ...item,
    status: "pending",
    available: false,
  }));
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(emptyBootstrap),
    });
  });
  await openRuntime(page);

  await expect(page.locator("#page-batches tbody .runtime-empty")).toContainText(
    /No evaluation results|暂无评测结果/,
  );
  await expect(page.locator("#page-batches tbody tr[data-batch-id]")).toHaveCount(0);
  await expect(page.locator('.nav[data-page="review"] .review-count')).toBeHidden();

  await page.locator("#new-run").click();
  const dialog = page.locator("#new-run-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("#issue-count")).toContainText(/55 reference warnings/);
  await expect(dialog.locator(".validation-row")).toHaveCount(3);
  await expect(dialog.locator(".validation-row").nth(0)).toContainText("56 / 56");
  await expect(dialog.locator(".validation-row").nth(1)).toContainText("56 / 56");
  await expect(dialog.locator(".validation-row").nth(2)).toContainText("56 / 56");
  await expect(dialog.locator("#choose-dataset-package")).toBeVisible();
  await expect(dialog.locator("#choose-dataset-repair")).toBeVisible();
  await expect(dialog.locator("#download-dataset-issues")).toBeVisible();
  await expect(dialog.locator(".dataset-issue-item")).toHaveCount(55);
  await expect(dialog.locator(".dataset-issue-item.blocking")).toHaveCount(0);
  await expect(dialog.locator(".dataset-issue-item.warning")).toHaveCount(55);
  await expect(dialog.locator(".batch-asr:disabled")).toHaveCount(3);
  await expect(dialog.locator("#start-run")).toBeDisabled();

  const auditResponse = await page.request.get("/api/evaluation/dataset/audit");
  expect(auditResponse.ok()).toBeTruthy();
  const audit = await auditResponse.json();
  expect(audit.conversation_count).toBe(56);
  expect(audit.valid_conversations).toBe(56);
  expect(audit.event_count).toBe(853);
  expect(audit.user_event_count).toBe(381);
  expect(audit.issues).toHaveLength(55);
  expect(audit.blocking_issue_count).toBe(0);
  expect(audit.warning_count).toBe(55);
});

test("deletes one Benchmark from list or detail only after confirmation", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  const sample = {
    id: "BM-DELETE-UI",
    batch_id: "EV-DELETE-UI",
    conversation_id: "1030000000086501",
    event_id: "R3",
    case_type: "bad",
    source: "manual",
    language: "ar",
    scenario_tag: "branch_names",
    label: "فرع الرياض",
    revision: 1,
    audio_start_s: 1,
    audio_end_s: 2,
    audio_url: null,
    clip_status: "unavailable",
    clip_error: "Fixture has no audio",
  };
  let deleted = false;
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    const items = deleted ? [] : [sample];
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ...bootstrap,
        benchmarks: { items, total: items.length, limit: 20, offset: 0 },
        summary: { ...bootstrap.summary, benchmark_count: items.length },
      }),
    });
  });
  await page.route("**/api/evaluation/benchmarks/BM-DELETE-UI", async (route) => {
    if (route.request().method() !== "DELETE") {
      await route.continue();
      return;
    }
    deleted = true;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ id: sample.id, deleted: true }),
    });
  });
  await openRuntime(page, "library");

  await page.locator(".runtime-benchmark-delete").click();
  await expect(page.locator("#delete-benchmark-dialog")).toBeVisible();
  await expect(page.locator("#delete-benchmark-dialog")).toContainText(
    "source conversation, evaluation batch, report, and manual review remain unchanged",
  );
  await page.locator("#delete-benchmark-dialog [data-close]").last().click();
  expect(deleted).toBeFalsy();

  await page.locator(".runtime-sample-detail").click();
  await expect(page.locator("#sample-dialog")).toBeVisible();
  await page.locator("#sample-dialog .benchmark-delete").click();
  await page.locator("#confirm-delete-benchmark").click();
  await expect(page.locator("#page-library tbody .runtime-empty")).toBeVisible();
  expect(deleted).toBeTruthy();
});

test("keeps a rejected batch creation error visible inside the dialog", async ({ page }) => {
  await page.route("**/api/evaluation/batches", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Pricing is unavailable for selected model(s): qwen-plus. Add model pricing in Cost settings before starting the evaluation.",
      }),
    });
  });
  await openRuntime(page);
  await page.locator("#new-run").click();
  const dialog = page.locator("#new-run-dialog");
  await dialog.locator(".batch-asr").first().evaluate((input) => {
    input.disabled = false;
    input.checked = true;
  });
  await dialog.locator("#start-run").evaluate((button) => {
    button.disabled = false;
  });

  await dialog.locator("#start-run").click();

  const error = dialog.locator("#new-run-error");
  await expect(dialog).toBeVisible();
  await expect(error).toBeVisible();
  await expect(error).toContainText("qwen-plus");
  await expect(error).toBeFocused();
});

test("persists scenario tag versions, status, and deletion through the real API", async ({ page }, testInfo) => {
  await openRuntime(page, "tags");
  const cards = page.locator("#scenario-tag-grid .tag-card");
  const suffix = testInfo.project.name;
  await page.locator("#new-tag").click();
  await page.locator("#tag-name-en").fill(`Speaker overlap ${suffix}`);
  await page.locator("#tag-name-zh").fill(`说话人重叠 ${suffix}`);
  await page.locator("#tag-description-en").fill("Agent speech overlaps the customer channel.");
  await page.locator("#tag-description-zh").fill("坐席语音与用户声道重叠。");
  await page.locator("#tag-type").selectOption("acoustic");
  await page.locator("#save-tag").click();

  const branch = cards.filter({ hasText: `Speaker overlap ${suffix}` });
  await expect(branch).toHaveCount(1);
  await branch.getByRole("button", { name: `Edit Speaker overlap ${suffix}` }).click();
  await page.locator("#tag-description-en").fill(
    "Agent or robot speech overlaps the customer channel.",
  );
  await page.locator("#save-tag").click();
  await expect(branch).toContainText("v2");
  await expect(branch).toContainText("Agent or robot speech");

  await branch.getByRole("button", { name: "Disable" }).click();
  await expect(branch).toContainText("Disabled");
  await branch.getByRole("button", { name: "Enable" }).click();
  await expect(branch).toContainText("Enabled");

  await branch.getByRole("button", { name: `Delete Speaker overlap ${suffix}` }).click();
  await expect(page.locator("#delete-tag-dialog")).toBeVisible();
  await page.locator("#confirm-delete-tag").click();
  await expect(branch).toHaveCount(0);
});

test("versions the CNY to USD rate used by future mixed-currency batches", async ({ page }) => {
  await openRuntime(page, "costs");
  const rate = page.locator("#cny-to-usd-rate");
  const source = page.locator("#cny-to-usd-source");
  const budget = page.locator("#default-batch-budget");
  await expect(rate).toBeVisible();
  await rate.fill("0.145");
  await source.fill("Finance-approved browser acceptance rate");
  await budget.fill("12.50");
  const asrCard = page.locator("#page-costs article.card").filter({ hasText: "ASR resource rates" });
  await asrCard.locator("tbody tr").first().locator(".price-input").fill("$0.11");
  await page.locator("#save-costs").click();
  await expect(page.locator("#toast")).toContainText(/Pricing and FX version saved|价格与汇率版本已保存/);
  const response = await page.request.get("/api/evaluation/pricing/settings");
  expect(response.ok()).toBeTruthy();
  const pricing = await response.json();
  expect(pricing.cny_to_usd).toBe(0.145);
  expect(pricing.fx_rates).toEqual({ USD: 1, CNY: 0.145 });
  expect(pricing.default_batch_budget).toBe(12.5);
  expect(pricing.rates.asr.find((item) => item.provider === "Soniox").unit_price).toBe(0.11);
});

test("uploads a replacement package through the visible file picker", async ({ page }) => {
  await openRuntime(page);
  const currentAudit = await (
    await page.request.get("/api/evaluation/dataset/audit")
  ).json();
  const blockingIssue = {
    severity: "blocking",
    issue_type: "missing_file",
    conversation_id: "1030000000086002",
    expected_path: "record/1030000000086002.mp3",
    message: "Required full-call audio is missing.",
  };
  await page.route("**/api/evaluation/dataset/upload", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...currentAudit,
        dataset_id: "dataset-ui-candidate",
        filename: "my-real-data.zip",
        active: false,
        valid: false,
        valid_conversations: 55,
        blocking_issue_count: 1,
        blocking_issues: [blockingIssue],
        issues: [...currentAudit.warnings, blockingIssue],
      }),
    });
  });

  await page.locator("#new-run").click();
  await expect(page.locator("#new-run-dialog")).toBeVisible();
  await page.locator("#dataset-upload-input").setInputFiles({
    name: "my-real-data.zip",
    mimeType: "application/zip",
    buffer: Buffer.from("browser-upload-fixture"),
  });

  await expect(page.locator("#dataset-package-name")).toHaveText("my-real-data.zip");
  await expect(page.locator("#dataset-upload-status")).toContainText(
    "staged for repair",
  );
  await expect(page.locator("#discard-dataset-upload")).toBeVisible();
  await expect(page.locator("#start-run")).toBeDisabled();
  await page.locator("#discard-dataset-upload").click();
  await expect(page.locator("#dataset-package-name")).not.toHaveText("my-real-data.zip");
  await expect(page.locator("#discard-dataset-upload")).toBeHidden();
});

test("deletes a failed batch only after explicit confirmation", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  const failedBatch = {
    id: "EV-DELETE-FAILED",
    name: "Mistaken upload",
    context_name: "利雅得银行分行转接 v10",
    input_count: 56,
    status: "partially_failed",
    stage: "failed",
    progress: 0,
    suspected_numerator: null,
    denominator: 381,
    excluded_count: 0,
    cost: 0,
    budget: 10,
    review_total: 0,
    review_completed: 0,
    report_type: null,
    result_disposition: "formal",
    snapshot: {
      execution_failure: {
        category: "connection_unavailable",
        message: "Missing verified connections: soniox",
        stage: "pass_1",
        retryable: true,
      },
    },
    updated_at: "2026-09-17T00:00:00Z",
    version: 1,
  };
  let deleted = false;
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ ...bootstrap, batches: deleted ? [] : [failedBatch] }),
    });
  });
  await page.route("**/api/evaluation/batches/EV-DELETE-FAILED", async (route) => {
    expect(route.request().method()).toBe("DELETE");
    deleted = true;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ id: failedBatch.id, deleted: true }),
    });
  });

  await page.goto("/evaluation.html");
  const row = page.locator('tr[data-batch-id="EV-DELETE-FAILED"]');
  await expect(row).toBeVisible();
  await expect(row).toContainText("Riyad Bank branch routing v10");
  await expect(row).not.toContainText("利雅得银行分行转接");
  await row.getByRole("button", { name: "View task" }).click();
  await expect(page.locator(".runtime-failure-notice")).toContainText(
    "Missing verified connections: soniox",
  );
  await expect(page.locator("#page-run .page-head")).toContainText(
    "Riyad Bank branch routing v10",
  );
  await page.getByRole("button", { name: "Evaluation batches", exact: true }).click();
  await row.getByRole("button", { name: "Delete" }).click();
  await expect(page.locator("#delete-batch-dialog")).toBeVisible();
  await page.locator("#confirm-delete-batch").click();
  await expect(row).toHaveCount(0);
});

test("only enables ASR resources with a persisted verified capability", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  bootstrap.asr_capabilities = bootstrap.asr_capabilities.map((item) => ({
    ...item,
    status: item.provider === "soniox" ? "verified" : "pending",
    available: item.provider === "soniox",
    verified_at: item.provider === "soniox" ? "2026-09-17T00:00:00Z" : null,
  }));
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  await page.goto("/evaluation.html");
  await page.locator("#new-run").click();
  const dialog = page.locator("#new-run-dialog");
  await expect(dialog.locator(".batch-asr:not(:disabled)")).toHaveCount(1);
  await expect(dialog.locator(".batch-asr:checked")).toHaveCount(1);
  await expect(dialog.locator(".batch-asr:disabled")).toHaveCount(2);
  await expect(dialog.locator("#start-run")).toBeEnabled();
  await expect(dialog.locator(".batch-asr-option").nth(1)).toContainText("pending verification");
});

test("loads verified official ASR and selected-model LLM prices", async ({ page }) => {
  const requests = [];
  await page.route("**/api/evaluation/pricing/official", async (route) => {
    const payload = route.request().postDataJSON();
    requests.push(payload);
    const asrItems = [
      ["Soniox", "stt-async-v5", 0.10, "https://soniox.com/pricing"],
      ["Speechmatics", "melia-1", 0.129, "https://www.speechmatics.com/pricing"],
      ["ElevenLabs", "scribe-v2", 0.22, "https://elevenlabs.io/pricing/api"],
    ].map(([provider, model, unit_price, source_url]) => ({
      provider,
      model,
      unit_price,
      currency: "USD",
      billing_unit: "audio_hour",
      source_url,
      source_label: `${provider} official pricing`,
      note: "Public list price",
      checked_at: "2026-09-16T20:00:00Z",
    }));
    const llmItems = [
      {
        provider: "DeepSeek",
        model: "deepseek-flash",
        input_per_1m: 0.30,
        cached_input_per_1m: 0.006,
        output_per_1m: 1.20,
        currency: "USD",
        source_url: "https://api-docs.deepseek.com/quick_start/pricing",
        source_label: "DeepSeek API pricing",
        note: "Public list price",
      },
      {
        provider: "GPT",
        model: "gpt-5-mini",
        input_per_1m: 0.25,
        cached_input_per_1m: 0.025,
        output_per_1m: 2,
        currency: "USD",
        source_url: "https://developers.openai.com/api/docs/models/gpt-5-mini",
        source_label: "OpenAI API model pricing",
        note: "Public list price",
      },
    ];
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        scope: payload.scope,
        checked_at: "2026-09-16T20:00:00Z",
        items: payload.scope === "asr" ? asrItems : llmItems,
      }),
    });
  });

  await openRuntime(page, "costs");
  await page.locator("#sync-asr-pricing").click();
  const asrRows = page
    .locator("#sync-asr-pricing")
    .locator("xpath=ancestor::article")
    .locator("tbody tr");
  await expect(asrRows.nth(0).locator(".price-input")).toHaveValue("$0.10");
  await expect(asrRows.nth(1).locator(".price-input")).toHaveValue("$0.129");
  await expect(asrRows.nth(2).locator(".price-input")).toHaveValue("$0.22");

  const llmRows = page.locator("#page-costs .pricing-table tbody tr");
  await llmRows.nth(0).locator(".model-provider").selectOption("DeepSeek");
  await llmRows.nth(0).locator(".model-name-select").selectOption("__custom__");
  await llmRows.nth(0).locator(".custom-model").fill("DeepSeek/deepseek-flash");
  await page.locator("#sync-llm-pricing").click();
  await expect(llmRows.nth(0).locator(".price-input").nth(0)).toHaveValue("$0.30");
  await expect(llmRows.nth(0).locator(".price-input").nth(1)).toHaveValue("$0.006");
  await expect(llmRows.nth(0).locator(".price-input").nth(2)).toHaveValue("$1.20");
  expect(requests[1]).toEqual({
    scope: "llm",
    selections: [
      { provider: "DeepSeek", model: "deepseek-flash" },
      { provider: "GPT", model: "gpt-5-mini" },
    ],
  });
});

test("serves the actual Arabic workbook transcript and real audio", async ({ page }) => {
  await openRuntime(page);

  const response = await page.request.get(
    "/api/evaluation/conversations/1030000000091506",
  );
  expect(response.ok()).toBeTruthy();
  const conversation = await response.json();
  expect(conversation.detected_language).toBe("ar");
  expect(conversation.event_count).toBe(22);
  const event = conversation.events.find((item) => item.event_id === "R18");
  expect(event.speaker).toBe("customer");
  expect(event.text).toBe("أقول لك أنا، أنا عميلة الهدية.");
  expect(JSON.stringify(conversation)).not.toContain("I'm a Diamond customer");

  const fullCallResponse = await page.request.get(conversation.audio_url, {
    headers: { Range: "bytes=0-1023" },
  });
  expect(fullCallResponse.status()).toBe(206);
  expect(fullCallResponse.headers()["content-type"]).toContain("audio/mpeg");
  expect((await fullCallResponse.body()).byteLength).toBe(1024);

  const userAudioResponse = await page.request.get(conversation.user_audio_url, {
    headers: { Range: "bytes=0-1023" },
  });
  expect(userAudioResponse.status()).toBe(206);
  expect(userAudioResponse.headers()["content-type"]).toContain("audio/wav");
  expect((await userAudioResponse.body()).byteLength).toBe(1024);
});

test("does not expose simulated report, review, or Benchmark results", async ({ page }) => {
  const emptyBootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  emptyBootstrap.batches = [];
  emptyBootstrap.reviews = [];
  emptyBootstrap.benchmarks = { ...emptyBootstrap.benchmarks, items: [], total: 0 };
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(emptyBootstrap),
    });
  });
  await openRuntime(page, "report");
  await expect(page.locator("#page-batches")).toHaveClass(/active/);
  await expect(page.locator("#page-report")).not.toHaveClass(/active/);
  await expect(page.locator("#page-batches tbody tr[data-batch-id]")).toHaveCount(0);

  await page.locator('[data-page="review"]').click();
  await expect(page.locator('#page-review [data-review-panel="asr"] .runtime-empty')).toContainText(
    /No review cases remain|没有待复核/,
  );
  await expect(page.locator("#page-review .review")).toBeHidden();

  await page.locator('[data-page="library"]').click();
  await expect(page.locator("#page-library tbody .runtime-empty")).toContainText(
    /No Benchmark samples|暂无 Benchmark/,
  );
  await expect(page.locator("#page-library tbody tr[data-benchmark-id]")).toHaveCount(0);
  await expect(page.locator("#download-benchmarks")).toBeDisabled();
  await expect(page.locator("#download-filtered-benchmarks")).toBeDisabled();
  await expect(page.locator("#select-all-benchmarks")).toBeDisabled();

  const bootstrap = await page.evaluate(async () => (
    await (await fetch("/api/evaluation/bootstrap")).json()
  ));
  expect(bootstrap.batches).toEqual([]);
  expect(bootstrap.reviews).toEqual([]);
  expect(bootstrap.benchmarks.items).toEqual([]);
});

test("keeps the confirmed frozen fixture available only by explicit flag", async ({
  page,
}) => {
  await page.goto("/evaluation.html?gate2=1&page=report");
  await expect(page.locator("#page-report")).toHaveClass(/active/);
  await expect(page.getByText("Evaluation funnel", { exact: true })).toBeVisible();

  await openRuntime(page, "report");
  await expect(page.locator("#page-report")).not.toHaveClass(/active/);
  await expect(page.locator("#page-batches")).toHaveClass(/active/);
});

test("keeps runtime pages free of horizontal overflow", async ({ page }) => {
  await openRuntime(page, "library");
  const overflow = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    dialogs: [...document.querySelectorAll("dialog")].map(
      (dialog) => dialog.scrollWidth - dialog.clientWidth,
    ),
  }));
  expect(overflow.document).toBeLessThanOrEqual(1);
  expect(overflow.dialogs.every((value) => value <= 1)).toBeTruthy();
});

test("persists evaluation configuration versions and previews the actual request envelope", async ({
  page,
}, testInfo) => {
  await openRuntime(page, "settings");
  const suffix = testInfo.project.name;

  const contextRow = page.locator("#context-table-body tr").first();
  await contextRow.getByRole("button", { name: "Edit new version" }).click();
  const contextDialog = page.locator("#context-dialog");
  const objective = contextDialog.getByLabel("Business background and objective");
  await objective.fill(`${await objective.inputValue()} · ${suffix}`);
  await contextDialog.getByRole("button", { name: "Save as new version" }).click();
  await expect(contextDialog).toBeHidden();
  await expect(contextRow.locator(".context-version")).toHaveText(/v[4-9]|v\d{2,}/);

  await contextRow.getByRole("button", { name: "Preview requests" }).click();
  const preview = page.locator("#request-preview-dialog");
  await expect(preview).toBeVisible();
  await expect(preview.locator("#preview-template-message")).toContainText("event_results");
  await expect(preview.locator("#request-field-map-grid")).toContainText(
    "{{conversation_history}} → User Message.conversation_history",
  );
  await expect(preview.locator("#preview-rendered-message")).toContainText(suffix);
  await preview.getByRole("button", { name: "Pass 2 · Evidence decision" }).click();
  await expect(preview.locator("#preview-template-message")).toContainText("{{request_group_id}}");
  await expect(preview.locator("#preview-template-message")).toContainText('"results"');
  await expect(preview.locator("#preview-template-message")).toContainText('"positioning_quality"');
  await expect(preview.locator("#preview-rendered-message")).toContainText("candidate_cases");
  await preview.getByRole("button", { name: "Close", exact: true }).click();

  await page.getByRole("button", { name: "Reference dictionaries", exact: true }).click();
  const dictionaryRow = page.locator("#dictionary-table-body tr").first();
  await dictionaryRow.getByRole("button", { name: "Edit new version" }).click();
  const dictionaryDialog = page.locator("#dictionary-dialog");
  const entries = JSON.parse(await dictionaryDialog.getByLabel(/Dictionary entries/).inputValue());
  entries.push({ canonical_value: suffix, alias: suffix, code: "", locale: "en" });
  await dictionaryDialog.getByLabel(/Dictionary entries/).fill(JSON.stringify(entries, null, 2));
  await dictionaryDialog.getByRole("button", { name: "Save as new version" }).click();
  await expect(dictionaryDialog).toBeHidden();

  await page.getByRole("button", { name: "Two-pass evaluation prompts", exact: true }).click();
  const firstPromptCard = page.locator("#evaluation-prompts .card").first();
  await firstPromptCard.getByRole("button", { name: "Edit fixed template" }).click();
  const editor = firstPromptCard.locator(".prompt-editor");
  const originalPrompt = await editor.inputValue();
  await editor.fill(`${originalPrompt}\nRuntime acceptance: ${suffix}`);
  await firstPromptCard.getByRole("button", { name: "Save as new version" }).click();
  await expect(editor).toHaveAttribute("readonly", "");

  await firstPromptCard.getByRole("button", { name: "Version history" }).click();
  const historyDialog = page.locator("#prompt-history-dialog");
  await expect(historyDialog).toBeVisible();
  expect(await historyDialog.evaluate((node) => node.scrollWidth - node.clientWidth)).toBeLessThanOrEqual(1);
  expect(await historyDialog.locator(".prompt-version-item").count()).toBeGreaterThan(1);
  await historyDialog.locator(".prompt-version-item").nth(1).click();
  await expect(historyDialog.locator(".prompt-version-diff")).toContainText(
    `Runtime acceptance: ${suffix}`,
  );
  await historyDialog.getByRole("button", { name: /Restore v\d+ as v\d+/ }).click();
  await expect(historyDialog).toBeHidden();
  await expect(editor).toHaveValue(originalPrompt);

  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  expect(bootstrap.evaluation_contexts[0].business_background_and_objective).toContain(suffix);
  expect(bootstrap.reference_dictionaries[0].entries.at(-1).canonical_value).toBe(suffix);
  expect(bootstrap.prompt_templates.find((item) => item.template_key === "pass_1").content)
    .toBe(originalPrompt);
});

test("keeps English manual-review UI free of Chinese while preserving source text", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  bootstrap.reviews = [{
    id: "review-i18n",
    batch_id: "batch-i18n",
    conversation_id: "1030000000091506",
    event_id: "R18",
    issue_en: "客户类别需要回听确认",
    issue_zh: "客户类别需要回听确认",
    question_en: "用户实际说的是哪个客户类别？",
    question_zh: "用户实际说的是哪个客户类别？",
    priority: "P1",
    production_transcript: "أقول لك أنا، أنا عميلة الهدية.",
    context: [{ event: "R18", speaker: "customer", text: "原始来源文本" }],
    providers: [{
      provider: "Soniox",
      text: "أنا عميلة ذهبية",
      segment_id: "soniox-1",
      start_s: 1,
      end_s: 2,
    }],
    language: "ar",
    scenario_tag: "customer_tier",
    start_s: 1,
    end_s: 2,
    audio_url: "/api/evaluation/conversations/1030000000091506/user-audio",
    version: 1,
  }];
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  await page.goto("/evaluation.html?page=review");
  const review = page.locator("#page-review .review");
  await expect(review.locator(".review-head h2")).toHaveText(
    "Customer tier needs audio confirmation",
  );
  await expect(review.locator(".evidence-grid .evidence").nth(1)).toContainText(
    "Which customer tier did the customer actually say?",
  );
  const controlledCopy = await review.locator(
    ".review-head, .notice, .form-grid, .review-comparison label, .review-actions",
  ).allInnerTexts();
  expect(controlledCopy.join(" ")).not.toMatch(/[\u4e00-\u9fff]/);
  await expect(review.locator(".evidence-grid .evidence").nth(2)).toContainText("原始来源文本");
});

test("reviews historical Turn issues in a separate audio-first queue", async ({ page }, testInfo) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  bootstrap.reviews = [];
  bootstrap.historical_turn_issues = [{
    issue_group_id: "HTI-R28-R30",
    batch_id: "EV-TURN-REVIEW",
    conversation_id: "1030000000070676",
    source_event_ids: ["R28", "R30"],
    resulting_case_ids: ["CASE-I014", "CASE-I015"],
    issue_type: "order_anomaly",
    issue_types: ["order_anomaly"],
    affected_turn_count: 2,
    status: "pending",
    version: 1,
    audio_url: "/api/evaluation/historical-turn-issues/HTI-R28-R30/audio",
    audio_evidence: {
      islands: [
        {
          case_id: "CASE-I014",
          audio_island_id: "1030000000070676:island:7",
          start_s: 42,
          end_s: 44,
          audio_url: "/api/evaluation/historical-turn-issues/HTI-R28-R30/audio?audio_island_id=island-7",
          providers: [{
            provider: "soniox",
            turn_id: "soniox-turn-28",
            text: "two two three",
            inferred_role: "customer",
            overlap_s: 1.7,
          }],
        },
        {
          case_id: "CASE-I015",
          audio_island_id: "1030000000070676:island:8",
          start_s: 45,
          end_s: 46,
          audio_url: "/api/evaluation/historical-turn-issues/HTI-R28-R30/audio?audio_island_id=island-8",
          providers: [{
            provider: "speechmatics",
            turn_id: "speechmatics-turn-30",
            text: "two two three",
            inferred_role: "customer",
            overlap_s: 0.8,
          }],
        },
      ],
    },
    source_turns: [
      { event_id: "R28", source_row: 28, speaker: "customer", text: "two" },
      { event_id: "R30", source_row: 30, speaker: "customer", text: "three" },
    ],
  }];
  let submitted = null;
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  await page.route("**/api/evaluation/historical-turn-issues/HTI-R28-R30/decision", async (route) => {
    submitted = route.request().postDataJSON();
    bootstrap.historical_turn_issues = [];
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        issue_group_id: "HTI-R28-R30",
        status: "confirmed",
        decision: "confirm",
        version: 2,
      }),
    });
  });

  await page.goto("/evaluation.html?page=review");
  await page.locator('[data-review-mode="turn"]').click();
  const panel = page.locator('[data-review-panel="turn"]');
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("1030000000070676");
  await expect(panel).toContainText("R28 · row 28");
  await expect(panel).toContainText("R30 · row 30");
  await expect(panel).toContainText("CASE-I014");
  await expect(panel).toContainText("CASE-I015");
  await expect(panel).toContainText("soniox-turn-28");
  await expect(panel).toContainText("speechmatics-turn-30");
  await expect(panel.locator("audio")).toHaveCount(2);
  await expect(panel.locator("audio").first()).toHaveAttribute(
    "src",
    "/api/evaluation/historical-turn-issues/HTI-R28-R30/audio?audio_island_id=island-7",
  );
  await expect(panel.locator('[data-turn-decision="confirm"]')).toBeVisible();
  expect(await panel.evaluate((node) => node.scrollWidth - node.clientWidth)).toBeLessThanOrEqual(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
    .toBeLessThanOrEqual(1);
  await page.screenshot({
    path: path.join(
      evaluationEvidenceDir,
      `actual-v1.20-turn-review-${testInfo.project.name}.png`,
    ),
    animations: "disabled",
  });

  await panel.locator('[data-turn-decision="confirm"]').click();
  await expect(panel.locator(".runtime-empty")).toBeVisible();
  expect(submitted.decision).toBe("confirm");
  expect(submitted.expected_version).toBe(1);
});

test("refreshes stale Turn issue counts before opening the queue", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  const staleIssue = {
    issue_group_id: "HTI-STALE",
    batch_id: "EV-STALE",
    conversation_id: "1030000000070676",
    source_event_ids: ["R28"],
    resulting_case_ids: ["CASE-I014"],
    issue_type: "wrong_merge",
    issue_types: ["wrong_merge"],
    affected_turn_count: 1,
    status: "pending",
    version: 1,
    audio_evidence: { islands: [] },
    source_turns: [],
  };
  let bootstrapRequests = 0;
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    bootstrapRequests += 1;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ...bootstrap,
        reviews: [],
        historical_turn_issues: bootstrapRequests === 1 ? [staleIssue] : [],
      }),
    });
  });

  await page.goto("/evaluation.html?page=review");
  await expect(page.locator("#page-review .turn-review-count")).toHaveText("1");
  await page.locator('[data-review-mode="turn"]').click();
  await expect(page.locator("#page-review .turn-review-count")).toHaveText("0");
  await expect(page.locator("#page-review [data-review-panel='turn'] .queue h2")).toHaveText(
    "Pending Turn issue groups 0",
  );
  expect(bootstrapRequests).toBeGreaterThanOrEqual(2);
});

test("keeps the current view when review queue refresh fails", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  const staleIssue = {
    issue_group_id: "HTI-REFRESH-FAILURE",
    batch_id: "EV-REFRESH-FAILURE",
    conversation_id: "1030000000070676",
    source_event_ids: ["R28"],
    resulting_case_ids: ["CASE-I014"],
    issue_type: "wrong_merge",
    issue_types: ["wrong_merge"],
    affected_turn_count: 1,
    status: "pending",
    version: 1,
    audio_evidence: { islands: [] },
    source_turns: [],
  };
  const batch = {
    id: "EV-REFRESH-FAILURE",
    name: "Refresh failure",
    context_name: "Review refresh guard",
    input_count: 1,
    status: "awaiting_review",
    stage: "manual_review",
    progress: 92,
    denominator: 1,
    excluded_count: 0,
    suspected_numerator: 1,
    cost: 0,
    budget: 1,
    providers: ["soniox"],
    updated_at: "2026-09-23T12:00:00Z",
    version: 1,
    report_type: null,
    review_total: 1,
    review_completed: 0,
    snapshot: {},
  };
  let bootstrapRequests = 0;
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    bootstrapRequests += 1;
    if (bootstrapRequests === 1) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          ...bootstrap,
          batches: [batch],
          reviews: [],
          historical_turn_issues: [staleIssue],
        }),
      });
      return;
    }
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "offline" }),
    });
  });

  await page.goto("/evaluation.html");
  await page.locator('.nav[data-page="review"]').click();
  await expect(page.locator("#page-batches")).toHaveClass(/active/);
  await expect(page.locator('.nav[data-page="review"] .review-count')).toHaveText("1");
  await expect(page.locator("#toast")).toContainText("Review data could not be refreshed");

  await page.locator('tr[data-batch-id="EV-REFRESH-FAILURE"] [data-action="open"]').click();
  await expect(page.locator("#page-run")).toHaveClass(/active/);
  await page.locator(".runtime-open-review").click();
  await expect(page.locator("#page-run")).toHaveClass(/active/);
  await expect(page.locator("#toast")).toContainText("Review data could not be refreshed");

  bootstrapRequests = 0;
  await page.goto("/evaluation.html?page=review");
  await expect(page.locator('[data-review-mode="asr"]')).toHaveClass(/active/);
  await page.locator('[data-review-mode="turn"]').click();
  await expect(page.locator('[data-review-mode="asr"]')).toHaveClass(/active/);
  await expect(page.locator('[data-review-mode="turn"]')).not.toHaveClass(/active/);
  await expect(page.locator("#page-review .turn-review-count")).toHaveText("1");
  await expect(page.locator("#toast")).toContainText("Review data could not be refreshed");
});

test("renders a persisted report into the frozen report structure", async ({ page }, testInfo) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  bootstrap.batches = [{
    id: "EV-REPORT-RUNTIME",
    name: "Runtime report",
    context_name: "Riyad Bank branch routing v4",
    input_count: 56,
    status: "awaiting_review",
    stage: "manual_review",
    progress: 92,
    denominator: 381,
    excluded_count: 0,
    suspected_numerator: 1,
    cost: 0.45,
    budget: 10,
    providers: ["soniox", "speechmatics", "elevenlabs"],
    updated_at: "2026-09-16T20:00:00Z",
    version: 3,
    // The report can be recovered after this bootstrap snapshot was read.
    report_type: null,
    review_total: 1,
    review_completed: 0,
    snapshot: {
      pass_1_model: "deepseek-chat",
      source_warning_counts: { decreasing_event_time: 55 },
    },
  }];
  const report = {
    report_id: "EV-REPORT-RUNTIME-R1",
    version: 1,
    report_type: "preliminary",
    payload: {
      batch_id: "EV-REPORT-RUNTIME",
      batch_name: "Runtime report",
      context_name: "Riyad Bank branch routing v4",
      report_type: "preliminary",
      input_conversations: 56,
      valid_user_events: 381,
      source_user_events: 386,
      excluded_count: 5,
      excluded_reasons: [{ reason: "pass_1_failed_or_unavailable", count: 5 }],
      source_warning_counts: {},
      candidate_count: 1,
      decision_counts: { "Good Case": 0, "Bad Case": 1, "Needs manual audio review": 0 },
      suspected_count: 1,
      suspected_rate: 0.26,
      review_total: 0,
      review_completed: 0,
      historical_turn_quality: {
        confirmed_group_count: 1,
        affected_turn_row_count: 2,
        review_total: 2,
        review_completed: 1,
        review_pending: 1,
        review_coverage: 50,
        groups: [{
          conversation_id: "1030000000070676",
          source_event_ids: ["R28", "R30"],
          resulting_case_ids: ["CASE-R28-R30"],
          issue_type: "over_split",
          issue_types: ["over_split"],
          affected_turn_count: 2,
          audio_evidence: {
            islands: [{
              case_id: "CASE-R28-R30",
              audio_island_id: "1030000000070676:island:7",
              audio_url: "/api/evaluation/historical-turn-issues/HTI-R28-R30/audio?audio_island_id=island-7",
            }],
          },
        }],
      },
      tag_distribution: [{ name: "服务诉求", count: 1 }],
      language_distribution: [{ name: "ar", count: 1 }],
      proposed_tags: [{
        proposal_key: "customer-tier-audio",
        type: "semantic",
        name_en: "Customer tier audio",
        name_zh: "客户类别录音",
        description_en: "Review tier wording from linked audio.",
        description_zh: "通过关联录音复核客户类别表述。",
        case_keys: [["1030000000091506", "R18"], ["1030000000091506", "R20"]],
      }],
      production_asr_observations: [{
        scenario_tag: "服务诉求",
        case_count: 1,
        case_keys: [["1030000000091506", "R18"]],
      }],
      cases: [{
        conversation_id: "1030000000091506",
        event_id: "R18",
        language: "ar",
        priority: "P1",
        issue_title: "服务诉求",
        production_transcript: "أقول لك أنا، أنا عميلة الهدية.",
        audio_start_s: 59.5,
        audio_end_s: 65.5,
        audio_available: true,
        evaluation_asr: { soniox: "legacy full-call evidence ".repeat(20) },
        decision: "Bad Case",
        reference_text: "أنا عميلة ذهبية",
        scenario_tag: "服务诉求",
        reason: "业务实体与历史转写不一致。",
        label_status: "AI labeled",
      }],
      frozen_snapshot: { benchmark_count: 1 },
    },
  };
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  await page.route("**/api/evaluation/batches/EV-REPORT-RUNTIME/report", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(report) });
  });
  await page.route("**/api/evaluation/batches/EV-REPORT-RUNTIME/costs", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ asr: [], llm: [], total_usd: 0 }) });
  });
  const conversation = {
    conversation_id: "1030000000091506",
    event_count: 2,
    audio_url: "/api/evaluation/conversations/1030000000091506/audio?batch_id=EV-REPORT-RUNTIME",
    events: [
      { event_id: "R17", time_s: 57.1, speaker: "robot", text: "Which customer tier do you mean?" },
      { event_id: "R18", time_s: 61.2, speaker: "customer", text: "أقول لك أنا، أنا عميلة الهدية." },
    ],
  };
  const scopedSourceRequests = [];
  await page.route(/\/api\/evaluation\/conversations\/1030000000091506\?batch_id=EV-REPORT-RUNTIME$/, async (route) => {
    scopedSourceRequests.push(route.request().url());
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(conversation) });
  });
  await page.route(/\/api\/evaluation\/conversations\/1030000000091506\/(?:audio|user-audio)\?batch_id=EV-REPORT-RUNTIME$/, async (route) => {
    scopedSourceRequests.push(route.request().url());
    await route.fulfill({ status: 200, contentType: "audio/wav", body: Buffer.alloc(44) });
  });
  const translationPayloads = [];
  await page.route("**/api/evaluation/batches/EV-REPORT-RUNTIME/display-translation", async (route) => {
    const translationPayload = route.request().postDataJSON();
    translationPayloads.push(translationPayload);
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        translations: translationPayload.texts.map((text) => (
          text === "أقول لك أنا، أنا عميلة الهدية."
            ? "我跟你说，我是礼品客户。"
            : "您指的是哪一种客户等级？"
        )),
        provider: "deepseek",
        model_id: "deepseek-chat",
        ephemeral: true,
        evidence: false,
      }),
    });
  });
  await page.goto("/evaluation.html");
  await page.getByRole("button", { name: "View task" }).click();
  await expect(page.locator("#page-run article.card:nth-of-type(2) tbody tr")).toHaveCount(1);
  await expect(page.locator("#page-run article.card:nth-of-type(2)")).toContainText(
    "1030000000091506 · R18",
  );
  await expect(page.locator("#page-run article.card:nth-of-type(2)")).toContainText(
    "Service request",
  );
  await expect(page.locator("#page-run .grid4 .metric").nth(1)).toContainText(
    "Unique persisted first-pass candidates",
  );
  await expect(page.locator("#page-run .runtime-cost-breakdown")).toContainText(
    "Usage was not recorded for this legacy run",
  );
  await page.getByRole("button", { name: "Evaluation report" }).click();
  await expect(page.getByText("Evaluation funnel", { exact: true })).toBeVisible();
  await expect(page.getByText("Case tag distribution", { exact: true })).toBeVisible();
  await expect(page.getByText("Proposed tag details", { exact: true })).toBeVisible();
  await expect(page.getByText("Production ASR recognition analysis", { exact: true })).toBeVisible();
  await expect(page.getByText("All suspicious cases in this batch", { exact: true })).toBeVisible();
  const turnQuality = page.locator("#historical-turn-quality");
  await expect(turnQuality.locator(".turn-quality-summary")).toContainText("1 group · 2 Turn rows");
  await expect(turnQuality).toContainText("50%");
  await expect(turnQuality).toContainText("1030000000070676");
  await expect(turnQuality).toContainText("R28 · R30");
  await expect(turnQuality).toContainText("Historical over-split");
  await expect(turnQuality.locator(".turn-report-audio")).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth))
    .toBeLessThanOrEqual(1);
  await page.screenshot({
    path: path.join(
      evaluationEvidenceDir,
      `actual-v1.20-turn-report-${testInfo.project.name}.png`,
    ),
    animations: "disabled",
    fullPage: true,
  });
  await expect(page.locator("#batch-case-details tbody tr")).toHaveCount(1);
  await expect(page.locator("#batch-case-details")).toContainText("1030000000091506 · R18");
  await expect(page.locator("#batch-case-details .runtime-report-audio")).toBeVisible();
  await page.locator("#batch-case-details .runtime-report-audio").click();
  await expect.poll(() => scopedSourceRequests.some((url) => url.includes("/user-audio?batch_id=EV-REPORT-RUNTIME"))).toBeTruthy();
  await expect(page.locator("#page-report > .grid4 .metric").nth(3)).toContainText("Benchmark samples");
  await expect(page.locator("#page-report > .grid4 .metric").nth(3)).toContainText("1");
  await expect(page.locator("#production-asr-analysis")).toContainText("1 / 1 cases show errors");
  await expect(page.locator("#production-asr-analysis")).not.toContainText("1030000000091506");
  await expect(page.locator("#report-tag-overview .runtime-open-proposed-tags")).toHaveText(
    "Review cases & create tag",
  );
  await expect(page.locator("#proposed-tag-details tbody tr")).toHaveCount(2);
  await expect(page.locator("#proposed-tag-details tbody tr").nth(0)).toContainText(
    "1030000000091506 · R18",
  );
  await expect(page.locator("#proposed-tag-details tbody tr").nth(1)).toContainText(
    "1030000000091506 · R20",
  );
  await expect(page.locator("#proposed-tag-details .runtime-create-proposed-tag")).toHaveCount(1);
  await expect(page.locator("#proposed-tag-details .runtime-report-audio")).toHaveText("▶ R18");
  await expect(page.locator("#proposed-tag-details .card-title .pill")).toHaveText(
    "2 cases pending classification",
  );
  await expect(page.locator("#batch-case-details .card-title select")).toHaveCount(1);
  await expect(page.locator("#batch-case-details tbody tr").first()).toContainText(
    "legacy full-call evidence",
  );
  await expect(page.locator("#batch-case-details .runtime-case-reason")).toHaveText(
    "The stored evidence indicates a meaning-changing transcript mismatch. Review the linked provider evidence for details.",
  );
  await expect(page.locator("#batch-case-details .runtime-case-reason")).not.toContainText(
    "业务实体",
  );
  await page.locator("#batch-case-details .runtime-conversation-link").click();
  await expect.poll(() => scopedSourceRequests.some((url) => url.endsWith("?batch_id=EV-REPORT-RUNTIME"))).toBeTruthy();
  await expect(page.locator("#conversation-drawer")).toBeVisible();
  await expect(page.locator("#conversation-drawer .runtime-conversation-turn")).toHaveCount(2);
  await expect(page.locator("#conversation-drawer")).toContainText("أقول لك أنا، أنا عميلة الهدية.");
  expect(translationPayloads).toHaveLength(0);
  await page.locator("#close-conversation-drawer").click();
  await page.getByRole("tab", { name: "中文" }).click();
  await page.locator("#batch-case-details .runtime-conversation-link").click();
  await expect(page.locator("#conversation-drawer")).toContainText("我跟你说，我是礼品客户。");
  await expect(page.locator("#drawer-event-id")).toContainText("deepseek / deepseek-chat");
  await expect(page.locator("#batch-case-details")).not.toContainText("Bad Case");
  await expect(page.locator("#batch-case-details")).not.toContainText("AI labeled");
  expect(await page.locator("#conversation-drawer").evaluate((node) => node.scrollWidth <= node.clientWidth)).toBeTruthy();
  expect(translationPayloads).toHaveLength(2);
  expect(translationPayloads).toContainEqual({
    texts: conversation.events.map((event) => event.text),
  });
  expect(translationPayloads).toContainEqual({ texts: ["أقول لك أنا، أنا عميلة الهدية."] });
  expect(JSON.stringify(translationPayloads)).not.toContain("关闭弹窗");
  await page.locator("#close-conversation-drawer").click();
  await page.locator("#batch-case-details .runtime-conversation-link").click();
  await expect(page.locator("#conversation-drawer")).toContainText("我跟你说，我是礼品客户。");
  expect(translationPayloads).toHaveLength(2);
  await page.locator("#batch-case-details .runtime-report-filter").selectOption("服务诉求");
  await expect(page.locator("#batch-case-details .card-title .pill")).toHaveText("1 / 1 条匹配");
});

test("shows successful checkpoints from a failed batch as non-final partial results", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  bootstrap.batches = [{
    id: "EV-PARTIAL-RUNTIME",
    name: "Partial runtime",
    context_name: "Riyad Bank routing",
    input_count: 56,
    status: "partially_failed",
    stage: "pass_2",
    progress: 92,
    denominator: 381,
    excluded_count: 0,
    suspected_numerator: 1,
    cost: 0.31,
    budget: 10,
    providers: ["soniox"],
    updated_at: "2026-09-20T20:00:00Z",
    version: 4,
    report_type: null,
    review_total: 0,
    review_completed: 0,
    snapshot: {},
  }];
  const partial = {
    report_id: "EV-PARTIAL-RUNTIME-PARTIAL",
    version: 0,
    report_type: "partial_results",
    ephemeral: true,
    payload: {
      batch_id: "EV-PARTIAL-RUNTIME",
      batch_name: "Partial runtime",
      context_name: "Riyad Bank routing",
      report_type: "partial_results",
      incomplete: true,
      non_final: true,
      failed_stage: "pass_2",
      failure: { message: "One frozen request group failed", retryable: true },
      cost: 0.31,
      budget: 10,
      input_conversations: 56,
      valid_user_events: 381,
      source_user_events: 381,
      excluded_count: 0,
      candidate_count: 2,
      evaluated_case_count: 1,
      incomplete_case_count: 1,
      decision_counts: { "Good Case": 1, "Bad Case": 0, "Needs manual audio review": 0 },
      suspected_count: 0,
      suspected_rate: 0,
      review_total: 0,
      review_completed: 0,
      benchmark_count: 1,
      tag_distribution: [],
      language_distribution: [],
      proposed_tags: [],
      production_asr_observations: [],
      cases: [],
      frozen_snapshot: {},
    },
  };
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  await page.route("**/api/evaluation/batches/EV-PARTIAL-RUNTIME/partial-results", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(partial) });
  });
  await page.route("**/api/evaluation/batches/EV-PARTIAL-RUNTIME/costs", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ asr: [], llm: [], total_usd: 0.31 }),
    });
  });
  await page.goto("/evaluation.html");

  await page.getByRole("button", { name: "Partial results" }).click();

  await expect(page.locator("#page-report")).toHaveClass(/active/);
  await expect(page.locator("#page-report")).toContainText(
    "Partial results · not a complete report",
  );
  await expect(page.locator("#page-report")).toContainText("One frozen request group failed");
  await expect(page.locator("#page-report")).toContainText("1");
});

test("adds cached Chinese comparisons to visible Arabic review and Benchmark evidence", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  const batchId = "EV-ARABIC-TRANSLATION";
  bootstrap.reviews = [{
    id: "RV-AR-1",
    batch_id: batchId,
    conversation_id: "CONV-AR-1",
    event_id: "R2",
    issue_en: "Transcript needs audio confirmation",
    issue_zh: "转写需要回听确认",
    question_en: "What did the customer say?",
    question_zh: "用户说了什么？",
    priority: "high",
    production_transcript: "أنا عميلة الهدية",
    context: [
      { speaker: "robot", event: "R1", text: "اختر اللغة" },
      { speaker: "customer", event: "R2", text: "أنا عميلة الهدية" },
    ],
    providers: [
      { provider: "Soniox", text: "أنا عميلة ذهبية", segment_id: "SO-1", start_s: 1, end_s: 2 },
      { provider: "Speechmatics", text: "gold customer", segment_id: "SM-1", start_s: 1, end_s: 2 },
      { provider: "ElevenLabs", text: "أنا عميلة الهدية", segment_id: "EL-1", start_s: 1, end_s: 2 },
    ],
    language: "ar",
    scenario_tag: "customer_tier",
    start_s: 1,
    end_s: 2,
    audio_url: "/missing-review.wav",
    version: 1,
  }];
  bootstrap.benchmarks = {
    items: [
      {
        id: "BM-AR-1", batch_id: batchId, conversation_id: "CONV-AR-1", event_id: "R2",
        case_type: "bad", language: "ar", scenario_tag: "customer_tier", source: "ai",
        label: "أنا عميلة ذهبية", revision: 1, audio_url: null, clip_status: "missing",
      },
      {
        id: "BM-AR-2", batch_id: batchId, conversation_id: "CONV-AR-2", event_id: "R4",
        case_type: "good", language: "ar", scenario_tag: "branches", source: "manual",
        label: "فرع العليا", revision: 1, audio_url: null, clip_status: "missing",
      },
      {
        id: "BM-AR-3", batch_id: batchId, conversation_id: "CONV-AR-3", event_id: "R6",
        case_type: "bad", language: "ar", scenario_tag: "branches", source: "ai",
        label: "فرع الروضة", revision: 1, audio_url: null, clip_status: "missing",
      },
    ],
    total: 3,
    limit: 20,
    offset: 0,
  };
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  const requests = [];
  const translations = {
    "أنا عميلة الهدية": "我是礼遇客户。",
    "اختر اللغة": "请选择语言。",
    "أنا عميلة ذهبية": "我是黄金客户。",
    "فرع العليا": "欧拉亚分行。",
    "فرع الروضة": "拉达分行。",
    "هذا هو النص التاريخي": "这是历史转写。",
  };
  await page.route(`**/api/evaluation/batches/${batchId}/display-translation`, async (route) => {
    const payload = route.request().postDataJSON();
    requests.push(payload.texts);
    const values = payload.texts.map((text) =>
      text === "فرع الروضة" ? null : translations[text]);
    const failedCount = values.filter((value) => value === null).length;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        translations: values,
        provider: "deepseek",
        model_id: "deepseek-chat",
        ephemeral: true,
        evidence: false,
        partial: failedCount > 0,
        failed_count: failedCount,
      }),
    });
  });
  await page.route(/\/api\/evaluation\/conversations\/CONV-AR-1$/, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        conversation_id: "CONV-AR-1",
        events: [{ event_id: "R2", speaker: "customer", time_s: 1, text: "هذا هو النص التاريخي" }],
      }),
    });
  });

  await page.goto("/evaluation.html");
  await page.getByRole("tab", { name: "中文" }).click();
  expect(requests).toHaveLength(0);
  await page.locator('.nav[data-page="review"]').click();
  await expect(page.locator("#page-review .review")).toContainText("我是礼遇客户。");
  await expect(page.locator("#page-review .review")).toContainText("请选择语言。");
  await expect(page.locator("#page-review .review")).toContainText("我是黄金客户。");
  expect(requests).toHaveLength(1);
  expect(requests[0]).toEqual(["أنا عميلة الهدية", "اختر اللغة", "أنا عميلة ذهبية"]);
  expect(JSON.stringify(requests)).not.toContain("历史转写");

  await page.locator('.nav[data-page="library"]').click();
  await expect(page.locator('#page-library tr[data-benchmark-id="BM-AR-2"]')).toContainText("欧拉亚分行。");
  await expect(page.locator('#page-library tr[data-benchmark-id="BM-AR-3"]')).toContainText("中文对照暂不可用");
  await expect(page.locator("#toast")).toContainText("1 条中文对照暂不可用，其余译文已保留。");
  expect(requests).toHaveLength(2);
  expect(requests[1]).toEqual(["فرع العليا", "فرع الروضة"]);
  await page.locator('#page-library tr[data-benchmark-id="BM-AR-1"] .runtime-sample-detail').click();
  await expect(page.locator("#sample-dialog")).toContainText("这是历史转写。");
  await expect(page.locator("#sample-dialog")).toContainText("我是黄金客户。");
  expect(requests).toHaveLength(3);
  expect(requests[2]).toEqual(["هذا هو النص التاريخي"]);
  await page.locator("#sample-dialog [data-close]").first().click();
  await page.locator('#page-library tr[data-benchmark-id="BM-AR-1"] .runtime-sample-detail').click();
  await expect(page.locator("#sample-dialog")).toContainText("这是历史转写。");
  expect(requests).toHaveLength(3);
});

test("exposes every persisted batch lifecycle state and its next action", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  const base = {
    name: "Lifecycle acceptance",
    context_name: "Riyad Bank branch routing v4",
    input_count: 56,
    stage: "pass_1",
    progress: 37,
    denominator: 381,
    excluded_count: 0,
    suspected_numerator: 12,
    cost: 0.25,
    budget: 10,
    providers: ["soniox"],
    updated_at: "2026-09-17T00:00:00Z",
    version: 1,
    report_type: null,
    review_total: 0,
    review_completed: 0,
    snapshot: {},
  };
  const states = [
    ["READY", "data_ready", "data_ready", "Start evaluation"],
    ["RUNNING", "running", "pass_1", "Pause"],
    ["PAUSED", "paused", "pass_1", "Resume"],
    ["BUDGET", "budget_paused", "pass_2", "Resume"],
    ["FAILED", "partially_failed", "evaluation_asr", "Retry failed resources"],
    ["REVIEW", "awaiting_review", "manual_review", "View task"],
    ["DONE", "completed", "completed", "Evaluation report"],
    ["PARTIAL", "completed_partial", "completed", "Evaluation report"],
  ];
  const now = Date.now();
  bootstrap.batches = states.map(([id, status, stage]) => ({
    ...base,
    id: `EV-${id}`,
    status,
    stage,
    report_type: status.startsWith("completed") ? "final" : null,
    active_operations: id === "RUNNING" ? [
      {
        operation_id: "pass-1-group-1",
        stage: "pass_1",
        provider: "qwen",
        ordinal: 1,
        total: 2,
        started_at: new Date(now - 2_000).toISOString(),
        heartbeat_at: new Date(now).toISOString(),
      },
      {
        operation_id: "pass-1-group-2",
        stage: "pass_1",
        provider: "qwen",
        ordinal: 2,
        total: 2,
        started_at: new Date(now - 32_000).toISOString(),
        heartbeat_at: new Date(now - 25_000).toISOString(),
      },
    ] : [],
    snapshot: id === "BUDGET" ? {
      execution_status: {
        pass_2: { completed: 11, failed: 30, pending: 3, finished: 41, total: 44 },
      },
      pass_2_request_status: {
        completed: 1, failed: 2, pending: 2, attempts: 17, total: 5, superseded: 2,
      },
      pass_2_good_status: { completed: 6, failed: 0, pending: 0, finished: 6, total: 6 },
    } : {},
  }));
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  await page.goto("/evaluation.html");
  for (const [id, , , action] of states) {
    const row = page.locator(`tr[data-batch-id="EV-${id}"]`);
    await expect(row).toBeVisible();
    await expect(row.getByRole("button", { name: action })).toHaveCount(1);
  }
  const retryState = page.locator('tr[data-batch-id="EV-BUDGET"] .batch-progress-copy');
  await expect(retryState).toHaveText("30 failed · 11 succeeded");
  await expect(retryState).not.toContainText("pending");
  await expect(retryState).not.toContainText("attempts");
  const activeRows = page.locator('tr[data-batch-id="EV-RUNNING"] .runtime-live-operation');
  await expect(activeRows).toHaveCount(2);
  await expect(activeRows.first()).toContainText("Group 1/2 · Waiting for qwen");
  await expect(activeRows.nth(1)).toContainText("Status sync interrupted");
  const elapsed = activeRows.first().locator("time");
  await expect(elapsed).toHaveAttribute("aria-hidden", "true");
  const operationStatus = page.locator("#runtime-operation-status");
  await expect(operationStatus).toContainText("qwen request 1/2 started");
  await expect(operationStatus).toContainText("qwen request 2/2 status sync interrupted");
  const announcement = await operationStatus.textContent();
  const before = await elapsed.textContent();
  await page.waitForTimeout(1_100);
  await expect(elapsed).not.toHaveText(before);
  await expect(operationStatus).toHaveText(announcement);
  await expect(page.locator('tr[data-batch-id="EV-PARTIAL"] .job-state')).toContainText("Completed · partial coverage");
});

test("shows audio-evidence alignment as step four with continuous elapsed time", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  const now = Date.now();
  bootstrap.batches = [{
    id: "EV-ALIGN-LIVE",
    name: "Live alignment",
    context_name: "Riyad Bank branch routing v4",
    status: "running",
    stage: "event_alignment",
    progress: 61,
    input_count: 36,
    denominator: 560,
    excluded_count: 0,
    suspected_numerator: 30,
    cost: 0.86,
    budget: 10,
    providers: ["soniox", "speechmatics", "elevenlabs"],
    updated_at: new Date(now).toISOString(),
    version: 4,
    report_type: null,
    review_total: 0,
    review_completed: 0,
    active_operations: [{
      operation_id: "event_alignment:EAG-live:1",
      stage: "event_alignment",
      provider: "qwen",
      ordinal: 2,
      total: 7,
      started_at: new Date(now - 65_000).toISOString(),
      heartbeat_at: new Date(now).toISOString(),
    }],
    snapshot: {
      candidate_conversation_count: 36,
      execution_status: {
        pass_1: { completed: 82, failed: 0, pending: 0, finished: 82, total: 82 },
        evaluation_asr: { completed: 108, failed: 0, pending: 0, finished: 108, total: 108 },
        event_alignment: { completed: 12, failed: 0, pending: 24, finished: 12, total: 36 },
        pass_2: { completed: 0, failed: 0, pending: 30, finished: 0, total: 30 },
      },
    },
  }];
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  await page.route("**/api/evaluation/batches/EV-ALIGN-LIVE/report", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        report_type: "preliminary",
        payload: {
          candidate_count: 2,
          cases: [
            { conversation_id: "C1", event_id: "E1", decision: "Good Case" },
            { conversation_id: "C2", event_id: "E2", decision: "Bad Case" },
          ],
        },
      }),
    });
  });
  await page.goto("/evaluation.html");
  await page.locator('tr[data-batch-id="EV-ALIGN-LIVE"] .runtime-open-batch').click();

  const steps = page.locator("#page-run > .steps > .step");
  await expect(steps).toHaveCount(6);
  await expect(steps.nth(3)).toContainText("4 音频与证据对齐");
  await expect(steps.nth(3)).toContainText("Evidence group 2/7 · Waiting for qwen");
  await expect(steps.nth(3).locator("time")).toHaveText(/01:0[5-9]/);
  await expect(steps.nth(4)).toContainText("2/2 unique Cases completed");
  await expect(steps.nth(2)).not.toContainText("qwen");
  const providerRows = page.locator("#page-run > article.card").first().locator("tbody tr");
  await expect(providerRows).toHaveCount(3);
  await expect(providerRows.nth(0).locator("td").nth(2)).toHaveText("36");
  await expect(providerRows.nth(1).locator("td").nth(2)).toHaveText("36");
  await expect(providerRows.nth(2).locator("td").nth(2)).toHaveText("36");
  const overflow = await page.locator("#page-run").evaluate((node) => node.scrollWidth - node.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("confirms finishing an incomplete batch with current results", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  bootstrap.batches = [{
    id: "EV-FINISH-CURRENT",
    name: "Finish current results",
    context_name: "Riyad Bank branch routing v4",
    status: "paused",
    stage: "evaluation_asr",
    progress: 53,
    input_count: 56,
    denominator: 381,
    excluded_count: 0,
    suspected_numerator: 17,
    cost: 1.25,
    budget: 10,
    providers: ["soniox", "speechmatics", "elevenlabs"],
    updated_at: "2026-09-22T00:00:00Z",
    version: 8,
    report_type: "preliminary",
    result_disposition: "formal",
    review_total: 7,
    review_completed: 3,
    snapshot: {
      execution_status: {
        pass_2: { completed: 17, failed: 0, pending: 4, finished: 17, total: 21 },
      },
    },
  }];
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  const finalReport = {
    report_id: "EV-FINISH-CURRENT-R2",
    report_type: "final_partial",
    payload: {
      batch_id: "EV-FINISH-CURRENT",
      batch_name: "Finish current results",
      context_name: "Riyad Bank branch routing v4",
      report_type: "final_partial",
      completion_mode: "current_results",
      partial_coverage: true,
      input_conversations: 56,
      valid_user_events: 381,
      candidate_count: 21,
      suspected_count: 7,
      suspected_rate: 1.84,
      review_total: 7,
      review_completed: 3,
      review_pending: 4,
      benchmark_count: 10,
      result_excluded_count: 4,
      incomplete_case_count: 4,
      excluded_reasons: [{ reason: "unreviewed", count: 4 }],
      decision_counts: { "Good Case": 3, "Bad Case": 7, "Not completed": 4 },
      proposed_tags: [],
      production_asr_observations: [],
      cases: [],
    },
  };
  let completionRequest;
  await page.route("**/api/evaluation/batches/EV-FINISH-CURRENT/complete-with-current-results", async (route) => {
    completionRequest = route.request().postDataJSON();
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(finalReport) });
  });
  await page.route("**/api/evaluation/batches/EV-FINISH-CURRENT/report", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(finalReport) });
  });
  await page.goto("/evaluation.html");
  await page.getByRole("button", { name: "Use current results" }).click();

  const dialog = page.getByRole("dialog", { name: "Finish with current results?" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("Completed Pass 2 decisions");
  await expect(dialog).toContainText("does not call ASR or LLM services");
  await expect(dialog.getByText("17", { exact: true })).toBeVisible();
  const overflow = await dialog.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);
  await dialog.getByRole("button", { name: "Finish with current results" }).click();
  await expect(page.locator("#page-report .eyebrow")).toHaveText(
    "Final report · partial coverage",
  );
  await expect(page.locator("#runtime-partial-results-note")).toContainText(
    "persisted results only",
  );
  await expect(page.locator("#runtime-partial-results-note")).toContainText("Unreviewed: 4");
  expect(completionRequest.expected_version).toBe(8);
});

test("keeps a completed batch completed while offering a scoped coverage retry", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  bootstrap.batches = [{
    id: "EV-PASS2-FAILED",
    name: "Coverage exclusions",
    context_name: "Riyad Bank branch routing v4",
    input_count: 56,
    status: "completed",
    stage: "completed",
    progress: 100,
    denominator: 381,
    excluded_count: 3,
    suspected_numerator: 7,
    cost: 0.25,
    budget: 10,
    providers: ["speechmatics"],
    updated_at: "2026-09-17T00:00:00Z",
    version: 8,
    report_type: "preliminary",
    review_total: 0,
    review_completed: 0,
    active_operations: [],
    snapshot: { coverage: { eligible: 7, excluded: 3 } },
  }];
  let actionRequest;
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  await page.route("**/api/evaluation/batches/EV-PASS2-FAILED/retry-plan", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({
      plan_hash: "a".repeat(64),
      eligible_items: [{ stage: "pass2", key: ["C-1", "R1"] }],
      skipped_items: [{ stage: "case_asr", key: ["speechmatics", "C-2", "R2"] }],
      unknown_usage_usd: 0.25,
      hard_budget_remaining_usd: 9.5,
      estimated_max_retry_cost_usd: 9.5,
    }) });
  });
  await page.route("**/api/evaluation/batches/EV-PASS2-FAILED/actions", async (route) => {
    actionRequest = route.request().postDataJSON();
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({
      ...bootstrap.batches[0], status: "running", stage: "pass_2", version: 9,
    }) });
  });
  let confirmationMessage = "";
  page.on("dialog", (dialog) => {
    confirmationMessage = dialog.message();
    dialog.accept();
  });
  await page.goto("/evaluation.html");
  const row = page.locator('tr[data-batch-id="EV-PASS2-FAILED"]');
  await expect(row.locator(".job-state")).toContainText("Completed");
  await expect(row.getByRole("button", { name: "Evaluation report" })).toHaveCount(1);
  await row.getByRole("button", { name: "Improve excluded coverage" }).click();
  await expect.poll(() => actionRequest).toBeTruthy();
  expect(confirmationMessage).toContain("Maximum additional cost: $9.50");
  expect(actionRequest.retry_plan_hash).toBe("a".repeat(64));
  await expect(row.getByRole("button", { name: "Delete" })).toHaveCount(1);
});

test("renders active source, selected report, and global Benchmark as separate scopes", async ({ page }) => {
  const bootstrap = await (await page.request.get("/api/evaluation/bootstrap")).json();
  bootstrap.batches = [];
  bootstrap.summary = {
    ...bootstrap.summary,
    batch_count: 6,
    pending_reviews: 3,
    pending_conversations: 2,
    source_issue_count: 0,
    active_source: {
      scope: "active_source",
      dataset_id: "dataset-active-82",
      conversation_count: 82,
    },
    selected_report: {
      scope: "selected_report",
      batch_id: "EV-HISTORICAL-REPORT",
      suspected_rate: 12.5,
      suspected_numerator: 5,
      valid_user_events: 40,
    },
    benchmark_library: {
      scope: "global_benchmark_library",
      benchmark_count: 17,
      ai_count: 10,
      manual_count: 7,
    },
  };
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(bootstrap) });
  });
  await page.goto("/evaluation.html");
  const metrics = page.locator("#page-batches .grid4 .metric");
  await expect(metrics.nth(0)).toContainText("82 source conversations available");
  await expect(metrics.nth(0)).toContainText("dataset-active-82");
  await expect(metrics.nth(2)).toContainText("12.5");
  await expect(metrics.nth(2)).toContainText("5 / 40 valid user events");
  await expect(metrics.nth(2)).toContainText("EV-HISTORICAL-REPORT");
  await expect(metrics.nth(3)).toContainText("17");
  await expect(metrics.nth(3)).toContainText("10 AI · 7 manual · global library");
});

test("replaces prototype rows with explicit loading and API error states", async ({ page }) => {
  let releaseBootstrap;
  const waitForRelease = new Promise((resolve) => { releaseBootstrap = resolve; });
  await page.route("**/api/evaluation/bootstrap", async (route) => {
    await waitForRelease;
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "offline" }) });
  });
  const navigation = page.goto("/evaluation.html");
  await expect(page.locator("#page-batches tbody .runtime-empty")).toHaveText("Loading real evaluation data…");
  await expect(page.locator("#page-batches tbody tr[data-batch-id]")).toHaveCount(0);
  releaseBootstrap();
  await navigation;
  await expect(page.locator("#page-batches tbody .runtime-empty")).toContainText("could not be loaded");
  await expect(page.locator("#toast")).toContainText("Local evaluation API is unavailable");
});

test("provides named modal controls, keyboard dismissal, and focus restoration", async ({ page }) => {
  await openRuntime(page);
  const trigger = page.getByRole("button", { name: "New evaluation" });
  await trigger.focus();
  await trigger.press("Enter");
  const dialog = page.getByRole("dialog", { name: "New ASR evaluation" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Batch name")).toBeVisible();
  await expect(dialog.getByLabel("Evaluation context")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Close dialog" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  await expect(page.locator("#toast")).toHaveAttribute("role", "status");
  await expect(page.locator("#toast")).toHaveAttribute("aria-live", "polite");
});
