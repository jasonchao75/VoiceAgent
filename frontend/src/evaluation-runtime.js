import "./evaluation-runtime.css";

const runtime = {
  bootstrap: null,
  selectedBatchId: null,
  selectedReviewId: null,
  reviewBatchId: null,
  selectedBenchmarkIds: new Set(),
  benchmarkItems: new Map(),
  benchmarkResult: null,
  benchmarkOffset: 0,
  benchmarkTotal: 0,
  activeBenchmarkId: null,
  pendingDeleteBenchmarkId: null,
  audio: null,
  reportAudio: null,
  reportAudioButton: null,
  currentReport: null,
  drawerConversation: null,
  displayTranslationCache: new Map(),
  arabicTranslations: new Map(),
  poll: null,
  elapsedPoll: null,
  operationStates: new Map(),
  reviewDirty: false,
  datasetAudit: null,
  datasetCandidateId: null,
  datasetUploading: false,
  newBatchIdempotencyKey: null,
  pricing: { asr: null, llm: null },
  savedPricing: null,
  editingTagId: null,
  pendingDeleteTagId: null,
  pendingDeleteBatchId: null,
  pendingFinishBatchId: null,
  finishMode: "review",
  editingContextId: null,
  editingDictionaryId: null,
  previewContextId: null,
  previewPass: 0,
  previewField: "conversation_history",
  promptHistoryKey: null,
  promptHistory: [],
  selectedPromptVersion: null,
};

function zh() {
  return document.documentElement.lang === "zh-CN";
}

function copy(en, cn) {
  return zh() ? cn : en;
}

function controlledReviewCopy(review) {
  const mappings = {
    branches: [
      "Branch name needs audio confirmation",
      "分行名称需要回听确认",
      "Which branch or city did the customer actually say?",
      "用户实际说的是哪个分行或城市？",
    ],
    numbers: [
      "Branch code needs audio confirmation",
      "分行代码需要回听确认",
      "Which digits or code did the customer actually say?",
      "用户实际说的是哪些数字或代码？",
    ],
    customer_tier: [
      "Customer tier needs audio confirmation",
      "客户类别需要回听确认",
      "Which customer tier did the customer actually say?",
      "用户实际说的是哪个客户类别？",
    ],
    confirmation: [
      "Confirmation or negation needs audio confirmation",
      "确认或否定需要回听确认",
      "What confirmation, negation, or correction did the customer actually say?",
      "用户实际表达了什么确认、否定或纠正？",
    ],
  };
  const fallback = mappings[review.scenario_tag] || [
    "Transcript needs audio confirmation",
    "转写需要回听确认",
    "What did the customer actually say in this event?",
    "用户在该事件中实际说了什么？",
  ];
  const containsCjk = (value) => /[\u3400-\u9fff]/u.test(String(value || ""));
  return {
    issue: zh()
      ? (review.issue_zh || fallback[1])
      : (!review.issue_en || containsCjk(review.issue_en) ? fallback[0] : review.issue_en),
    question: zh()
      ? (review.question_zh || fallback[3])
      : (!review.question_en || containsCjk(review.question_en) ? fallback[2] : review.question_en),
  };
}

function safe(value) {
  const element = document.createElement("span");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

function notify(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.hidden = false;
  window.setTimeout(() => {
    toast.hidden = true;
  }, 3000);
}

function normalizedAsrProvider(value) {
  return String(value || "").trim().toLowerCase().replace("elevenlabs", "elevenlabs");
}

function updateStartRunAvailability() {
  const button = document.querySelector("#start-run");
  if (!button) return;
  const hasProvider = Boolean(document.querySelector(".batch-asr:checked:not(:disabled)"));
  button.disabled = !runtime.datasetAudit?.valid
    || runtime.datasetAudit?.active === false
    || !hasProvider;
}

function renderAsrCapabilities(capabilities = []) {
  const byProvider = new Map(capabilities.map((item) => [item.provider, item]));
  document.querySelectorAll("#batch-resources-card .batch-asr-option").forEach((option) => {
    const input = option.querySelector(".batch-asr");
    const provider = normalizedAsrProvider(option.querySelector("b")?.textContent);
    const capability = byProvider.get(provider);
    const available = Boolean(capability?.available);
    input.dataset.provider = provider;
    input.disabled = !available;
    input.checked = available && input.defaultChecked;
    option.classList.toggle("unavailable", !available);
    option.title = available
      ? copy(`Verified ${capability.verified_at || ""}`, `已验证 ${capability.verified_at || ""}`)
      : copy("Verify this resource before selecting it.", "请先验证该资源后再选择。");
    const detail = option.querySelector("small");
    if (detail && capability) {
      detail.textContent = `${capability.model_id} · ${available
        ? copy("verified", "已验证")
        : capability.status === "unavailable"
          ? copy("unavailable", "不可用")
          : copy("pending verification", "待验证")}`;
    }
  });
  document.querySelectorAll("#sources .source-card").forEach((card) => {
    const provider = normalizedAsrProvider(card.querySelector("h3")?.textContent);
    const capability = byProvider.get(provider);
    if (!capability) return;
    const badge = card.querySelector(".source-head .pill");
    badge.className = `pill ${capability.available ? "good" : capability.status === "unavailable" ? "bad" : "warn"}`;
    badge.textContent = capability.available
      ? copy("Available", "可用")
      : capability.status === "unavailable"
        ? copy("Unavailable", "不可用")
        : copy("Pending verification", "待验证");
    const endpoint = card.querySelector(".async-asr-endpoint");
    endpoint.value = capability.endpoint;
    endpoint.readOnly = true;
    const values = card.querySelectorAll("dd");
    if (values[0]) values[0].textContent = capability.model_id;
    if (values[1]) values[1].textContent = copy(
      "Model and input contract validated locally",
      "模型与输入约束已完成本地校验",
    );
    if (values[2]) values[2].textContent = capability.available
      ? copy(`Endpoint verified · ${capability.verified_at || "—"}`, `Endpoint 已验证 · ${capability.verified_at || "—"}`)
      : copy("Verify in Resource connections", "请在资源连接中验证");
  });
  updateStartRunAvailability();
}

async function testAsrCapability(button) {
  const provider = normalizedAsrProvider(button.dataset.provider);
  button.disabled = true;
  const original = button.textContent;
  button.textContent = copy("Testing…", "测试中…");
  try {
    const result = await json(`/api/evaluation/connections/${provider}/test-and-save`, {
      method: "POST",
      body: {},
    });
    if (!result.success) throw new Error(result.summary || copy("Validation failed", "验证失败"));
    await refreshBootstrap({ quiet: true });
    notify(copy("Async ASR capability verified.", "异步 ASR 能力已验证。"));
  } catch (error) {
    await refreshBootstrap({ quiet: true });
    notify(error.message);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : detail;
    } catch {
      // Keep the safe HTTP status when a response has no JSON body.
    }
    throw new Error(detail);
  }
  return response;
}

async function json(path, options = {}) {
  return (await api(path, options)).json();
}

function selectedPricingModel(row) {
  const provider = row.querySelector(".model-provider")?.value || "";
  const select = row.querySelector(".model-name-select");
  const rawModel = select?.value === "__custom__"
    ? row.querySelector(".custom-model")?.value.trim()
    : select?.value;
  const prefix = `${provider}/`;
  const model = String(rawModel || "").toLowerCase().startsWith(prefix.toLowerCase())
    ? String(rawModel).slice(prefix.length).trim()
    : String(rawModel || "").trim();
  return { provider, model };
}

function formatPrice(value, currency) {
  if (value === null || value === undefined) return "—";
  const amount = Number(value);
  const decimals = amount >= 1 ? 2 : amount >= 0.1 ? 3 : amount >= 0.01 ? 3 : 6;
  const rendered = amount.toFixed(decimals).replace(/0+$/, "").replace(/\.$/, "");
  const minimum = Number(rendered).toFixed(amount >= 0.1 ? 2 : 0);
  const display = amount >= 0.1 && Number(rendered) === Number(minimum) ? minimum : rendered;
  return `${currency === "CNY" ? "¥" : "$"}${display}`;
}

function parsePrice(input) {
  return Number(String(input?.value || "").replace(/[^0-9.]/g, ""));
}

function currentPricingDraft() {
  const saved = runtime.savedPricing?.rates || { asr: [], llm: [] };
  const asrRows = document.querySelectorAll("#page-costs article.card tbody tr");
  const asrRates = [...asrRows].slice(0, 3).map((row) => {
    const [provider, model = ""] = row.cells[0].textContent.split("·").map((item) => item.trim());
    const existing = saved.asr.find((item) => item.provider === provider) || {};
    return {
      ...existing,
      provider,
      model: existing.model || model,
      currency: row.querySelector(".price-input")?.value.trim().startsWith("¥") ? "CNY" : "USD",
      billing_unit: "audio_hour",
      unit_price: parsePrice(row.querySelector(".price-input")),
    };
  });
  const llmRates = [...document.querySelectorAll("#page-costs .pricing-table tbody tr")]
    .map((row) => {
      const { provider, model } = selectedPricingModel(row);
      const existing = saved.llm.find((item) => item.provider === provider && item.model === model) || {};
      const inputs = row.querySelectorAll(".price-input");
      const currency = inputs[0]?.value.trim().startsWith("¥") ? "CNY" : "USD";
      return {
        ...existing,
        provider,
        model,
        currency,
        input_per_1m: parsePrice(inputs[0]),
        cached_input_per_1m: parsePrice(inputs[1]),
        output_per_1m: parsePrice(inputs[2]),
      };
    });
  return { asrRates, llmRates };
}

function applySavedPricingSettings(current) {
  runtime.savedPricing = current;
  const asrRows = [...document.querySelectorAll("#page-costs article.card tbody tr")].slice(0, 3);
  current.rates.asr.forEach((item) => {
    const row = asrRows.find((candidate) => candidate.cells[0].textContent.includes(item.provider));
    if (!row) return;
    row.querySelector(".price-input").value = formatPrice(item.unit_price, item.currency);
    if (item.source_url && item.source_label) row.cells[3].innerHTML = pricingSourceMarkup(item);
  });
  const pricingRows = [...document.querySelectorAll("#page-costs .pricing-table tbody tr")];
  const selections = current.rates.llm_selections?.length
    ? current.rates.llm_selections
    : current.rates.llm.slice(0, pricingRows.length);
  pricingRows.forEach((row, index) => {
    const savedSelection = selections[index];
    if (savedSelection) {
      const providerSelect = row.querySelector(".model-provider");
      const modelSelect = row.querySelector(".model-name-select");
      providerSelect.value = savedSelection.provider;
      providerSelect.dispatchEvent(new Event("change", { bubbles: true }));
      if (![...modelSelect.options].some((option) => option.value === savedSelection.model)) {
        modelSelect.add(new Option(`${savedSelection.provider}/${savedSelection.model}`, savedSelection.model));
      }
      modelSelect.value = savedSelection.model;
    }
    const selection = selectedPricingModel(row);
    const item = current.rates.llm.find((rate) =>
      rate.provider === selection.provider && rate.model === selection.model
    );
    if (!item) return;
    [item.input_per_1m, item.cached_input_per_1m, item.output_per_1m]
      .forEach((value, index) => {
        row.querySelectorAll(".price-input")[index].value = formatPrice(value, item.currency);
      });
    if (item.source_url && item.source_label) row.querySelector(".llm-source").innerHTML = pricingSourceMarkup(item);
  });
}

function pricingSourceMarkup(item) {
  return `<a class="pricing-source-link" href="${safe(item.source_url)}" target="_blank" rel="noreferrer">${safe(item.source_label)}</a><small>${safe(item.currency)} · ${safe(item.model)}</small>`;
}

function renderPricingStatus(scope) {
  const state = runtime.pricing[scope];
  const target = document.querySelector(`#${scope}-sync-status`);
  if (!target) return;
  if (!state) {
    target.textContent = copy("Not synced", "尚未同步");
    return;
  }
  target.textContent = copy("Official prices checked · draft", "官网价格已核对 · 待保存");
  target.title = state.checked_at;
  if (scope === "llm") {
    document.querySelectorAll("#page-costs .pricing-table tbody tr").forEach((row, index) => {
      const item = state.items[index];
      if (item) row.querySelector(".llm-source").innerHTML = pricingSourceMarkup(item);
    });
  }
}

function applyOfficialPricing(scope, payload) {
  if (scope === "asr") {
    const rows = [...document.querySelectorAll("#sync-asr-pricing")]
      .map((button) => button.closest("article"))[0]
      ?.querySelectorAll("tbody tr") || [];
    payload.items.forEach((item) => {
      const row = [...rows].find((candidate) => candidate.cells[0].textContent.includes(item.provider));
      if (!row) return;
      const input = row.querySelector(".price-input");
      input.value = formatPrice(item.unit_price, item.currency);
      input.title = item.note;
      row.cells[3].innerHTML = pricingSourceMarkup(item);
      row.querySelector(".asr-updated").textContent = copy("Just checked", "刚刚核对");
    });
  } else {
    const rows = document.querySelectorAll("#page-costs .pricing-table tbody tr");
    payload.items.forEach((item, index) => {
      const row = rows[index];
      if (!row) return;
      const prices = [item.input_per_1m, item.cached_input_per_1m, item.output_per_1m];
      row.querySelectorAll(".price-input").forEach((input, priceIndex) => {
        input.value = formatPrice(prices[priceIndex], item.currency);
        input.title = item.note;
      });
      row.querySelector(".llm-source").innerHTML = pricingSourceMarkup(item);
    });
  }
  runtime.pricing[scope] = payload;
  renderPricingStatus(scope);
}

function invalidateLlmPricing(row) {
  runtime.pricing.llm = null;
  row.querySelectorAll(".price-input").forEach((input) => {
    input.value = "";
    input.placeholder = copy("Sync required", "需要重新同步");
  });
  renderPricingStatus("llm");
}

async function syncOfficialPricing(scope, button) {
  const body = { scope, selections: [] };
  if (scope === "llm") {
    body.selections = [...document.querySelectorAll("#page-costs .pricing-table tbody tr")]
      .map(selectedPricingModel);
    if (body.selections.some((selection) => !selection.provider || !selection.model)) {
      notify(copy("Choose an exact model for both passes first.", "请先为两轮选择准确的模型。"));
      return;
    }
  }
  const original = button.textContent;
  button.disabled = true;
  button.textContent = copy("Checking official source…", "正在核对官网…");
  try {
    const payload = await json("/api/evaluation/pricing/official", {
      method: "POST",
      body,
    });
    applyOfficialPricing(scope, payload);
    notify(copy(
      "Official list prices were verified and loaded as an unsaved draft.",
      "官网公开价已核对并载入为待保存草稿。",
    ));
  } catch (error) {
    notify(error.message);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function installPricingVersionControls() {
  const form = document.querySelector("#page-costs .cost-form");
  if (!form || document.querySelector("#cny-to-usd-rate")) return;
  const card = document.createElement("article");
  card.className = "card pricing-fx-card";
  card.innerHTML = `<div class="field"><label>${copy("CNY → USD rate", "人民币兑美元汇率")}</label><input class="input" id="cny-to-usd-rate" type="number" min="0.000001" max="1" step="0.000001"></div><div class="field"><label>${copy("Rate source / approval note", "汇率来源 / 审批说明")}</label><input class="input" id="cny-to-usd-source" maxlength="500"></div><p class="muted pricing-fx-version"></p>`;
  form.append(card);
  const budget = form.querySelector("article:first-child .field .input");
  if (budget) budget.id = "default-batch-budget";
  try {
    const current = await json("/api/evaluation/pricing/settings");
    card.querySelector("#cny-to-usd-rate").value = String(current.cny_to_usd);
    card.querySelector("#cny-to-usd-source").value = current.source_note;
    card.querySelector(".pricing-fx-version").textContent = `${copy("Current version", "当前版本")} v${current.version} · ${current.created_at}`;
    if (budget) budget.value = formatPrice(current.default_batch_budget, "USD");
    const batchBudget = document.querySelector("#new-run-dialog .batch-budget-control input");
    if (batchBudget) {
      batchBudget.value = formatPrice(current.default_batch_budget, "USD");
      batchBudget.defaultValue = batchBudget.value;
    }
    applySavedPricingSettings(current);
  } catch (error) {
    card.querySelector(".pricing-fx-version").textContent = error.message;
  }
}

document.addEventListener("evaluation:model-catalog-loaded", () => {
  if (runtime.savedPricing) applySavedPricingSettings(runtime.savedPricing);
});

async function savePricingVersion() {
  const rate = Number(document.querySelector("#cny-to-usd-rate")?.value);
  const sourceNote = document.querySelector("#cny-to-usd-source")?.value.trim();
  const defaultBatchBudget = parsePrice(document.querySelector("#default-batch-budget"));
  const { asrRates, llmRates } = currentPricingDraft();
  const invalidPrices = [...asrRates, ...llmRates].some((item) =>
    Object.entries(item).some(([key, value]) => key.includes("price") || key.includes("per_1m")
      ? !(Number(value) >= 0)
      : false)
  );
  if (!(rate > 0 && rate <= 1) || !sourceNote || !(defaultBatchBudget > 0) || invalidPrices) {
    notify(copy("Enter a valid CNY→USD rate and source note.", "请填写有效的人民币兑美元汇率和来源说明。"));
    return;
  }
  try {
    const saved = await json("/api/evaluation/pricing/settings", {
      method: "POST",
      body: {
        cny_to_usd: rate,
        source_note: sourceNote,
        default_batch_budget: defaultBatchBudget,
        asr_rates: asrRates,
        llm_rates: llmRates,
      },
    });
    applySavedPricingSettings(saved);
    document.querySelector(".pricing-fx-version").textContent = `${copy("Current version", "当前版本")} v${saved.version} · ${saved.created_at}`;
    const savedModels = saved.rates.llm_selections
      .map((item) => `${item.provider}/${item.model}`)
      .join(" · ");
    notify(copy(
      `Pricing saved for ${savedModels}. Previously configured model prices were retained.`,
      `已保存 ${savedModels} 的价格；此前配置的其他模型价格已保留。`,
    ));
  } catch (error) {
    notify(error.message);
  }
}

function idempotency(prefix) {
  return `${prefix}-${crypto.randomUUID()}`;
}

function showPage(name) {
  document.querySelectorAll(".page").forEach((page) => {
    page.classList.toggle("active", page.id === `page-${name}`);
  });
  document.querySelectorAll(".nav").forEach((nav) => {
    nav.classList.toggle("active", nav.dataset.page === name);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function modeBanner(fixture) {
  const environment = document.querySelector(".env");
  if (!environment) return;
  environment.title = copy(
    `Real source files ${fixture.counts.conversation_history}/${fixture.counts.record}/${fixture.counts.user_record}; ASR and LLM results have not been run`,
    `真实来源文件 ${fixture.counts.conversation_history}/${fixture.counts.record}/${fixture.counts.user_record}；尚未运行 ASR 和 LLM`,
  );
}

const STATUS = {
  data_ready: ["blue", "Source imported", "来源已导入"],
  running: ["good", "Running", "进行中"],
  paused: ["warn", "Paused", "已暂停"],
  awaiting_review: ["warn", "Awaiting review", "待人工复核"],
  completed: ["good", "Completed", "已完成"],
  completed_partial: ["blue", "Final · partial", "最终报告 · 部分覆盖"],
  partially_failed: ["bad", "Partially failed", "部分失败"],
  budget_paused: ["warn", "Budget paused", "预算暂停"],
  stopped: ["", "Stopped", "已停止"],
};

const SEEDED_DISPLAY_COPY = {
  "本地验收模拟 · 56通": ["Local acceptance simulation · 56 calls", "本地验收模拟 · 56通"],
  "RiyadBank · 9月抽检": ["RiyadBank · September sampling", "RiyadBank · 9月抽检"],
  "RiyadBank · 8月回归": ["RiyadBank · August regression", "RiyadBank · 8月回归"],
  多语种回归: ["Multilingual regression", "多语种回归"],
  分行代码冒烟测试: ["Branch code smoke test", "分行代码冒烟测试"],
  "利雅得银行分行转接 v3": ["Riyad Bank branch routing v3", "利雅得银行分行转接 v3"],
  "利雅得银行分行转接 v2": ["Riyad Bank branch routing v2", "利雅得银行分行转接 v2"],
  "利雅得银行分行转接 v1": ["Riyad Bank branch routing v1", "利雅得银行分行转接 v1"],
  "多语种服务路由 v1": ["Multilingual service routing v1", "多语种服务路由 v1"],
};

const RUN_CASE_COPY = [
  {
    issue: ["Customer tier recognition", "客户类别识别"],
    priority: ["P1 · May affect routing", "P1 · 可能影响路由"],
  },
  {
    issue: ["Branch-code confirmation", "分行代码确认"],
    priority: ["P1 · May affect routing", "P1 · 可能影响路由"],
  },
  {
    issue: ["Branch-code conflict", "分行代码冲突"],
    priority: ["P1 · May affect routing", "P1 · 可能影响路由"],
  },
];

function seededDisplay(value) {
  const localized = SEEDED_DISPLAY_COPY[value];
  if (localized) return copy(localized[0], localized[1]);
  const seededContext = String(value || "").match(/^利雅得银行分行转接\s+(v\d+)$/u);
  if (seededContext) {
    return copy(`Riyad Bank branch routing ${seededContext[1]}`, value);
  }
  return value;
}

function localizeRunCases(page) {
  const rows = page.querySelectorAll("article.card:nth-of-type(2) tbody tr");
  rows.forEach((row, index) => {
    const localized = RUN_CASE_COPY[index];
    if (!localized) return;
    const cells = row.querySelectorAll("td");
    if (cells.length >= 5) {
      cells[1].textContent = copy(localized.issue[0], localized.issue[1]);
      cells[4].textContent = copy(localized.priority[0], localized.priority[1]);
    }
  });
}

function batchAction(batch) {
  if (batch.result_disposition === "audit_only") {
    return ["open", copy("View audit evidence", "查看审计证据")];
  }
  if (batch.status === "data_ready") return ["start", copy("Start evaluation", "开始评测")];
  if (batch.status === "running") return ["pause", copy("Pause", "暂停")];
  if (["paused", "budget_paused"].includes(batch.status)) {
    return ["resume", copy("Resume", "恢复")];
  }
  if (batch.status === "partially_failed") {
    return ["retry_failed", copy("Retry failed resources", "重试失败资源")];
  }
  if (batch.status === "awaiting_review") {
    return ["open", copy("View task", "查看任务")];
  }
  if (batch.status === "completed_partial" && Number(batch.snapshot?.pass_2_failed || 0) > 0) {
    return ["retry_failed", copy("Retry failed resources", "重试失败资源")];
  }
  if (["completed", "completed_partial"].includes(batch.status)) {
    return ["report", copy("Evaluation report", "评测报告")];
  }
  return ["open", copy("View", "查看")];
}

function renderSummary(summary) {
  const metrics = document.querySelectorAll("#page-batches .grid4 .metric");
  if (metrics.length < 4) return;
  metrics[0].querySelector("strong").textContent = summary.batch_count;
  metrics[0].querySelector("small").textContent = `${summary.conversation_count} ${copy("source conversations available", "通来源对话可用")}`;
  metrics[1].querySelector("strong").textContent = summary.pending_reviews;
  metrics[1].querySelector("small").textContent = `${copy("From", "来自")} ${summary.pending_conversations} ${copy("conversations", "通对话")}`;
  metrics[2].querySelector("strong").textContent = summary.suspected_rate ?? "—";
  metrics[2].querySelector("small").textContent = summary.suspected_rate
    ? `${summary.suspected_numerator} / ${summary.valid_user_events} ${copy("valid user events", "个有效用户事件")}`
    : `${summary.source_issue_count} ${copy("source issues; evaluation not run", "个来源问题；尚未评测")}`;
  metrics[3].querySelector("strong").textContent = summary.benchmark_count;
  metrics[3].querySelector("small").textContent = `${summary.benchmark_ai_count} ${copy("AI", "AI 标注")} · ${summary.benchmark_manual_count} ${copy("manual", "人工标注")}`;
  const reviewCount = document.querySelector(".review-count");
  reviewCount.textContent = summary.pending_reviews;
  reviewCount.hidden = Number(summary.pending_reviews) === 0;
}

function executionProgressCopy(batch, stage = batch.stage) {
  const state = batch.snapshot?.execution_status?.[stage];
  if (!state) {
    return batch.status === "running" && stage === batch.stage
      ? copy("Waiting for the first completed item", "正在等待首个任务完成")
      : "";
  }
  if (stage === "pass_2") {
    const requests = batch.snapshot?.pass_2_request_status;
    const plan = batch.snapshot?.pass_2_plan;
    const requestTotal = Number(requests?.total ?? plan?.request_group_count ?? 0);
    const requestCopy = requestTotal
      ? ` · ${Number(requests?.completed || 0)} ${copy("request groups succeeded", "个请求组成功")} · ${Number(requests?.failed || 0)} ${copy("failed", "失败")} · ${Number(requests?.pending || 0)} ${copy("pending", "待处理")}`
      : "";
    const failed = Number(state.failed || 0);
    const pending = Number(state.pending ?? Math.max(0, Number(state.total || 0) - Number(state.finished || 0)));
    const attempts = Number(requests?.attempts || 0);
    const controls = batch.snapshot?.pass_2_good_status;
    const controlCopy = Number(controls?.total || 0)
      ? ` · ${copy("Good controls", "Good 控制样本")}: ${Number(controls.completed || 0)} ${copy("succeeded", "成功")} · ${Number(controls.failed || 0)} ${copy("failed", "失败")} · ${Number(controls.pending || 0)} ${copy("pending", "待处理")}`
      : "";
    return `${Number(state.completed || 0)} ${copy("suspect Cases succeeded", "个疑点样本成功")} · ${failed} ${copy("failed", "失败")} · ${pending} ${copy("pending", "待处理")}${requestCopy}${attempts ? ` · ${attempts} ${copy("attempts", "次尝试")}` : ""}${controlCopy}`;
  }
  if (stage === "pass_1") {
    const requests = batch.snapshot?.pass_1_request_status;
    const plan = batch.snapshot?.pass_1_plan;
    const requestFinished = Number(requests?.completed || 0) + Number(requests?.failed || 0);
    const requestTotal = Number(requests?.total ?? plan?.request_group_count ?? 0);
    const requestCopy = requestTotal
      ? ` · ${requestFinished}/${requestTotal} ${copy("request groups", "个请求组")}`
      : "";
    const failureCopy = Number(state.failed || 0)
      ? ` · ${state.failed} ${copy("failed", "失败")}`
      : "";
    return `${state.finished}/${state.total} ${copy("conversation checks", "通对话检查")}${requestCopy}${failureCopy}`;
  }
  const unit =
    stage === "evaluation_asr"
      ? copy("jobs", "个任务")
      : copy("items", "项");
  const failed = Number(state.failed || 0);
  const failureCopy = failed ? ` · ${failed} ${copy("failed", "失败")}` : "";
  return `${state.finished}/${state.total} ${unit}${failureCopy}`;
}

function activeOperationRows(batch) {
  if (batch.status !== "running") return "";
  const now = Date.now();
  const operations = Array.isArray(batch.active_operations) ? batch.active_operations : [];
  return operations.map((operation) => {
    const heartbeat = Date.parse(operation.heartbeat_at || "");
    const stale = !Number.isFinite(heartbeat) || now - heartbeat > 20_000;
    const provider = String(operation.provider || "LLM");
    const ordinal = Number(operation.ordinal || 1);
    const total = Number(operation.total || 1);
    const stage = String(operation.stage || "");
    const action = stale
      ? copy("Status sync interrupted", "状态同步中断")
      : stage === "evaluation_asr"
        ? copy(`Call ${ordinal}/${total}`, `对话 ${ordinal}/${total}`)
        : copy(`Group ${ordinal}/${total} · Waiting for ${provider}`, `请求组 ${ordinal}/${total} · 等待 ${provider}`);
    const asrPrefix = stage === "evaluation_asr" ? `${safe(provider)} · ` : "";
    return `<div class="runtime-live-operation ${stale ? "stale" : ""}" data-operation-id="${safe(operation.operation_id)}"><i aria-hidden="true"></i><span>${asrPrefix}${safe(action)}</span><time class="runtime-live-elapsed" data-started-at="${safe(operation.started_at)}" aria-hidden="true">00:00</time></div>`;
  }).join("");
}

function liveOperationsBlock(batch) {
  const rows = activeOperationRows(batch);
  return rows ? `<div class="runtime-live-operations" aria-label="${copy("Current external requests", "当前外部请求")}">${rows}</div>` : "";
}

function announceOperationStateChanges(batches) {
  const region = document.querySelector("#runtime-operation-status");
  if (!region) return;
  const next = new Map();
  const announcements = [];
  batches.forEach((batch) => {
    if (batch.status !== "running") return;
    (batch.active_operations || []).forEach((operation) => {
      const key = `${batch.id}:${operation.operation_id}`;
      const heartbeat = Date.parse(operation.heartbeat_at || "");
      const state = !Number.isFinite(heartbeat) || Date.now() - heartbeat > 20_000
        ? "stale"
        : "active";
      next.set(key, state);
      const previous = runtime.operationStates.get(key);
      if (previous === state) return;
      const provider = String(operation.provider || "LLM");
      const position = `${Number(operation.ordinal || 1)}/${Number(operation.total || 1)}`;
      announcements.push(state === "stale"
        ? copy(`${provider} request ${position} status sync interrupted.`, `${provider} 请求 ${position} 状态同步中断。`)
        : previous === "stale"
          ? copy(`${provider} request ${position} status sync restored.`, `${provider} 请求 ${position} 状态同步已恢复。`)
          : copy(`${provider} request ${position} started.`, `${provider} 请求 ${position} 已开始。`));
    });
  });
  runtime.operationStates.forEach((_state, key) => {
    if (!next.has(key)) announcements.push(copy("External request finished.", "外部请求已结束。"));
  });
  runtime.operationStates = next;
  if (announcements.length) region.textContent = announcements.join(" ");
}

function compactStageSummary(batch) {
  if (!["paused", "budget_paused", "partially_failed"].includes(batch.status)) return "";
  const state = batch.snapshot?.execution_status?.[batch.stage];
  if (!state) return "";
  return `${Number(state.failed || 0)} failed · ${Number(state.completed || 0)} succeeded`;
}

function refreshVisibleElapsedTimes() {
  const now = Date.now();
  document.querySelectorAll(".runtime-live-elapsed[data-started-at]").forEach((node) => {
    const started = Date.parse(node.dataset.startedAt || "");
    const total = Math.max(0, Math.floor((now - started) / 1000));
    if (!Number.isFinite(total)) return;
    node.textContent = `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
  });
}

function renderBatches(batches) {
  const body = document.querySelector("#page-batches tbody");
  if (!batches.length) {
    body.innerHTML = `<tr><td colspan="8"><div class="runtime-empty">${copy(
      "No evaluation results. Import validation must pass before a real ASR/LLM run can start.",
      "暂无评测结果。来源数据校验通过后，才能开始真实 ASR/LLM 运行。",
    )}</div></td></tr>`;
    return;
  }
  body.innerHTML = batches
    .map((batch) => {
      const auditOnly = batch.result_disposition === "audit_only";
      const status = auditOnly
        ? ["warn", "Audit only", "仅审计"]
        : batch.status === "completed_partial" && batch.report_type === "preliminary"
          ? ["bad", "Automated stage partially failed", "自动评测部分失败"]
        : STATUS[batch.status] || ["", batch.status, batch.status];
      const [action, actionLabel] = batchAction(batch);
      const suspect = batch.denominator && batch.suspected_numerator != null
        ? `${batch.suspected_numerator} / ${batch.denominator} · ${(
            (batch.suspected_numerator / batch.denominator) *
            100
          ).toFixed(1)}%`
        : "—";
      const progress = auditOnly
        ? ""
        : ["data_ready", "running", "paused", "budget_paused", "partially_failed"].includes(batch.status)
        ? ` · ${batch.progress}%`
        : batch.status === "awaiting_review"
          ? ` · ${batch.review_total - batch.review_completed}`
          : "";
      const progressBar = `<div class="batch-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${batch.progress}"><i style="width:${batch.progress}%"></i></div>`;
      const liveOperations = liveOperationsBlock(batch);
      const compactSummary = compactStageSummary(batch);
      const canInspect = ["running", "paused", "budget_paused", "partially_failed"].includes(batch.status);
      const reportAction = !auditOnly && batch.report_type
        ? `<button class="btn small runtime-batch-action" data-action="report" data-version="${batch.version}">${copy("Evaluation report", "评测报告")}</button>`
        : "";
      const partialResultsAction = !auditOnly && ["partially_failed", "budget_paused", "stopped"].includes(batch.status)
        ? `<button class="btn small runtime-batch-action" data-action="partial_results" data-version="${batch.version}">${copy("Partial results", "查看部分结果")}</button>`
        : "";
      const finishCurrentAction = !auditOnly
        && ["paused", "partially_failed"].includes(batch.status)
        && batch.report_type
        ? `<button class="btn small danger runtime-finish-current" data-version="${batch.version}">${copy("Use current results", "使用现有结果结束")}</button>`
        : "";
      const inspectAction = canInspect && !auditOnly
        ? `<button class="btn small runtime-open-batch">${copy("View task", "查看任务")}</button>`
        : "";
      const canDelete = auditOnly || ["failed", "partially_failed", "stopped", "awaiting_review", "completed", "completed_partial"].includes(batch.status);
      const deleteAction = canDelete
        ? `<button class="btn small danger runtime-delete-batch" data-version="${batch.version}">${copy("Delete", "删除")}</button>`
        : "";
      const primaryAction = action === "report" && reportAction
        ? ""
        : `<button class="btn small runtime-batch-action ${action === "start" ? "primary" : ""}" data-action="${action}" data-version="${batch.version}">${actionLabel}</button>`;
      const actions = `${inspectAction}${reportAction}${partialResultsAction}${primaryAction}${finishCurrentAction}${deleteAction}`;
      return `<tr data-batch-id="${safe(batch.id)}"><td><b>${safe(seededDisplay(batch.name))}</b><br><span class="muted">${safe(batch.id)}</span></td><td>${safe(seededDisplay(batch.context_name))}</td><td>${batch.input_count} ${copy("calls", "通")}</td><td><span class="pill ${status[0]} job-state">${copy(status[1], status[2])}${progress}</span>${progressBar}${liveOperations}${compactSummary ? `<small class="batch-progress-copy">${safe(compactSummary)}</small>` : ""}</td><td>${suspect}</td><td>$${batch.cost.toFixed(2)} / $${batch.budget.toFixed(2)}</td><td>${new Date(batch.updated_at).toLocaleString()}</td><td><div class="batch-actions">${actions}</div></td></tr>`;
    })
    .join("");
}

function stageIndex(stage) {
  return {
    data_ready: 0,
    validating: 0,
    pass_1: 1,
    evaluation_asr: 2,
    pass_2: 3,
    manual_review: 4,
    completed: 5,
  }[stage] ?? 0;
}

function renderRun(batch) {
  if (!batch) return;
  runtime.selectedBatchId = batch.id;
  const page = document.querySelector("#page-run");
  page.querySelector(".eyebrow").textContent = batch.id;
  page.querySelector("h1").textContent = seededDisplay(batch.name);
  const auditOnly = batch.result_disposition === "audit_only";
  page.querySelector(".page-head p:last-child").textContent = auditOnly
    ? `${batch.input_count} ${copy("calls", "通")} · ${copy("Audit-only evidence; excluded from formal reports, metrics, reviews, Benchmarks, and acceptance evidence", "仅保留审计证据；不进入正式报告、指标、人工复核、Benchmark 或验收证据")}`
    : `${batch.input_count} ${copy("calls", "通")} · ${seededDisplay(batch.context_name)} · ${copy("frozen snapshot", "配置快照已冻结")}`;
  page.querySelector(".runtime-failure-notice")?.remove();
  const failure = batch.snapshot?.execution_failure;
  if (batch.status === "partially_failed" && failure?.message) {
    page.querySelector(".page-head").insertAdjacentHTML(
      "afterend",
      `<div class="notice runtime-failure-notice" role="alert"><b>${copy("Evaluation stopped", "评测已停止")}</b><br>${safe(failure.message)}<br><small>${copy("Stage", "阶段")}: ${safe(failure.stage || "unknown")} · ${copy("Category", "类别")}: ${safe(failure.category || "evaluation_error")}</small></div>`,
    );
  }
  const steps = page.querySelectorAll(".steps .step");
  const activeIndex = stageIndex(batch.stage);
  steps.forEach((step, index) => {
    step.querySelector(".runtime-live-operations")?.remove();
    step.classList.toggle("done", batch.status === "data_ready" ? index === 0 : index < activeIndex);
    step.classList.toggle("current", batch.status !== "data_ready" && index === activeIndex);
    const detail = step.querySelector("span");
    if (!detail) return;
    const progressDetails = [
      `${batch.input_count} ${copy("conversations", "通对话")} · ${batch.denominator} ${copy("customer events parsed", "条用户事件已解析")}`,
      executionProgressCopy(batch, "pass_1"),
      executionProgressCopy(batch, "evaluation_asr"),
      executionProgressCopy(batch, "pass_2"),
      batch.review_total
        ? `${batch.review_completed}/${batch.review_total} ${copy("reviewed", "已复核")}`
        : "",
    ];
    detail.textContent = progressDetails[index] || copy("Not run", "尚未运行");
    if (index === activeIndex) {
      const live = liveOperationsBlock(batch);
      if (live) step.insertAdjacentHTML("beforeend", live);
    }
  });
  const metrics = page.querySelectorAll(".grid4 .metric");
  metrics[0].querySelector("strong").textContent = batch.denominator || "—";
  metrics[0].querySelector("small").textContent = copy(
    "Parsed from the uploaded Excel files",
    "来自上传 Excel 的真实解析",
  );
  const candidateCount = batch.snapshot?.candidate_event_count ?? batch.suspected_numerator;
  metrics[1].querySelector("strong").textContent = candidateCount ?? "—";
  metrics[1].querySelector("small").textContent = batch.stage === "pass_1"
    ? copy("Real first-pass analysis is running", "真实第一轮分析进行中")
    : copy("Persisted first-pass candidates", "已持久化的第一轮候选");
  const automaticCount = batch.snapshot?.benchmark_count;
  metrics[2].querySelector("strong").textContent = automaticCount ?? "—";
  metrics[2].querySelector("small").textContent = batch.stage === "pass_2"
    ? copy("Real evidence decisions are running", "真实证据判定进行中")
    : copy("Persisted automatic decisions", "已持久化的自动判定");
  metrics[3].querySelector("strong").textContent = batch.review_total || "—";
  metrics[3].querySelector("small").textContent = copy(
    "Cases requiring audio review",
    "需要人工回听的 Case",
  );
  const actions = page.querySelector(".page-head .actions");
  actions.innerHTML = "";
  const [action, label] = batchAction(batch);
  if (!auditOnly && ["pause", "resume", "retry_failed"].includes(action)) {
    actions.insertAdjacentHTML(
      "beforeend",
      `<button class="btn runtime-run-action" data-action="${action}" data-version="${batch.version}">${label}</button>`,
    );
  }
  if (
    !auditOnly &&
    batch.status === "awaiting_review" &&
    batch.progress >= 92 &&
    batch.providers.includes("elevenlabs")
  ) {
    actions.insertAdjacentHTML(
      "beforeend",
      `<button class="btn runtime-run-action" data-action="retry_failed" data-version="${batch.version}">${copy("Retry failed resources", "重试失败资源")}</button>`,
    );
  }
  if (!auditOnly && batch.status === "awaiting_review" && batch.review_total > batch.review_completed) {
    actions.insertAdjacentHTML(
      "beforeend",
      `<button class="btn runtime-open-review">${copy("Open manual review", "进入人工复核")}</button>`,
    );
  }
  if (
    !auditOnly
    && ["paused", "partially_failed"].includes(batch.status)
    && batch.report_type
  ) {
    actions.insertAdjacentHTML(
      "beforeend",
      `<button class="btn danger runtime-finish-current" data-version="${batch.version}">${copy("Use current results", "使用现有结果结束")}</button>`,
    );
  }
  if (!auditOnly && batch.report_type) {
    actions.insertAdjacentHTML(
      "afterbegin",
      `<button class="btn runtime-run-report" data-batch-id="${safe(batch.id)}">${copy("Evaluation report", "评测报告")}</button>`,
    );
  }
  const providerCard = page.querySelector("article.card");
  const providerRows = providerCard?.querySelectorAll("tbody tr") || [];
  const providerSummary = providerCard?.querySelector(".card-title > p, .card-title p");
  if (providerSummary) {
    providerSummary.textContent = copy(
      "Evaluation resources only, not production streaming ASR.",
      "仅用于评测，不是线上流式 ASR。",
    );
  }
  const providerCost = providerCard?.querySelector(".card-title > .pill");
  if (providerCost) {
    providerCost.textContent = `${copy("Cost", "成本")} $${batch.cost.toFixed(2)} / $${batch.budget.toFixed(2)}`;
  }
  providerRows.forEach((row, index) => {
    if (index >= batch.providers.length) {
      row.hidden = true;
      return;
    }
    row.hidden = false;
    const cells = row.querySelectorAll("td");
    if (cells.length >= 6) {
      const jobs = batch.snapshot?.candidate_conversation_count;
      cells[2].textContent = jobs ?? "—";
      cells[3].textContent = ["pass_2", "manual_review", "completed"].includes(batch.stage)
        ? jobs ?? "—"
        : "—";
      cells[4].textContent = "—";
      const action = cells[6]?.querySelector("button");
      if (action) action.hidden = true;
    }
    const status = row.querySelector(".pill");
    const asrStarted = ["evaluation_asr", "pass_2", "manual_review", "completed"].includes(batch.stage);
    const asrDone = ["pass_2", "manual_review", "completed"].includes(batch.stage);
    status.className = `pill ${asrDone ? "good" : asrStarted ? "blue" : ""}`;
    status.textContent = asrDone
      ? copy("Completed", "已完成")
      : asrStarted
        ? copy("Running", "进行中")
        : copy("Not run", "尚未运行");
  });
  const candidateBody = page.querySelector("article.card:nth-of-type(2) tbody");
  if (candidateBody) {
    candidateBody.innerHTML = `<tr><td colspan="6"><div class="runtime-empty">${copy(
      "Loading persisted candidate results…",
      "正在加载已持久化的候选结果…",
    )}</div></td></tr>`;
  }
  void refreshRunReport(batch.id);
  void refreshBatchCosts(batch.id);
}

async function refreshRunReport(batchId) {
  const body = document.querySelector("#page-run article.card:nth-of-type(2) tbody");
  if (!body) return;
  try {
    const batch = runtime.bootstrap?.batches.find((item) => item.id === batchId);
    const auditOnly = batch?.result_disposition === "audit_only";
    const endpoint = auditOnly
      ? "audit-evidence"
      : batch?.report_type
        ? "report"
        : ["partially_failed", "budget_paused", "stopped"].includes(batch?.status)
          ? "partial-results"
          : "report";
    const report = await json(
      `/api/evaluation/batches/${encodeURIComponent(batchId)}/${endpoint}`,
    );
    if (runtime.selectedBatchId !== batchId) return;
    const actions = document.querySelector("#page-run .page-head .actions");
    if (!auditOnly && actions && !actions.querySelector(".runtime-run-report")) {
      actions.insertAdjacentHTML(
        "afterbegin",
        `<button class="btn runtime-run-report" data-batch-id="${safe(batchId)}">${copy("Evaluation report", "评测报告")}</button>`,
      );
    }
    if (batch && !auditOnly) batch.report_type = report.report_type;
    const cases = report.payload?.cases || [];
    const rawCandidates = Number(batch?.snapshot?.candidate_event_count ?? batch?.suspected_numerator ?? 0);
    const uniqueCandidates = Number(report.payload?.candidate_count ?? cases.length);
    const duplicateCandidates = Math.max(0, rawCandidates - uniqueCandidates);
    const metrics = document.querySelectorAll("#page-run .grid4 .metric");
    if (metrics.length >= 2) {
      metrics[1].querySelector("strong").textContent = uniqueCandidates;
      metrics[1].querySelector("small").textContent = duplicateCandidates
        ? `${copy("Unique candidate events", "个唯一候选事件")} · ${duplicateCandidates} ${copy("duplicate rows removed", "条重复候选已去重")}`
        : copy("Unique persisted first-pass candidates", "已持久化的唯一第一轮候选");
    }
    const secondPassDetail = document.querySelector("#page-run .steps .step:nth-child(4) span");
    if (secondPassDetail) {
      const incomplete = cases.filter((item) => item.decision === "Not completed").length;
      secondPassDetail.textContent = `${cases.length - incomplete}/${cases.length} ${copy("unique Cases completed", "个唯一样本已完成")}${incomplete ? ` · ${incomplete} ${copy("failed", "失败")}` : ""}${duplicateCandidates ? ` · ${duplicateCandidates} ${copy("duplicates removed", "条重复已去除")}` : ""}`;
    }
    body.innerHTML = cases.length
      ? cases.map((item) => {
          const decisionClass = item.decision === "Bad Case"
            ? "bad"
            : item.decision === "Good Case"
              ? "good"
              : item.decision === "Not completed"
                ? ""
                : "warn";
          const playback = item.audio_available
            ? `<button class="btn small runtime-report-audio" data-conversation-id="${safe(item.conversation_id)}" data-start="${Number(item.audio_start_s)}" data-end="${Number(item.audio_end_s)}">▶ ${formatTime(Number(item.audio_start_s))} – ${formatTime(Number(item.audio_end_s))}</button>`
            : `<span class="muted">${copy("Unavailable", "不可用")}</span>`;
          return `<tr><td><span class="id">${safe(item.conversation_id)} · ${safe(item.event_id)}</span></td><td>${safe(reportTagName(item.scenario_tag))}</td><td>${safe(item.production_transcript)}</td><td><span class="pill ${decisionClass}">${safe(item.decision)}</span></td><td>${safe(item.priority)}</td><td>${playback}</td></tr>`;
        }).join("")
      : `<tr><td colspan="6"><div class="runtime-empty">${copy("No persisted candidate results.", "没有已持久化的候选结果。")}</div></td></tr>`;
  } catch (error) {
    body.innerHTML = `<tr><td colspan="6"><div class="runtime-empty">${copy("Preliminary report is not available.", "初步报告尚不可用。")} ${safe(error.message)}</div></td></tr>`;
  }
}

async function refreshBatchCosts(batchId) {
  try {
    const ledger = await json(`/api/evaluation/batches/${encodeURIComponent(batchId)}/costs`);
    const page = document.querySelector("#page-run");
    const resourceCard = [...page.querySelectorAll("article.card")].find((card) =>
      card.textContent.includes("Async ASR"),
    );
    if (!resourceCard) return;
    let target = resourceCard.querySelector(".runtime-cost-breakdown");
    if (!target) {
      target = document.createElement("div");
      target.className = "runtime-cost-breakdown";
      resourceCard.querySelector(".card-title")?.after(target);
    }
    const asrSeconds = ledger.asr.reduce((sum, item) => sum + Number(item.audio_seconds || 0), 0);
    const asrCost = ledger.asr.reduce((sum, item) => sum + Number(item.estimated_cost || 0), 0);
    const llmCalls = ledger.llm.reduce((sum, item) => sum + Number(item.calls || 0), 0);
    const input = ledger.llm.reduce((sum, item) => sum + Number(item.input_tokens || 0), 0);
    const reasoning = ledger.llm.reduce((sum, item) => sum + Number(item.reasoning_tokens || 0), 0);
    const output = ledger.llm.reduce((sum, item) => sum + Number(item.output_tokens || 0), 0);
    const batch = runtime.bootstrap?.batches.find((item) => item.id === batchId);
    const legacyUsage = !ledger.asr.length && !ledger.llm.length && Number(batch?.cost || 0) > 0;
    target.innerHTML = legacyUsage
      ? `<div><b>${copy("ASR ledger", "ASR 账单")}</b><span>${copy("Usage was not recorded for this legacy run.", "该历史运行未记录用量。")}</span></div><div><b>${copy("LLM ledger", "LLM 账单")}</b><span>${copy("Usage was not recorded for this legacy run.", "该历史运行未记录用量。")}</span><small>${copy("The batch total is retained, but it cannot be truthfully split after the fact.", "批次总成本仍保留，但无法事后真实拆分。")}</small></div>`
      : `<div><b>${copy("ASR ledger", "ASR 账单")}</b><span>${(asrSeconds / 60).toFixed(2)} min · ${copy("estimated", "估算")} $${asrCost.toFixed(4)}</span></div><div><b>${copy("LLM ledger", "LLM 账单")}</b><span>${llmCalls} ${copy("requests", "次请求")} · ${input} input · ${reasoning} reasoning · ${output} output tokens</span><small>${copy("Token usage is actual; money remains supplier-side until a frozen token price is available.", "Token 用量为实际值；冻结 Token 单价可用前，金额以供应商账单为准。")}</small></div>`;
  } catch {
    // Batch rendering remains usable if the optional ledger endpoint is unavailable.
  }
}

function reportTagName(value) {
  const tags = runtime.bootstrap?.scenario_tags || [];
  const match = tags.find((tag) => [tag.name_en, tag.name_zh, tag.tag_key].includes(value));
  if (match) return zh() ? match.name_zh : match.name_en;
  const legacyBilingual = {
    "语言选择": ["Language selection", "语言选择"],
    "语种选择": ["Language selection", "语种选择"],
    "服务诉求": ["Service request", "服务诉求"],
    "服务诉求与转接意图": ["Service request and transfer intent", "服务诉求与转接意图"],
    "服务诉求回答截断或误转写": [
      "Truncated or misrecognized service-request response",
      "服务诉求回答截断或误转写",
    ],
  };
  if (legacyBilingual[value]) return copy(...legacyBilingual[value]);
  return value === "Unclassified (AI suggested)"
    ? copy("Unclassified (AI suggested)", "待归类（AI 建议）")
    : /[\u3400-\u9fff]/u.test(String(value || ""))
      ? copy("Unclassified legacy tag", "未归类历史标签")
      : value;
}

function canonicalReportTag(value) {
  const tags = runtime.bootstrap?.scenario_tags || [];
  const match = tags.find((tag) => [tag.name_en, tag.name_zh, tag.tag_key].includes(value));
  return match?.tag_key || value;
}

function controlledReportReason(item) {
  const reason = String(item.reason || "").trim();
  const containsChinese = /[\u3400-\u9fff]/u.test(reason);
  if ((zh() && containsChinese) || (!zh() && !containsChinese)) return reason;
  const bilingualFallback = {
    "Good Case": [
      "The stored evidence supports the production transcript. Review the linked provider evidence for details.",
      "现有证据支持线上转写；详情请查看关联的厂商识别证据。",
    ],
    "Bad Case": [
      "The stored evidence indicates a meaning-changing transcript mismatch. Review the linked provider evidence for details.",
      "现有证据表明转写存在改变含义的偏差；详情请查看关联的厂商识别证据。",
    ],
    "Needs manual audio review": [
      "Provider evidence is conflicting or incomplete. Listen to the linked audio before deciding.",
      "厂商证据互相冲突或不完整，请回听关联音频后再判定。",
    ],
    "Not completed": [
      "Second-pass evaluation did not complete for this Case.",
      "该 Case 的第二轮评测尚未完成。",
    ],
  };
  return copy(
    bilingualFallback[item.decision]?.[0] || "Review the linked evidence for this Case.",
    bilingualFallback[item.decision]?.[1] || "请查看该 Case 的关联证据。",
  );
}

function reportDecisionName(value) {
  return {
    "Good Case": copy("Good Case", "正确"),
    "Bad Case": copy("Bad Case", "错误"),
    "Needs manual audio review": copy("Needs manual audio review", "需要人工回听"),
    "Not completed": copy("Not completed", "未完成"),
  }[value] || value;
}

function reportLabelStatusName(value) {
  return {
    admitted: copy("Admitted", "已入库"),
    pending: copy("Pending", "待处理"),
    excluded: copy("Excluded", "已排除"),
    unavailable: copy("Unavailable", "不可用"),
    "ai labeled": copy("AI labeled", "AI 标注"),
    "manual labeled": copy("Manual labeled", "人工标注"),
  }[String(value || "").toLowerCase()] || value;
}

function reportConversationLink(conversationId, eventId) {
  return `<button class="conversation-link runtime-conversation-link" type="button" data-conversation-id="${safe(conversationId)}" data-event-id="${safe(eventId)}">${safe(conversationId)}</button> · <span class="muted">${safe(eventId)}</span>`;
}

function renderReport(report) {
  const payload = report.payload;
  const reportCases = Array.isArray(payload.cases) ? payload.cases : [];
  const completedDecisions = new Set(["Good Case", "Bad Case", "Needs manual audio review"]);
  const completedCases = reportCases.filter((item) => completedDecisions.has(item.decision));
  const incompleteCount = reportCases.length - completedCases.length;
  const completedTagCounts = new Map();
  const completedLanguageCounts = new Map();
  completedCases.forEach((item) => {
    const scenarioTag = canonicalReportTag(item.scenario_tag);
    completedTagCounts.set(scenarioTag, (completedTagCounts.get(scenarioTag) || 0) + 1);
    const language = item.language || "unknown";
    completedLanguageCounts.set(language, (completedLanguageCounts.get(language) || 0) + 1);
  });
  const tagDistribution = [...completedTagCounts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((left, right) => right.count - left.count || String(left.name).localeCompare(String(right.name)));
  const languageDistribution = [...completedLanguageCounts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((left, right) => right.count - left.count || String(left.name).localeCompare(String(right.name)));
  runtime.currentReport = report;
  const page = document.querySelector("#page-report");
  const header = page.querySelector(".page-head > div");
  const partialResults = payload.report_type === "partial_results";
  const finalPartial = payload.report_type === "final_partial";
  header.querySelector(".eyebrow").textContent = partialResults
    ? copy("Partial results · not a complete report", "部分结果 · 非完整报告")
    : payload.report_type === "final"
      ? copy("Final report", "最终报告")
      : finalPartial
        ? copy("Final report · partial coverage", "最终报告 · 部分覆盖")
        : copy("Preliminary report", "初步报告");
  header.querySelector("h1").textContent = seededDisplay(payload.batch_name);
  header.querySelector("h1 + p").textContent = partialResults
    ? `${payload.input_conversations} ${copy("calls", "通")} · ${seededDisplay(payload.context_name)} · ${copy("successful checkpoints through", "成功结果截至")} ${payload.failed_stage || "—"}`
    : `${payload.input_conversations} ${copy("calls", "通")} · ${seededDisplay(payload.context_name)} · ${copy("immutable snapshot", "不可变快照")}`;
  page.querySelector("#runtime-partial-results-note")?.remove();
  if (partialResults) {
    const asrFailures = Array.isArray(payload.asr_failures) ? payload.asr_failures : [];
    const casePreparationFailures = Array.isArray(payload.case_preparation_failures)
      ? payload.case_preparation_failures
      : [];
    const asrFailureSummary = asrFailures.length
      ? `<details><summary>${copy("ASR failures", "ASR 失败")} · ${asrFailures.length}</summary><ul>${asrFailures.map((failure) => `<li><b>${safe(failure.provider)}</b> · ${copy("full call", "完整录音")} · ${copy("attempts", "尝试")} ${Number(failure.attempts || 0)} · ${safe(failure.category)} · ${safe(failure.message)} · ${failure.retryable ? copy("retryable", "可重试") : copy("not retryable", "不可重试")}</li>`).join("")}</ul></details>`
      : "";
    const casePreparationFailureSummary = casePreparationFailures.length
      ? `<details><summary>${copy("Case preparation failures", "Case 准备失败")} · ${casePreparationFailures.length}</summary><ul>${casePreparationFailures.map((failure) => `<li><b>${safe(failure.provider)}</b> · ${safe(failure.conversation_id)} / ${safe(failure.event_id)} · ${safe(failure.category)} · ${safe(failure.message)}</li>`).join("")}</ul></details>`
      : "";
    page.querySelector(".page-head").insertAdjacentHTML(
      "afterend",
      `<div class="report-note" id="runtime-partial-results-note">${copy(
        "This view contains only persisted successful work. Missing sections were not run or failed; retrying reuses successful checkpoints. It is not an immutable preliminary or final report.",
        "这里只展示已成功持久化的内容；缺失部分代表尚未运行或执行失败。重试会复用成功检查点，本页不是不可变初步报告或最终报告。",
      )}${payload.failure?.message ? ` ${safe(payload.failure.message)}` : ""}${asrFailureSummary}${casePreparationFailureSummary}</div>`,
    );
  } else if (finalPartial) {
    const exclusionLabels = {
      pass_1_failed_or_unavailable: copy(
        "Pass 1 failed or unavailable",
        "第一轮失败或不可用",
      ),
      unreviewed: copy("Unreviewed", "未复核"),
      unclear_audio: copy("Unclear audio", "听不清"),
      unclippable: copy("Unclippable", "无法可靠裁片"),
      unfinished_or_failed: copy("Unfinished or failed", "未完成或失败"),
    };
    const exclusionSummary = (payload.excluded_reasons || [])
      .filter((item) => Number(item.count || 0) > 0)
      .map((item) => `${exclusionLabels[item.reason] || item.reason}: ${Number(item.count)}`)
      .join(" · ");
    const completionCopy = payload.completion_mode === "current_results"
      ? copy(
        "This immutable final report was finished with persisted results only. No ASR or LLM retry was run.",
        "该不可变最终报告仅使用已持久化结果结束，未执行 ASR 或 LLM 重试。",
      )
      : copy(
        "This immutable final report has partial review coverage.",
        "该不可变最终报告仅覆盖部分人工复核。",
      );
    page.querySelector(".page-head").insertAdjacentHTML(
      "afterend",
      `<div class="report-note" id="runtime-partial-results-note"><b>${copy(
        "Partial coverage",
        "部分覆盖",
      )}</b> · ${safe(completionCopy)} ${copy("Excluded from formal results", "未计入正式结果")}: ${Number(
        payload.result_excluded_count ?? payload.incomplete_case_count ?? 0,
      )}${exclusionSummary ? ` · ${safe(exclusionSummary)}` : ""}</div>`,
    );
  }

  const metrics = page.querySelectorAll(":scope > .grid4 .metric");
  if (metrics.length >= 4) {
    metrics[0].querySelector(".label").textContent = copy("Suspected ASR sentence rate", "疑似 ASR 错误句子占比");
    metrics[0].querySelector("strong").textContent = `${Number(payload.suspected_rate).toFixed(1)}%`;
    metrics[0].querySelector("small").textContent = `${payload.suspected_count} / ${payload.valid_user_events}`;
    metrics[1].querySelector(".label").textContent = copy("Confirmed Bad Cases", "已确认错误样本");
    metrics[1].querySelector("strong").textContent = payload.decision_counts["Bad Case"] || 0;
    metrics[1].querySelector("small").textContent = copy("Automated evidence decisions", "自动证据判定");
    metrics[2].querySelector(".label").textContent = copy("Manual review coverage", "人工复核覆盖率");
    metrics[2].querySelector("strong").textContent = payload.review_total
      ? `${Math.round((payload.review_completed / payload.review_total) * 100)}%`
      : "100%";
    metrics[2].querySelector("small").textContent = `${payload.review_completed} / ${payload.review_total}`;
    metrics[3].querySelector(".label").textContent = copy("Benchmark samples", "Benchmark 样本");
    metrics[3].querySelector("strong").textContent = Number(
      payload.benchmark_count
      ?? (Number(payload.decision_counts["Good Case"] || 0) + Number(payload.decision_counts["Bad Case"] || 0)),
    );
    metrics[3].querySelector("small").textContent = zh()
      ? `${payload.decision_counts["Good Case"] || 0} 正确 · ${payload.decision_counts["Bad Case"] || 0} 错误`
      : `${payload.decision_counts["Good Case"] || 0} Good · ${payload.decision_counts["Bad Case"] || 0} Bad`;
  }

  const funnel = page.querySelector(".funnel");
  if (funnel) {
    const values = [
      [payload.valid_user_events, copy("Valid user sentences", "有效用户句子")],
      [payload.candidate_count, copy("First-pass candidates", "第一轮候选")],
      [completedCases.length, copy("Completed second-pass decisions", "已完成第二轮判定")],
      [payload.suspected_count, copy("Suspected errors", "最终疑似错误")],
    ];
    funnel.innerHTML = values.map(([value, label]) => `<div class="funnel-item"><strong>${value}</strong><span>${label}</span></div>`).join("");
  }

  const tagOverview = page.querySelector("#report-tag-overview");
  if (tagOverview) {
    const max = Math.max(1, ...tagDistribution.map((item) => item.count));
    tagOverview.querySelector(".bar-list").innerHTML = tagDistribution.map((item) => `<div class="bar-row"><span>${safe(reportTagName(item.name))}</span><div class="bar"><i style="width:${Math.round((item.count / max) * 100)}%"></i></div><b>${item.count}</b></div>`).join("");
    const actionList = tagOverview.querySelector(".action-list");
    const proposalGroups = ["acoustic", "semantic"].map((type) => ({
      type,
      proposals: payload.proposed_tags.filter((item) => item.type === type),
    })).filter((group) => group.proposals.length);
    actionList.innerHTML = `${proposalGroups.map((group) => {
      const caseCount = new Set(group.proposals.flatMap((item) => item.case_keys.map((key) => `${key[0]}::${key[1]}`))).size;
      const names = group.proposals.map((item) => safe(zh() ? item.name_zh : item.name_en)).join("；");
      return `<div class="action-item"><h3>${group.type === "acoustic" ? copy("Acoustic candidate tags", "声学候选标签") : copy("Semantic candidate tags", "语义候选标签")}</h3><p>${names} · ${caseCount} ${copy(caseCount === 1 ? "case" : "cases", "条 Case")}</p><div class="actions"><button class="btn small runtime-open-proposed-tags" data-proposal-type="${group.type}">${copy("Review cases & create tag", "查看 Case 并创建标签")}</button></div></div>`;
    }).join("")}${proposalGroups.length ? "" : `<div class="action-item"><h3>${copy("Candidate tags", "候选标签")}</h3><p>${copy("No complete proposed tags in this report.", "本报告没有结构完整的建议标签。")}</p></div>`}<div class="report-note">${copy(
      "Counts come only from this frozen second-pass result. Proposed tags remain unclassified until reviewed.",
      "计数仅来自本次冻结的第二轮结果；建议标签在审核创建前保持待归类。",
    )}</div>`;
  }

  const proposed = page.querySelector("#proposed-tag-details");
  if (proposed) {
    const proposedCaseCount = new Set(
      payload.proposed_tags.flatMap((item) =>
        item.case_keys.map((key) => `${key[0]}::${key[1]}`),
      ),
    ).size;
    const proposedCount = proposed.querySelector(".card-title .pill");
    if (proposedCount) {
      proposedCount.className = `pill ${proposedCaseCount ? "warn" : ""}`.trim();
      proposedCount.textContent = proposedCaseCount
        ? `${proposedCaseCount} ${copy(
            proposedCaseCount === 1 ? "case pending classification" : "cases pending classification",
            "条待归类",
          )}`
        : copy("No complete proposals", "暂无完整建议");
    }
    const body = proposed.querySelector("tbody");
    proposed.querySelector("thead").innerHTML = `<tr><th>${copy("AI-proposed tag and description", "AI 建议标签与描述")}</th><th>${copy("Case", "Case")}</th><th>${copy("Production transcript", "线上转写")}</th><th>${copy("Audio", "试听")}</th><th>${copy("Current group", "当前分组")}</th><th></th></tr>`;
    body.innerHTML = payload.proposed_tags.length
      ? payload.proposed_tags.flatMap((item) => item.case_keys.map((key, index) => {
          const candidate = payload.cases.find((caseItem) => caseItem.conversation_id === key[0] && caseItem.event_id === key[1]);
          const audio = candidate?.audio_available
            ? `<button class="btn small runtime-report-audio" data-conversation-id="${safe(candidate.conversation_id)}" data-start="${Number(candidate.audio_start_s)}" data-end="${Number(candidate.audio_end_s)}">▶ ${safe(candidate.event_id)}</button>`
            : `<span class="muted">${copy("Unavailable", "不可用")}</span>`;
          const createAction = index === 0
            ? `<button class="btn small primary runtime-create-proposed-tag" data-proposal-key="${safe(item.proposal_key)}">${copy(`Create tag & move ${item.case_keys.length}`, `创建标签并移动 ${item.case_keys.length} 条`)}</button>`
            : "";
          return `<tr data-proposed-tag="${safe(item.proposal_key)}" data-proposal-type="${safe(item.type)}"><td><b>${safe(zh() ? item.name_zh : item.name_en)}</b><p class="tag-ai-description">${safe(zh() ? item.description_zh : item.description_en)}</p><span class="pill ${item.type === "acoustic" ? "warn" : "blue"}">${safe(item.type === "acoustic" ? copy("Acoustic", "声学") : copy("Semantic", "语义"))}</span></td><td><span class="id">${reportConversationLink(key[0], key[1])}</span></td><td>${arabicComparisonHtml(payload.batch_id, candidate?.production_transcript || copy("Unavailable", "不可用"))}</td><td>${audio}</td><td><span class="pill">${copy("Unclassified", "待归类")}</span></td><td>${createAction}</td></tr>`;
        })).join("")
      : `<tr><td colspan="6"><div class="runtime-empty">${copy("No complete proposed tags in this report.", "本报告没有结构完整的建议标签。")}</div></td></tr>`;
  }

  const observations = page.querySelector("#production-asr-analysis");
  if (observations) {
    const table = observations.querySelector("table");
    table.querySelector("thead").innerHTML = `<tr><th>${copy("Scenario tag", "场景标签")}</th><th>${copy("Production ASR result", "线上 ASR 结果")}</th><th>${copy("Finding", "本批次观察")}</th><th>${copy("Attention", "关注程度")}</th></tr>`;
    table.querySelector("tbody").innerHTML = tagDistribution.map((item) => {
      const matchingCases = completedCases.filter(
        (candidate) => canonicalReportTag(candidate.scenario_tag) === item.name,
      );
      if (!matchingCases.length) return "";
      const badCount = matchingCases.filter((candidate) => candidate.decision === "Bad Case").length;
      const manualCount = matchingCases.filter((candidate) => candidate.decision === "Needs manual audio review").length;
      const attentionClass = badCount ? "bad" : manualCount ? "warn" : "good";
      const attention = badCount
        ? copy("Needs attention", "需要关注")
        : manualCount
          ? copy("Watch", "持续观察")
          : copy("Performing well", "表现较好");
      const result = zh()
        ? `${matchingCases.length} 条中 ${badCount} 条出现错误`
        : `${badCount} / ${matchingCases.length} cases show errors`;
      const finding = manualCount
        ? copy(`${badCount} confirmed errors; ${manualCount} Cases still need manual review.`, `${badCount} 条已确认错误；另有 ${manualCount} 条仍需人工复核。`)
        : badCount
          ? copy(`${badCount} meaning-changing transcript errors were confirmed in this batch.`, `本批次确认 ${badCount} 条改变含义的转写错误。`)
          : copy("No meaning-changing ASR error was confirmed in this batch.", "本批次未确认改变业务含义的 ASR 错误。");
      return `<tr><td>${safe(reportTagName(item.name))}</td><td>${safe(result)}</td><td>${safe(finding)}</td><td><span class="pill ${attentionClass}">${safe(attention)}</span></td></tr>`;
    }).join("");
  }

  const details = page.querySelector("#batch-case-details");
  if (details) {
    let filter = details.querySelector(".runtime-report-filter");
    if (!filter) {
      const baselineFilter = details.querySelector(".case-detail-filter");
      filter = baselineFilter ? baselineFilter.cloneNode(false) : document.createElement("select");
      filter.className = "select case-detail-filter runtime-report-filter";
      filter.setAttribute("aria-label", copy("Filter Cases by scenario tag", "按场景标签筛选样本"));
      if (baselineFilter) {
        baselineFilter.replaceWith(filter);
      } else {
        details.querySelector(".card-title").append(filter);
      }
    }
    const uniqueTags = [...new Set(payload.cases.map((item) => canonicalReportTag(item.scenario_tag)))];
    filter.innerHTML = `<option value="all">${copy("All scenario tags", "全部场景标签")}</option>${uniqueTags.map((tag) => `<option value="${safe(tag)}">${safe(reportTagName(tag))}</option>`).join("")}`;
    details.querySelector(".card-title .pill").textContent = `${payload.cases.length} ${copy("total", "条")}`;
    details.querySelector("tbody").innerHTML = reportCases.map((item) => {
      const providers = ["soniox", "speechmatics", "elevenlabs"];
      const providerCells = providers.map((provider) => {
        const evidenceText = String(item.evaluation_asr?.[provider] || "").trim();
        const failure = item.evaluation_asr_failures?.[provider];
        const rendered = evidenceText
          ? arabicComparisonHtml(payload.batch_id, evidenceText)
          : failure
            ? `<span class="muted">${safe(failure.category)} · ${safe(failure.message)} · ${copy("attempts", "尝试")} ${Number(failure.attempts || 0)}</span>`
            : "—";
        return `<td>${rendered}</td>`;
      }).join("");
      const decisionClass = item.decision === "Bad Case" ? "bad" : item.decision === "Good Case" ? "good" : "warn";
      const audio = item.audio_available
        ? `<button class="btn small runtime-report-audio" data-conversation-id="${safe(item.conversation_id)}" data-start="${Number(item.audio_start_s)}" data-end="${Number(item.audio_end_s)}">▶ ${copy("Audio", "试听")}</button>`
        : `<span class="muted">${copy("Audio unavailable", "音频不可用")}</span>`;
      const displayedReason = controlledReportReason(item);
      const reason = displayedReason ? `<small class="muted runtime-case-reason">${safe(displayedReason)}</small>` : "";
      return `<tr data-scenario="${safe(canonicalReportTag(item.scenario_tag))}"><td><span class="id">${reportConversationLink(item.conversation_id, item.event_id)}</span></td><td>${safe(reportTagName(item.scenario_tag))}</td><td>${arabicComparisonHtml(payload.batch_id, item.production_transcript)}</td><td>${audio}</td>${providerCells}<td><span class="pill ${decisionClass}">${safe(reportDecisionName(item.decision))}</span>${reason}</td><td><span class="pill">${safe(reportLabelStatusName(item.label_status))}</span></td></tr>`;
    }).join("") || `<tr><td colspan="8"><div class="runtime-empty">${copy("No completed Cases.", "暂无已完成样本。")}</div></td></tr>`;
    details.querySelector(".report-note")?.remove();
  }
  if (zh()) {
    const reportArabicTexts = reportCases.flatMap((item) => [
      item.production_transcript,
      ...Object.values(item.evaluation_asr || {}),
    ]).filter((text) => typeof text === "string" && text.length <= 240);
    ensureArabicTranslations(payload.batch_id, reportArabicTexts, () => renderReport(report));
  }
}

function filterReportCases(value) {
  const rows = [...document.querySelectorAll("#batch-case-details tbody tr[data-scenario]")];
  let visible = 0;
  rows.forEach((row) => {
    row.hidden = value !== "all" && row.dataset.scenario !== value;
    if (!row.hidden) visible += 1;
  });
  const counter = document.querySelector("#batch-case-details .card-title .pill");
  if (counter) {
    counter.textContent = value === "all"
      ? `${rows.length} ${copy("total", "条")}`
      : `${visible} / ${rows.length} ${copy("matching", "条匹配")}`;
  }
}

function reportLanguageName(value) {
  return {
    ar: copy("Arabic", "阿拉伯语"),
    en: copy("English", "英语"),
    mixed: copy("Arabic–English mixed", "阿英混合"),
    unknown: copy("Unknown", "未知"),
  }[value] || value;
}

async function toggleReportAudio(button) {
  if (runtime.reportAudioButton === button && runtime.reportAudio) {
    if (runtime.reportAudio.paused) await runtime.reportAudio.play();
    else runtime.reportAudio.pause();
    return;
  }
  if (runtime.reportAudio) runtime.reportAudio.pause();
  if (runtime.reportAudioButton) runtime.reportAudioButton.textContent = `▶ ${copy("Audio", "试听")}`;
  const audio = new Audio(`/api/evaluation/conversations/${encodeURIComponent(button.dataset.conversationId)}/user-audio`);
  const start = Number(button.dataset.start);
  const end = Number(button.dataset.end);
  runtime.reportAudio = audio;
  runtime.reportAudioButton = button;
  audio.addEventListener("loadedmetadata", async () => {
    audio.currentTime = Math.min(start, audio.duration || start);
    await audio.play();
  }, { once: true });
  audio.addEventListener("play", () => { button.textContent = `Ⅱ ${copy("Audio", "试听")}`; });
  audio.addEventListener("pause", () => { button.textContent = `▶ ${copy("Audio", "试听")}`; });
  audio.addEventListener("timeupdate", () => {
    if (audio.currentTime >= end) {
      audio.pause();
      audio.currentTime = start;
    }
  });
  audio.addEventListener("error", () => {
    notify(copy("This source audio cannot be played.", "该来源音频无法播放。"));
  }, { once: true });
  audio.load();
}

function runtimeDrawerTranslationKey(batchId, conversation) {
  return `${batchId}:${conversation.conversation_id}:${JSON.stringify(conversation.events.map((event) => event.text))}`;
}

function containsArabic(value) {
  return /[\u0600-\u06ff]/u.test(String(value || ""));
}

function arabicTranslationKey(batchId, text) {
  return `${batchId}:${text}`;
}

function arabicComparisonHtml(batchId, text) {
  const original = `<span class="runtime-source-text" dir="auto">${safe(text)}</span>`;
  if (!zh() || !containsArabic(text)) return original;
  const state = runtime.arabicTranslations.get(arabicTranslationKey(batchId, text));
  const translated = state?.status === "ready"
    ? state.value
    : state?.status === "failed"
      ? "中文对照暂不可用"
      : "中文对照生成中…";
  return `${original}<span class="runtime-arabic-translation"><span class="language-label">中文</span>${safe(translated)}</span>`;
}

async function ensureArabicTranslations(batchId, texts, onComplete) {
  if (!zh() || !batchId) return;
  const missing = [...new Set(texts.filter(containsArabic))].filter((text) => {
    const state = runtime.arabicTranslations.get(arabicTranslationKey(batchId, text));
    return !state;
  });
  if (!missing.length) return;
  missing.forEach((text) => {
    runtime.arabicTranslations.set(arabicTranslationKey(batchId, text), { status: "loading" });
  });
  try {
    const result = await json(`/api/evaluation/batches/${encodeURIComponent(batchId)}/display-translation`, {
      method: "POST",
      body: { texts: missing },
    });
    missing.forEach((text, index) => {
      const value = result.translations[index];
      runtime.arabicTranslations.set(
        arabicTranslationKey(batchId, text),
        typeof value === "string" && value.trim()
          ? { status: "ready", value }
          : { status: "failed" },
      );
    });
    if (result.partial) {
      notify(copy(
        `${result.failed_count} Chinese comparisons are unavailable; other translations were kept.`,
        `${result.failed_count} 条中文对照暂不可用，其余译文已保留。`,
      ));
    }
  } catch (error) {
    missing.forEach((text) => {
      runtime.arabicTranslations.set(arabicTranslationKey(batchId, text), { status: "failed" });
    });
    notify(`${copy("Chinese comparison is unavailable", "中文对照暂不可用")} · ${error.message}`);
  }
  onComplete?.();
}

function renderRuntimeConversationDrawer() {
  const state = runtime.drawerConversation;
  if (!state) return;
  const { conversation, eventId, translations, translationStatus, modelLabel } = state;
  const drawer = document.querySelector("#conversation-drawer");
  const timeline = drawer.querySelector(".conversation-timeline");
  document.querySelector("#drawer-conversation-id").textContent = conversation.conversation_id;
  const translationMeta = zh() && modelLabel
    ? ` · ${copy("Chinese comparison", "中文对照")}：${modelLabel}`
    : "";
  document.querySelector("#drawer-event-id").textContent = `${conversation.event_count} ${copy("events", "个事件")} · ${eventId} ${copy("highlighted", "已高亮")}${translationMeta}`;
  document.querySelector("#drawer-audio-file").textContent = `record/${conversation.conversation_id}.mp3`;
  timeline.innerHTML = conversation.events.map((item, index) => {
    const isTarget = item.event_id === eventId;
    const isCustomer = item.speaker === "customer";
    const role = isCustomer ? copy("Customer", "用户") : copy("Robot", "机器人");
    const originalLanguage = /[\u0600-\u06ff]/u.test(item.text)
      ? copy("Arabic", "阿文")
      : copy("English", "英文");
    let translated = "";
    if (zh()) {
      const value = translations?.[index];
      const translationText = value
        || (translationStatus === "loading" ? "中文对照生成中…" : "中文对照暂不可用");
      translated = `<p class="translation"><span class="language-label">中文</span>${safe(translationText)}</p>`;
    }
    return `<div class="conversation-turn runtime-conversation-turn ${isCustomer ? "user" : ""} ${isTarget ? "target" : ""}" data-time-s="${Number(item.time_s || 0)}" tabindex="0" role="button"><label><span>${role}${isTarget ? copy(" · Target event", " · 当前样本") : ""}</span><span>${safe(item.event_id)} · ${formatTime(Number(item.time_s || 0))}</span></label><p dir="auto">${zh() ? `<span class="language-label">${originalLanguage}</span>` : ""}${safe(item.text)}</p>${translated}</div>`;
  }).join("");
}

async function requestRuntimeDrawerTranslations(state) {
  if (!zh() || !runtime.currentReport) return;
  const batchId = runtime.currentReport.payload.batch_id;
  const key = runtimeDrawerTranslationKey(batchId, state.conversation);
  let pending = runtime.displayTranslationCache.get(key);
  if (!pending) {
    pending = json(`/api/evaluation/batches/${encodeURIComponent(batchId)}/display-translation`, {
      method: "POST",
      body: { texts: state.conversation.events.map((event) => event.text) },
    });
    runtime.displayTranslationCache.set(key, pending);
  }
  state.translationStatus = "loading";
  renderRuntimeConversationDrawer();
  try {
    const result = await pending;
    if (runtime.drawerConversation !== state) return;
    state.translations = result.translations;
    state.translationStatus = "ready";
    state.modelLabel = `${result.provider} / ${result.model_id}`;
  } catch (error) {
    runtime.displayTranslationCache.delete(key);
    if (runtime.drawerConversation !== state) return;
    state.translationStatus = "failed";
    notify(`${copy("Chinese comparison is unavailable", "中文对照暂不可用")} · ${error.message}`);
  }
  renderRuntimeConversationDrawer();
}

async function openRuntimeConversation(button) {
  const conversationId = button.dataset.conversationId;
  const eventId = button.dataset.eventId;
  const drawer = document.querySelector("#conversation-drawer");
  const mask = document.querySelector("#conversation-drawer-mask");
  try {
    const conversation = await json(`/api/evaluation/conversations/${encodeURIComponent(conversationId)}`);
    const batchId = runtime.currentReport?.payload?.batch_id;
    const batch = runtime.bootstrap?.batches?.find((item) => item.id === batchId);
    const passOneModel = batch?.snapshot?.pass_1_model;
    const state = {
      conversation,
      eventId,
      translations: null,
      translationStatus: "idle",
      modelLabel: zh()
        ? `${copy("Pass 1 model", "第一轮模型")} / ${passOneModel || copy("configured model", "已配置模型")}`
        : "",
    };
    runtime.drawerConversation = state;
    const audio = document.querySelector("#drawer-audio");
    audio.pause();
    audio.dataset.conversationId = conversationId;
    audio.src = conversation.audio_url;
    audio.load();
    renderRuntimeConversationDrawer();
    drawer.hidden = false;
    mask.hidden = false;
    window.setTimeout(() => {
      drawer.focus();
      drawer.querySelector(".conversation-turn.target")?.scrollIntoView({ block: "center" });
    }, 0);
    if (zh()) await requestRuntimeDrawerTranslations(state);
  } catch (error) {
    notify(`${copy("Conversation details are unavailable", "历史对话明细暂不可用")} · ${error.message}`);
  }
}

function syncRuntimeDrawerAudio() {
  const state = runtime.drawerConversation;
  if (!state) return;
  const audio = document.querySelector("#drawer-audio");
  const turns = [...document.querySelectorAll("#conversation-drawer .runtime-conversation-turn")];
  let current = turns[0];
  turns.forEach((turn) => {
    if (Number(turn.dataset.timeS) <= audio.currentTime) current = turn;
  });
  turns.forEach((turn) => turn.classList.toggle("playing", turn === current));
}

async function openReport(batchId, partial = false) {
  try {
    const endpoint = partial ? "partial-results" : "report";
    const report = await json(`/api/evaluation/batches/${encodeURIComponent(batchId)}/${endpoint}`);
    renderReport(report);
    showPage("report");
  } catch (error) {
    notify(`${copy("Report is not available", "报告尚不可用")} · ${error.message}`);
  }
}

function renderBootstrapPlaceholder(message) {
  const targets = [
    ["#page-batches tbody", 8],
    ["#page-library tbody", 9],
  ];
  targets.forEach(([selector, columns]) => {
    const body = document.querySelector(selector);
    if (body) body.innerHTML = `<tr><td colspan="${columns}"><div class="runtime-empty" aria-live="polite">${safe(message)}</div></td></tr>`;
  });
}

function syncAccessibility() {
  document.querySelectorAll("dialog").forEach((dialog) => {
    const title = dialog.querySelector(".dialog-head h1, .dialog-head h2, .dialog-head h3");
    if (title) {
      if (!title.id) title.id = `${dialog.id}-title`;
      dialog.setAttribute("aria-labelledby", title.id);
    }
    dialog.querySelectorAll("button.close").forEach((button) => {
      button.setAttribute("aria-label", copy("Close dialog", "关闭弹窗"));
    });
  });
  document.querySelectorAll(".field").forEach((field) => {
    const label = field.querySelector(":scope > label");
    const control = field.querySelector(":scope > input, :scope > select, :scope > textarea");
    if (label && control && !control.getAttribute("aria-label") && !control.getAttribute("aria-labelledby")) {
      control.setAttribute("aria-label", label.textContent.trim());
    }
  });
  const toast = document.querySelector("#toast");
  if (toast) {
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
  }
  const drawer = document.querySelector("#conversation-drawer");
  if (drawer) {
    drawer.setAttribute("role", "dialog");
    drawer.setAttribute("aria-modal", "true");
    drawer.setAttribute("tabindex", "-1");
    drawer.setAttribute("aria-labelledby", "drawer-conversation-id");
  }
}

function installAccessibility() {
  let drawerTrigger = null;
  syncAccessibility();
  new MutationObserver(syncAccessibility).observe(document.body, { childList: true, subtree: true });
  document.addEventListener("click", (event) => {
    const conversationLink = event.target.closest(".conversation-link");
    if (conversationLink) {
      drawerTrigger = conversationLink;
      window.setTimeout(() => document.querySelector("#conversation-drawer:not([hidden])")?.focus(), 0);
    }
    if (event.target.closest("#close-conversation-drawer")) {
      window.setTimeout(() => drawerTrigger?.focus(), 0);
    }
  });
  document.addEventListener("keydown", (event) => {
    const drawer = document.querySelector("#conversation-drawer:not([hidden])");
    if (event.key === "Escape" && drawer) {
      event.preventDefault();
      document.querySelector("#close-conversation-drawer")?.click();
    }
  });
}

async function createReportProposedTag(button) {
  const report = runtime.currentReport;
  if (!report) return;
  button.disabled = true;
  try {
    await json(`/api/evaluation/reports/${encodeURIComponent(report.report_id)}/proposed-tags/${encodeURIComponent(button.dataset.proposalKey)}`, { method: "POST" });
    button.textContent = copy("Created and moved", "已创建并移动");
    await refreshBootstrap({ quiet: true });
  } catch (error) {
    button.disabled = false;
    notify(error.message);
  }
}

async function refreshBootstrap({ quiet = false } = {}) {
  try {
    const payload = await json("/api/evaluation/bootstrap");
    runtime.bootstrap = payload;
    announceOperationStateChanges(payload.batches);
    modeBanner(payload.fixture);
    renderSummary(payload.summary);
    renderBatches(payload.batches);
    renderReviews(payload.reviews);
    renderBenchmarks(payload.benchmarks);
    renderScenarioTags(payload.scenario_tags || []);
    renderAsrCapabilities(payload.asr_capabilities || []);
    renderEvaluationConfiguration();
    const selected = payload.batches.find((batch) => batch.id === runtime.selectedBatchId);
    if (selected) renderRun(selected);
    if (
      document.querySelector("#page-report.active") &&
      !payload.batches.some((batch) => ["completed", "completed_partial"].includes(batch.status))
    ) {
      showPage("batches");
      notify(copy("No real evaluation report exists.", "当前没有真实评测报告。"));
    }
  } catch (error) {
    if (!quiet) {
      renderBootstrapPlaceholder(copy(
        "Evaluation data could not be loaded. Check the local service, then retry.",
        "评测数据加载失败。请检查本地服务后重试。",
      ));
      notify(`${copy("Local evaluation API is unavailable", "本地评测接口不可用")} · ${error.message}`);
    }
  }
}

function renderScenarioTags(tags) {
  const grid = document.querySelector("#scenario-tag-grid");
  if (!grid) return;
  grid.innerHTML = tags.length
    ? tags.map((tag) => {
        const name = zh() ? tag.name_zh : tag.name_en;
        const description = zh() ? tag.description_zh : tag.description_en;
        const status = tag.enabled
          ? `<span class="pill good">${copy("Enabled", "启用")}</span>`
          : `<span class="pill">${copy("Disabled", "停用")}</span>`;
        const type = tag.tag_type === "acoustic"
          ? copy("Acoustic", "声学")
          : copy("Semantic", "语义");
        return `<article class="tag-card" data-tag-id="${safe(tag.id)}">
          ${status}<h3>${safe(name)}</h3><p>${safe(description)}</p>
          <small class="muted">${type} · v${tag.current_version} · ${tag.reference_count} ${copy("references", "个引用")}</small>
          <div class="tag-card-actions">
            <button class="btn small runtime-edit-tag" type="button" aria-label="${copy("Edit", "编辑")} ${safe(name)}">${copy("Edit", "编辑")}</button>
            <button class="btn small runtime-toggle-tag" type="button">${tag.enabled ? copy("Disable", "停用") : copy("Enable", "启用")}</button>
            <button class="btn small danger runtime-delete-tag" type="button" aria-label="${copy("Delete", "删除")} ${safe(name)}">${copy("Delete", "删除")}</button>
          </div>
        </article>`;
      }).join("")
    : `<div class="runtime-empty">${copy("No scenario tags.", "暂无场景标签。")}</div>`;
}

function scenarioTagById(tagId) {
  return runtime.bootstrap?.scenario_tags?.find((tag) => tag.id === tagId);
}

function openScenarioTagEditor(tag = null) {
  runtime.editingTagId = tag?.id || null;
  document.querySelector("#tag-dialog-title").textContent = tag
    ? copy("Edit scenario tag", "编辑场景标签")
    : copy("New scenario tag", "新建场景标签");
  document.querySelector("#save-tag").textContent = tag
    ? copy("Save new version", "保存新版本")
    : copy("Save tag", "保存标签");
  document.querySelector("#tag-name-en").value = tag?.name_en || "";
  document.querySelector("#tag-name-zh").value = tag?.name_zh || "";
  document.querySelector("#tag-description-en").value = tag?.description_en || "";
  document.querySelector("#tag-description-zh").value = tag?.description_zh || "";
  document.querySelector("#tag-type").value = tag?.tag_type || "semantic";
  document.querySelector("#tag-examples").value = (tag?.examples || []).join(" | ");
  document.querySelector("#tag-dialog").showModal();
}

function scenarioTagPayload(tag = null) {
  return {
    name_en: document.querySelector("#tag-name-en").value.trim(),
    name_zh: document.querySelector("#tag-name-zh").value.trim(),
    description_en: document.querySelector("#tag-description-en").value.trim(),
    description_zh: document.querySelector("#tag-description-zh").value.trim(),
    tag_type: document.querySelector("#tag-type").value,
    examples: document.querySelector("#tag-examples").value
      .split("|").map((value) => value.trim()).filter(Boolean),
    expected_version: tag?.current_version || null,
  };
}

async function saveScenarioTag() {
  const tag = runtime.editingTagId ? scenarioTagById(runtime.editingTagId) : null;
  const payload = scenarioTagPayload(tag);
  if (!payload.name_en || !payload.name_zh || !payload.description_en || !payload.description_zh) {
    notify(copy("Complete both names and definitions.", "请补全中英文名称和定义。"));
    return;
  }
  try {
    await json(tag ? `/api/evaluation/scenario-tags/${encodeURIComponent(tag.id)}` : "/api/evaluation/scenario-tags", {
      method: tag ? "PUT" : "POST",
      body: payload,
    });
    document.querySelector("#tag-dialog").close();
    await refreshBootstrap({ quiet: true });
    notify(tag
      ? copy("Saved as a new version; historical snapshots are unchanged.", "已保存为新版本，历史快照保持不变。")
      : copy("Scenario tag created.", "场景标签已创建。"));
  } catch (error) {
    notify(error.message);
  }
}

async function toggleScenarioTag(tag) {
  try {
    await json(`/api/evaluation/scenario-tags/${encodeURIComponent(tag.id)}/status`, {
      method: "PATCH",
      body: { enabled: !tag.enabled, expected_version: tag.current_version },
    });
    await refreshBootstrap({ quiet: true });
  } catch (error) {
    notify(error.message);
  }
}

function confirmScenarioTagDelete(tag) {
  runtime.pendingDeleteTagId = tag.id;
  const name = zh() ? tag.name_zh : tag.name_en;
  document.querySelector("#delete-tag-message").textContent = tag.reference_count
    ? copy(
        `${name} has ${tag.reference_count} references. Remove it from the current taxonomy?`,
        `${name} 已有 ${tag.reference_count} 个引用，仍要从当前标签库删除吗？`,
      )
    : copy(`Delete ${name} from the current taxonomy?`, `确认从当前标签库删除 ${name} 吗？`);
  document.querySelector("#delete-tag-dialog").showModal();
}

async function deleteScenarioTag() {
  const tag = scenarioTagById(runtime.pendingDeleteTagId);
  if (!tag) return;
  try {
    await api(`/api/evaluation/scenario-tags/${encodeURIComponent(tag.id)}?expected_version=${tag.current_version}`, {
      method: "DELETE",
    });
    runtime.pendingDeleteTagId = null;
    document.querySelector("#delete-tag-dialog").close();
    await refreshBootstrap({ quiet: true });
    notify(copy("Tag removed; historical snapshots remain.", "标签已删除，历史快照仍保留。"));
  } catch (error) {
    notify(error.message);
  }
}

async function runBatchAction(batchId, action, version) {
  try {
    const updated = await json(`/api/evaluation/batches/${encodeURIComponent(batchId)}/actions`, {
      method: "POST",
      body: {
        action,
        expected_version: Number(version),
        idempotency_key: idempotency(`batch-${action}`),
      },
    });
    runtime.selectedBatchId = batchId;
    const actionCopy = {
      start: ["Evaluation started.", "评测已开始。"],
      pause: ["Evaluation paused.", "评测已暂停。"],
      resume: ["Evaluation resumed.", "评测已恢复。"],
      retry_failed: ["Failed work queued for retry.", "失败任务已提交重试。"],
    }[action] || [`Batch ${action} saved.`, "批次操作已保存。"];
    notify(copy(actionCopy[0], actionCopy[1]));
    renderRun(updated);
    await refreshBootstrap({ quiet: true });
  } catch (error) {
    notify(error.message);
  }
}

function configurationContext(id) {
  return runtime.bootstrap?.evaluation_contexts?.find((item) => item.id === id);
}

function configurationDictionary(id) {
  return runtime.bootstrap?.reference_dictionaries?.find((item) => item.id === id);
}

function renderEvaluationConfiguration() {
  const contexts = runtime.bootstrap?.evaluation_contexts || [];
  const dictionaries = runtime.bootstrap?.reference_dictionaries || [];
  const promptTemplates = runtime.bootstrap?.prompt_templates || [];
  const contextBody = document.querySelector("#context-table-body");
  if (contextBody) {
    contextBody.innerHTML = contexts.map((context) => `
      <tr data-context-id="${safe(context.id)}" data-context-key="${safe(context.context_key)}">
        <td><b class="context-name">${safe(context.name)}</b></td>
        <td class="context-version">v${safe(context.current_version)}</td>
        <td class="context-scope">${safe(context.business_scope)}</td>
        <td>${context.is_default ? copy("Default", "默认") : copy("Persisted", "已持久化")}</td>
        <td><span class="pill ${context.enabled ? "good" : "muted"}">${context.enabled ? copy("Available", "可用") : copy("Disabled", "已停用")}</span></td>
        <td><div class="actions">
          <button class="btn small preview-context" data-context-id="${safe(context.id)}">${copy("Preview requests", "预览请求")}</button>
          <button class="btn small edit-context" data-context-id="${safe(context.id)}">${copy("Edit new version", "编辑新版本")}</button>
          ${context.is_default ? "" : `<button class="btn small context-default" data-context-id="${safe(context.id)}">${copy("Make default", "设为默认")}</button>`}
          ${context.is_default ? "" : `<button class="btn small context-status" data-context-id="${safe(context.id)}" data-enabled="${context.enabled ? "false" : "true"}">${context.enabled ? copy("Disable", "停用") : copy("Enable", "启用")}</button>`}
        </div></td>
      </tr>`).join("");
  }
  const dictionaryBody = document.querySelector("#dictionary-table-body");
  if (dictionaryBody) {
    dictionaryBody.innerHTML = dictionaries.map((dictionary) => {
      const linked = contexts.filter((context) =>
        context.dictionary_version_ids?.includes(dictionary.version_id));
      return `<tr data-dictionary-id="${safe(dictionary.id)}">
        <td><b class="dictionary-name">${safe(dictionary.name)}</b><br><small class="muted">${safe(dictionary.purpose)}</small></td>
        <td><code>${safe(dictionary.dictionary_key)}</code></td>
        <td class="dictionary-version">v${safe(dictionary.current_version)}</td>
        <td><code>${safe(dictionary.schema_fields.join(" / "))}</code></td>
        <td>${safe(linked.map((context) => context.name).join(", ") || copy("Not linked", "未关联"))}</td>
        <td><button class="btn small edit-dictionary" data-dictionary-id="${safe(dictionary.id)}">${copy("Edit new version", "编辑新版本")}</button></td>
      </tr>`;
    }).join("");
  }
  const referenceList = document.querySelector("#context-dialog .dictionary-ref-list");
  if (referenceList) {
    referenceList.innerHTML = dictionaries.map((dictionary) => `
      <label class="dictionary-ref"><input type="checkbox" class="context-dictionary-ref" value="${safe(dictionary.version_id)}"><span>${safe(dictionary.name)} · v${safe(dictionary.current_version)}</span></label>`).join("");
  }
  const contextSelect = document.querySelector("#new-run-dialog .form-grid select");
  if (contextSelect) {
    const availableContexts = contexts.filter((context) => context.enabled);
    contextSelect.innerHTML = availableContexts.map((context) =>
      `<option value="${safe(context.context_key)}" ${context.is_default ? "selected" : ""}>${safe(context.name)} v${safe(context.current_version)}</option>`).join("");
  }
  document.querySelectorAll("#evaluation-prompts .prompt-editor").forEach((editor, index) => {
    const key = index === 0 ? "pass_1" : "pass_2";
    const template = promptTemplates.find((item) => item.template_key === key);
    if (!template) return;
    editor.value = template.content;
    editor.dataset.saved = template.content;
    editor.dataset.promptKey = key;
    editor.dataset.version = String(template.current_version);
    const badge = editor.closest(".card")?.querySelector(".card-title .pill");
    if (badge) {
      badge.dataset.version = String(template.current_version);
      badge.textContent = copy(`Template v${template.current_version}`, `固定模板 v${template.current_version}`);
    }
    const actions = editor.closest(".card")?.querySelector(".actions");
    if (actions && !actions.querySelector(".prompt-history")) {
      actions.insertAdjacentHTML(
        "afterbegin",
        `<button class="btn prompt-history" data-prompt-key="${key}">${copy("Version history", "版本历史")}</button>`,
      );
    } else if (actions) {
      actions.querySelector(".prompt-history").textContent = copy("Version history", "版本历史");
    }
  });
}

function installPromptHistoryDialog() {
  if (document.querySelector("#prompt-history-dialog")) return;
  document.body.insertAdjacentHTML(
    "beforeend",
    `<dialog id="prompt-history-dialog" class="prompt-history-dialog">
      <div class="dialog-head"><div><h2>${copy("Prompt version history", "Prompt 版本历史")}</h2><p class="muted prompt-history-subtitle"></p></div><button class="close" data-close>×</button></div>
      <div class="dialog-body">
        <div class="prompt-history-layout">
          <nav class="prompt-version-list" aria-label="${copy("Prompt versions", "Prompt 版本")}"></nav>
          <section class="prompt-version-detail">
            <div class="prompt-diff-head"><b class="prompt-diff-title"></b><span class="prompt-diff-summary muted"></span></div>
            <pre class="prompt-version-diff" tabindex="0"></pre>
          </section>
        </div>
      </div>
      <div class="dialog-actions"><button class="btn" data-close>${copy("Close", "关闭")}</button><button class="btn primary restore-prompt-version" hidden>${copy("Restore as new version", "恢复为新版本")}</button></div>
    </dialog>`,
  );
  const dialog = document.querySelector("#prompt-history-dialog");
  dialog.querySelectorAll("[data-close]").forEach((button) => {
    button.addEventListener("click", () => dialog.close());
  });
}

function promptLineDiff(previous, current) {
  const left = previous.split("\n");
  const right = current.split("\n");
  const table = Array.from({ length: left.length + 1 }, () =>
    Array(right.length + 1).fill(0));
  for (let i = left.length - 1; i >= 0; i -= 1) {
    for (let j = right.length - 1; j >= 0; j -= 1) {
      table[i][j] = left[i] === right[j]
        ? table[i + 1][j + 1] + 1
        : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const rows = [];
  let i = 0;
  let j = 0;
  while (i < left.length || j < right.length) {
    if (i < left.length && j < right.length && left[i] === right[j]) {
      rows.push({ kind: "same", text: `  ${left[i]}` });
      i += 1;
      j += 1;
    } else if (j < right.length && (i === left.length || table[i][j + 1] >= table[i + 1][j])) {
      rows.push({ kind: "added", text: `+ ${right[j]}` });
      j += 1;
    } else {
      rows.push({ kind: "removed", text: `- ${left[i]}` });
      i += 1;
    }
  }
  return rows;
}

function renderPromptHistorySelection(version) {
  const dialog = document.querySelector("#prompt-history-dialog");
  const selected = runtime.promptHistory.find((item) => item.version === version);
  const current = runtime.promptHistory.find((item) => item.is_current);
  if (!dialog || !selected || !current) return;
  runtime.selectedPromptVersion = version;
  dialog.querySelectorAll(".prompt-version-item").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.version) === version);
  });
  dialog.querySelector(".prompt-diff-title").textContent = copy(
    `v${version} compared with current v${current.version}`,
    `v${version} 与当前 v${current.version} 对比`,
  );
  const rows = promptLineDiff(selected.content, current.content);
  const changed = rows.filter((row) => row.kind !== "same").length;
  dialog.querySelector(".prompt-diff-summary").textContent = selected.is_current
    ? copy("Current active version", "当前生效版本")
    : copy(`${changed} changed lines`, `${changed} 行变化`);
  dialog.querySelector(".prompt-version-diff").innerHTML = rows.map((row) =>
    `<span class="diff-${row.kind}">${safe(row.text) || " "}</span>`).join("\n");
  const restore = dialog.querySelector(".restore-prompt-version");
  restore.hidden = selected.is_current;
  restore.textContent = copy(
    `Restore v${version} as v${current.version + 1}`,
    `将 v${version} 恢复为 v${current.version + 1}`,
  );
}

async function openPromptHistory(templateKey) {
  installPromptHistoryDialog();
  try {
    const versions = await json(
      `/api/evaluation/prompt-templates/${encodeURIComponent(templateKey)}/versions`,
    );
    runtime.promptHistoryKey = templateKey;
    runtime.promptHistory = versions;
    const dialog = document.querySelector("#prompt-history-dialog");
    const label = templateKey === "pass_1"
      ? copy("Pass 1 · Candidate screening", "第一轮 · 疑点筛选")
      : copy("Pass 2 · Evidence decision", "第二轮 · 证据判定");
    dialog.querySelector(".prompt-history-subtitle").textContent = label;
    dialog.querySelector(".prompt-version-list").innerHTML = versions.map((item) => `
      <button class="prompt-version-item${item.is_current ? " active" : ""}" data-version="${item.version}">
        <b>v${item.version}</b><span>${item.is_current ? copy("Current", "当前") : safe(item.created_at)}</span>
      </button>`).join("");
    renderPromptHistorySelection(versions.find((item) => item.is_current)?.version || versions[0].version);
    dialog.showModal();
  } catch (error) {
    notify(error.message);
  }
}

async function restorePromptVersion() {
  const current = runtime.promptHistory.find((item) => item.is_current);
  if (!current || runtime.selectedPromptVersion === null) return;
  try {
    const updated = await json(
      `/api/evaluation/prompt-templates/${encodeURIComponent(runtime.promptHistoryKey)}/restore`,
      {
        method: "POST",
        body: {
          source_version: runtime.selectedPromptVersion,
          expected_version: current.version,
        },
      },
    );
    document.querySelector("#prompt-history-dialog").close();
    await refreshBootstrap({ quiet: true });
    notify(copy(
      `Historical content restored as Prompt v${updated.current_version}.`,
      `历史内容已恢复为 Prompt v${updated.current_version}。`,
    ));
  } catch (error) {
    notify(error.message);
  }
}

async function updatePersistedContextStatus(contextId, changes) {
  const context = configurationContext(contextId);
  if (!context) return;
  try {
    await json(`/api/evaluation/contexts/${encodeURIComponent(contextId)}/status`, {
      method: "PATCH",
      body: { ...changes, expected_version: context.current_version },
    });
    await refreshBootstrap({ quiet: true });
    notify(copy("Context selection settings saved.", "质检上下文选择设置已保存。"));
  } catch (error) {
    notify(error.message);
  }
}

function openPersistedContextEditor(contextId = null) {
  const context = contextId ? configurationContext(contextId) : null;
  runtime.editingContextId = contextId;
  const values = {
    "#context-name": context?.name || "",
    "#context-scope": context?.business_scope || "",
    "#context-background": context?.business_background_and_objective || "",
    "#context-flow": context?.standard_business_flow || "",
    "#context-terms": context?.terms_and_key_entities || "",
    "#context-rules": context?.dialogue_and_decision_rules || "",
    "#context-risks": context?.known_asr_risks || "",
  };
  Object.entries(values).forEach(([selector, value]) => {
    document.querySelector(selector).value = value;
  });
  document.querySelectorAll(".context-dictionary-ref").forEach((input) => {
    input.checked = Boolean(context?.dictionary_version_ids?.includes(input.value));
  });
  document.querySelector("#context-version-note").textContent = context
    ? copy(
        `Create v${context.current_version + 1} from v${context.current_version}; historical batches keep their frozen version.`,
        `基于 v${context.current_version} 创建 v${context.current_version + 1}；历史批次继续使用已冻结版本。`,
      )
    : copy("The first saved version will be v1.", "首次保存为 v1。");
  document.querySelector("#context-dialog").showModal();
}

async function savePersistedContext() {
  const current = configurationContext(runtime.editingContextId);
  const name = document.querySelector("#context-name").value.trim();
  const key = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "")
    || `context_${Date.now()}`;
  const body = {
    context_key: current?.context_key || key,
    name,
    business_scope: document.querySelector("#context-scope").value.trim(),
    business_background_and_objective: document.querySelector("#context-background").value.trim(),
    standard_business_flow: document.querySelector("#context-flow").value.trim(),
    terms_and_key_entities: document.querySelector("#context-terms").value.trim(),
    dialogue_and_decision_rules: document.querySelector("#context-rules").value.trim(),
    known_asr_risks: document.querySelector("#context-risks").value.trim(),
    dictionary_version_ids: [...document.querySelectorAll(".context-dictionary-ref:checked")]
      .map((input) => input.value),
    expected_version: current?.current_version || null,
  };
  if (Object.entries(body).some(([field, value]) =>
    !["expected_version", "dictionary_version_ids"].includes(field) && !value)) {
    notify(copy("Complete every context field before saving.", "请完整填写所有质检上下文字段。"));
    return;
  }
  try {
    await json(
      current ? `/api/evaluation/contexts/${encodeURIComponent(current.id)}` : "/api/evaluation/contexts",
      { method: current ? "PUT" : "POST", body },
    );
    document.querySelector("#context-dialog").close();
    await refreshBootstrap({ quiet: true });
    notify(copy("A persisted context version was saved.", "新的质检上下文版本已持久化保存。"));
  } catch (error) {
    notify(error.message);
  }
}

function openPersistedDictionaryEditor(dictionaryId = null) {
  const dictionary = dictionaryId ? configurationDictionary(dictionaryId) : null;
  runtime.editingDictionaryId = dictionaryId;
  document.querySelector("#dictionary-name").value = dictionary?.name || "";
  document.querySelector("#dictionary-stable-key").value = dictionary?.dictionary_key || "";
  document.querySelector("#dictionary-stable-key").readOnly = Boolean(dictionary);
  document.querySelector("#dictionary-description").value = dictionary?.purpose || "";
  document.querySelector("#dictionary-content").value = dictionary
    ? JSON.stringify(dictionary.entries, null, 2)
    : "[]";
  document.querySelector("#dictionary-version-note").textContent = dictionary
    ? copy(
        `Create v${dictionary.current_version + 1} from v${dictionary.current_version}; historical batches keep their frozen version.`,
        `基于 v${dictionary.current_version} 创建 v${dictionary.current_version + 1}；历史批次继续使用已冻结版本。`,
      )
    : copy("The first saved version will be v1.", "首次保存为 v1。");
  document.querySelector("#dictionary-dialog").showModal();
}

async function savePersistedDictionary() {
  const current = configurationDictionary(runtime.editingDictionaryId);
  let entries;
  try {
    entries = JSON.parse(document.querySelector("#dictionary-content").value);
    if (!Array.isArray(entries)) throw new Error("Dictionary content must be a JSON array");
  } catch (error) {
    notify(copy(`Invalid JSON: ${error.message}`, `JSON 格式错误：${error.message}`));
    return;
  }
  const body = {
    dictionary_key: current?.dictionary_key
      || document.querySelector("#dictionary-stable-key").value.trim(),
    name: document.querySelector("#dictionary-name").value.trim(),
    purpose: document.querySelector("#dictionary-description").value.trim(),
    schema_fields: current?.schema_fields
      || ["canonical_value", "alias", "code", "locale", "metadata"],
    entries,
    expected_version: current?.current_version || null,
  };
  try {
    await json(
      current
        ? `/api/evaluation/reference-dictionaries/${encodeURIComponent(current.id)}`
        : "/api/evaluation/reference-dictionaries",
      { method: current ? "PUT" : "POST", body },
    );
    document.querySelector("#dictionary-dialog").close();
    await refreshBootstrap({ quiet: true });
    notify(copy("A persisted dictionary version was saved.", "新的参考词典版本已持久化保存。"));
  } catch (error) {
    notify(error.message);
  }
}

async function savePersistedPrompt(button) {
  const editor = button.closest(".card").querySelector(".prompt-editor");
  try {
    const updated = await json(
      `/api/evaluation/prompt-templates/${encodeURIComponent(editor.dataset.promptKey)}`,
      {
        method: "PUT",
        body: { content: editor.value, expected_version: Number(editor.dataset.version) },
      },
    );
    editor.dataset.saved = updated.content;
    await refreshBootstrap({ quiet: true });
    button.closest(".card").querySelector(".cancel-prompt").click();
    notify(copy("A persisted Prompt version was saved.", "新的 Prompt 版本已持久化保存。"));
  } catch (error) {
    notify(error.message);
  }
}

function previewRuntimePayload(context, pass) {
  const dictionaries = (runtime.bootstrap?.reference_dictionaries || []).filter((dictionary) =>
    context.dictionary_version_ids?.includes(dictionary.version_id));
  const shared = {
    evaluation_context: context,
    reference_dictionaries: dictionaries,
    screening_strategy: "focused",
    scenario_tags: runtime.bootstrap?.scenario_tags?.filter((tag) => tag.enabled) || [],
  };
  const conversation = [
    { event_id: "R1", speaker: "robot", text: "Please tell me the branch." },
    { event_id: "R2", speaker: "customer", text: "Representative uploaded transcript." },
  ];
  if (pass === 0) return { conversation_history: conversation, ...shared };
  const conversationId = "representative-conversation-id";
  const candidateCases = [{
    conversation_id: conversationId,
    issue_id: "I1",
    event_id: "R2",
    priority: "P1",
  }];
  const productionTranscripts = { R2: "Representative uploaded transcript." };
  const asrResults = [{ provider: "provider-name", segments: [] }];
  return {
    request_group_id: "runtime-generated-group-id",
    ...shared,
    conversations: [{
      conversation_id: conversationId,
      conversation_history: conversation,
      candidate_cases: candidateCases,
      production_transcripts: productionTranscripts,
      asr_results: asrResults,
    }],
    candidate_case: candidateCases,
    conversation_history: [{ conversation_id: conversationId, events: conversation }],
    production_transcript: [{ conversation_id: conversationId, events: productionTranscripts }],
    asr_results: [{ conversation_id: conversationId, providers: asrResults }],
  };
}

function renderPersistedRequestPreview() {
  const context = configurationContext(runtime.previewContextId);
  if (!context) return;
  const templateKey = runtime.previewPass === 0 ? "pass_1" : "pass_2";
  const template = runtime.bootstrap.prompt_templates.find(
    (item) => item.template_key === templateKey,
  );
  const payload = previewRuntimePayload(context, runtime.previewPass);
  const fields = runtime.previewPass === 0
    ? ["conversation_history", "evaluation_context", "reference_dictionaries", "screening_strategy", "scenario_tags"]
    : [
      "request_group_id",
      "candidate_case",
      "conversation_history",
      "production_transcript",
      "asr_results",
      "evaluation_context",
      "reference_dictionaries",
      "screening_strategy",
      "scenario_tags",
    ];
  if (!fields.includes(runtime.previewField)) runtime.previewField = fields[0];
  document.querySelectorAll("#request-preview-dialog [data-preview-pass]").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.previewPass) === runtime.previewPass);
  });
  document.querySelector("#request-field-map-grid").innerHTML = fields.map((field) => `
    <button type="button" class="${field === runtime.previewField ? "active" : ""}" data-preview-map="${safe(field)}">
      <b>${safe(field.replaceAll("_", " "))}</b><code>{{${safe(field)}}} → User Message.${safe(field)}</code>
    </button>`).join("");
  document.querySelector("#preview-template-path").textContent = copy(
    `Fixed System Prompt v${template.current_version}`,
    `固定 System Prompt v${template.current_version}`,
  );
  document.querySelector("#preview-template-message").textContent = template.content;
  const rendered = JSON.stringify(payload, null, 2);
  const escaped = safe(rendered);
  const escapedKey = safe(`"${runtime.previewField}"`);
  document.querySelector("#preview-rendered-message").innerHTML = escaped.replace(
    escapedKey,
    `<mark>${escapedKey}</mark>`,
  );
  const sourceNote = document.querySelector("#request-preview-dialog .preview-source-note");
  sourceNote.textContent = copy(
    "The fixed System Prompt and runtime User Message are sent separately. {{variable}} markers below show the exact JSON field carrying each session value; linked dictionary entries are complete.",
    "固定 System Prompt 与运行时 User Message 分开发送。下方 {{变量}} 标记对应每个 Session 实际承载数据的 JSON 字段；关联词典包含完整 entries。",
  );
}

function openPersistedRequestPreview(contextId) {
  runtime.previewContextId = contextId;
  runtime.previewPass = 0;
  runtime.previewField = "conversation_history";
  renderPersistedRequestPreview();
  document.querySelector("#request-preview-dialog").showModal();
}

function installDatasetUploadShell() {
  const dialog = document.querySelector("#new-run-dialog");
  const upload = dialog.querySelector(".upload");
  upload.classList.add("runtime-dataset-upload");
  upload.innerHTML = `
    <input id="dataset-upload-input" type="file" accept=".zip,application/zip" hidden>
    <input id="dataset-repair-input" type="file" accept=".zip,.xlsx,.mp3,.wav,application/zip" hidden>
    <div class="dataset-dropzone" id="dataset-dropzone" tabindex="0" role="button">
      <div class="dataset-upload-copy">
        <b id="dataset-package-name">${copy("Current local source package", "当前本地来源数据")}</b>
        <p>${copy(
          "Upload one ZIP containing conversation_history/, record/, and user_record/.",
          "上传一个 ZIP，内含 conversation_history/、record/ 和 user_record/ 三个目录。",
        )}</p>
      </div>
      <div class="dataset-upload-actions">
        <button class="btn" id="discard-dataset-upload" type="button" hidden>${copy("Delete this upload", "删除本次上传")}</button>
        <button class="btn primary" id="choose-dataset-package" type="button">${copy("Choose ZIP", "选择完整 ZIP")}</button>
      </div>
    </div>
    <p class="dataset-upload-help" id="dataset-upload-status">${copy(
      "Files are staged and fully validated before the active dataset changes.",
      "文件会先进入暂存区并完成全部校验，通过后才切换当前数据。",
    )}</p>`;
  dialog.querySelector(".validation").innerHTML = `
    <div class="validation-row" data-dataset-folder="conversation_history"><span>conversation_history/ · ${copy("Per-conversation Excel", "逐通 Excel")}</span><b>—</b><span class="pill issue-status">${copy("Checking", "校验中")}</span></div>
    <div class="validation-row" data-dataset-folder="record"><span>record/ · ${copy("Full-call MP3", "完整通话 MP3")}</span><b>—</b><span class="pill issue-status">${copy("Checking", "校验中")}</span></div>
    <div class="validation-row" data-dataset-folder="user_record"><span>user_record/ · ${copy("Customer WAV", "用户 WAV")}</span><b>—</b><span class="pill issue-status">${copy("Checking", "校验中")}</span></div>`;
  dialog.querySelector(".validation").insertAdjacentHTML(
    "afterend",
    `<section class="dataset-issues" id="dataset-issues" hidden>
      <div class="dataset-issues-head">
        <div><b id="dataset-issues-title"></b><small>${copy(
          "Blocking issues must be repaired. Reference warnings are retained for audit and do not prevent evaluation.",
          "阻断问题需要修复；参考警告仅用于审计，不影响启动评测。",
        )}</small></div>
        <div class="dataset-issue-actions">
          <button class="btn small" id="download-dataset-issues" type="button">${copy("Download issues.csv", "下载问题 CSV")}</button>
          <button class="btn small primary" id="choose-dataset-repair" type="button">${copy("Upload corrections", "上传修复文件")}</button>
        </div>
      </div>
      <div class="dataset-issue-list" id="dataset-issue-list"></div>
    </section>`,
  );
  dialog.querySelector(".dialog-actions").insertAdjacentHTML(
    "beforebegin",
    `<div class="new-run-error" id="new-run-error" role="alert" aria-live="assertive" tabindex="-1" hidden></div>`,
  );
  const dropzone = dialog.querySelector("#dataset-dropzone");
  ["dragenter", "dragover"].forEach((name) =>
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragging");
    }),
  );
  ["dragleave", "drop"].forEach((name) =>
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragging");
    }),
  );
  dropzone.addEventListener("drop", async (event) => {
    const file = event.dataTransfer?.files?.[0];
    if (file) await uploadDatasetFile(file, false);
  });
  dropzone.addEventListener("keydown", (event) => {
    if (!["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    dialog.querySelector("#dataset-upload-input").click();
  });
}

function resetNewEvaluationControls() {
  const dialog = document.querySelector("#new-run-dialog");
  const batchName = dialog.querySelector('input.input:not([type="checkbox"])');
  batchName.value = batchName.defaultValue;
  dialog.querySelectorAll(".form-grid > .field .select").forEach((select) => {
    select.selectedIndex = 0;
  });
  dialog.querySelectorAll(".batch-asr").forEach((input) => {
    input.checked = input.defaultChecked;
  });
  dialog.querySelectorAll(".batch-llm-provider").forEach((select) => {
    select.selectedIndex = 0;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  const budget = dialog.querySelector(".batch-budget-control input");
  budget.value = budget.defaultValue;
  dialog.querySelectorAll("#dataset-upload-input, #dataset-repair-input").forEach((input) => {
    input.value = "";
  });
  const error = dialog.querySelector("#new-run-error");
  error.hidden = true;
  error.textContent = "";
}

async function openNewEvaluationDraft() {
  if (runtime.datasetUploading) return;
  const dialog = document.querySelector("#new-run-dialog");
  try {
    await refreshBootstrap({ quiet: true });
    const fixture = await json("/api/evaluation/dataset/pending", { method: "DELETE" });
    if (runtime.bootstrap) {
      runtime.bootstrap.pending_dataset = null;
      runtime.bootstrap.fixture = fixture;
    }
    runtime.datasetCandidateId = null;
    runtime.newBatchIdempotencyKey = idempotency("create-batch");
    resetNewEvaluationControls();
    renderAsrCapabilities(runtime.bootstrap?.asr_capabilities || []);
    fixtureReady(fixture);
    dialog.showModal();
  } catch (error) {
    notify(error.message);
  }
}

function issueLabel(issueType) {
  const labels = {
    missing_file: ["Missing file", "缺失文件"],
    invalid_workbook: ["Invalid workbook", "工作簿异常"],
    decreasing_event_time: ["Event time goes backwards", "事件时间倒退"],
    invalid_audio: ["Unreadable audio", "音频无法解析"],
    audio_timeline_mismatch: ["MP3/WAV timeline mismatch", "MP3/WAV 时间轴不一致"],
    event_outside_audio: ["Event exceeds audio duration", "事件超出音频时长"],
    unexpected_conversation_count: ["Conversation count mismatch", "对话数量不符合预期"],
    empty_package: ["Empty package", "空数据包"],
  };
  return copy(...(labels[issueType] || [issueType, issueType]));
}

function fixtureReady(fixture) {
  runtime.datasetAudit = fixture;
  runtime.datasetCandidateId = fixture.dataset_id?.startsWith("dataset-")
    ? fixture.dataset_id
    : null;
  const discardUpload = document.querySelector("#discard-dataset-upload");
  if (discardUpload) discardUpload.hidden = !(runtime.datasetCandidateId && fixture.active === false);
  const summary = document.querySelector("#validation-summary");
  const allIssues = fixture.issues || [];
  const blockingIssues = fixture.blocking_issues
    || allIssues.filter((issue) => (issue.severity || "blocking") === "blocking");
  const warnings = fixture.warnings
    || allIssues.filter((issue) => issue.severity === "warning");
  const blockingCount = Number(fixture.blocking_issue_count ?? blockingIssues.length);
  const warningCount = Number(fixture.warning_count ?? warnings.length);
  summary.classList.toggle("resolved", fixture.valid);
  document.querySelector("#issue-count").textContent = copy(
    fixture.valid
      ? `Real source data validated · ${warningCount} reference warnings`
      : `${blockingCount} blocking issues · ${warningCount} reference warnings`,
    fixture.valid
      ? `真实来源数据已校验 · ${warningCount} 个参考警告`
      : `${blockingCount} 个阻断问题 · ${warningCount} 个参考警告`,
  );
  document.querySelector("#issue-blocker").textContent = fixture.valid
    ? `${fixture.matched_conversations} ${copy("conversations passed content validation", "通对话通过内容校验")}`
    : `${fixture.valid_conversations} / ${fixture.conversation_count} ${copy("conversations are currently runnable", "通对话当前可运行")}`;
  const packageName = document.querySelector("#dataset-package-name");
  packageName.textContent = fixture.filename || fixture.source || copy("Current dataset", "当前数据");
  const uploadStatus = document.querySelector("#dataset-upload-status");
  uploadStatus.textContent = fixture.valid
    ? copy(
        `Validated and active · ${fixture.conversation_count} conversations`,
        `已校验并启用 · ${fixture.conversation_count} 通对话`,
      )
    : fixture.active === false
      ? copy(
          "This upload is staged for repair; the active dataset has not been replaced.",
          "该上传包正在等待修复，当前数据尚未被覆盖。",
        )
      : copy(
          "Current source is blocked. Upload a corrected full ZIP or use the repair entry below.",
          "当前来源数据被阻塞；请上传修正后的完整 ZIP，或使用下方修复入口。",
        );
  const rows = [...document.querySelectorAll("#new-run-dialog .validation-row")];
  rows.forEach((row) => {
    const folder = row.dataset.datasetFolder;
    const countValue = Number(fixture.counts?.[folder] || 0);
    const total = Number(fixture.conversation_count || 0);
    const complete = total > 0 && countValue === total;
    const count = row.querySelector("b");
    const status = row.querySelector(".issue-status") || row.querySelector(".pill");
    count.textContent = `${countValue} / ${total}`;
    status.className = `pill ${complete ? "good" : "bad"} issue-status`;
    status.textContent = complete ? copy("Files linked", "文件已关联") : copy("Incomplete", "不完整");
  });
  const issuePanel = document.querySelector("#dataset-issues");
  issuePanel.hidden = allIssues.length === 0;
  issuePanel.classList.toggle("warning-only", blockingCount === 0 && warningCount > 0);
  document.querySelector("#dataset-issues-title").textContent = copy(
    `${blockingCount} blocking issues · ${warningCount} reference warnings · ${fixture.valid_conversations}/${fixture.conversation_count} conversations runnable`,
    `${blockingCount} 个阻断问题 · ${warningCount} 个参考警告 · ${fixture.valid_conversations}/${fixture.conversation_count} 通可运行`,
  );
  document.querySelector("#dataset-issue-list").innerHTML = allIssues
    .map((issue) => {
      const location = issue.expected_path || issue.source_file || copy("Package", "数据包");
      const row = issue.source_row ? ` · R${safe(issue.source_row)}` : "";
      const severity = issue.severity === "warning" ? "warning" : "blocking";
      const severityLabel = severity === "warning"
        ? copy("Reference warning", "参考警告")
        : copy("Blocking", "阻断");
      return `<div class="dataset-issue-item ${severity}"><div><b>${safe(issueLabel(issue.issue_type))}<em>${safe(severityLabel)}</em></b><code>${safe(location)}${row}</code></div><span>${safe(issue.message || copy("Replace or correct this source file.", "请替换或修正该源文件。"))}</span></div>`;
    })
    .join("");
  updateStartRunAvailability();
}

function setDatasetUploading(uploading, label = "") {
  runtime.datasetUploading = uploading;
  ["choose-dataset-package", "choose-dataset-repair"].forEach((id) => {
    const button = document.querySelector(`#${id}`);
    if (button) button.disabled = uploading;
  });
  if (label) document.querySelector("#dataset-upload-status").textContent = label;
}

async function uploadDatasetFile(file, repair) {
  if (runtime.datasetUploading) return;
  const suffix = file.name.split(".").pop()?.toLowerCase();
  const allowed = repair ? ["zip", "xlsx", "mp3", "wav"] : ["zip"];
  if (!allowed.includes(suffix)) {
    notify(
      repair
        ? copy("Choose a ZIP, XLSX, MP3, or WAV repair file.", "请选择 ZIP、XLSX、MP3 或 WAV 修复文件。")
        : copy("Choose a complete ZIP package.", "请选择完整 ZIP 数据包。"),
    );
    return;
  }
  setDatasetUploading(
    true,
    copy(`Uploading and validating ${file.name}…`, `正在上传并校验 ${file.name}…`),
  );
  const form = new FormData();
  form.append("file", file, file.name);
  if (repair && runtime.datasetCandidateId) {
    form.append("candidate_id", runtime.datasetCandidateId);
  }
  try {
    const response = await fetch(
      repair ? "/api/evaluation/dataset/repair" : "/api/evaluation/dataset/upload",
      { method: "POST", body: form },
    );
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `${response.status} ${response.statusText}`);
    }
    const audit = await response.json();
    fixtureReady(audit);
    if (audit.active) {
      await refreshBootstrap({ quiet: true });
      fixtureReady(runtime.bootstrap.fixture);
      notify(copy("Upload validated and activated.", "上传包校验通过，已切换为当前数据。"));
    } else {
      const blockingCount = Number(audit.blocking_issue_count ?? audit.blocking_issues?.length ?? 0);
      const warningCount = Number(audit.warning_count ?? audit.warnings?.length ?? 0);
      notify(
        copy(
          `Upload staged with ${blockingCount} blocking issues and ${warningCount} reference warnings. Current data was not replaced.`,
          `上传包已暂存，仍有 ${blockingCount} 个阻断问题和 ${warningCount} 个参考警告；当前数据未被覆盖。`,
        ),
      );
    }
  } catch (error) {
    notify(error.message);
    if (runtime.datasetAudit) fixtureReady(runtime.datasetAudit);
  } finally {
    setDatasetUploading(false);
  }
}

function downloadDatasetFile(path, filename) {
  const anchor = document.createElement("a");
  anchor.href = path;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
}

async function createBatch() {
  const dialog = document.querySelector("#new-run-dialog");
  const button = document.querySelector("#start-run");
  const name = dialog.querySelector('input.input:not([type="checkbox"])').value.trim();
  const providers = [...dialog.querySelectorAll(".batch-asr:checked")]
    .filter((input) => !input.disabled)
    .map((input) => input.dataset.provider);
  if (!providers.length) {
    notify(copy(
      "Verify at least one async evaluation ASR resource before starting.",
      "请先验证至少一个异步评测 ASR 资源。",
    ));
    return;
  }
  const models = [...dialog.querySelectorAll(".batch-llm-model")].map((select) => select.value);
  const configurationSelects = dialog.querySelectorAll(".form-grid select");
  const contextKey = configurationSelects[0]?.value;
  const strategyLabel = configurationSelects[1]?.value || "Focused · High business impact only";
  const screeningStrategy = strategyLabel.startsWith("Comprehensive")
    ? "comprehensive"
    : strategyLabel.startsWith("Standard")
      ? "standard"
      : "focused";
  const budgetText = dialog.querySelector(".batch-budget-control input").value;
  const errorMessage = dialog.querySelector("#new-run-error");
  errorMessage.hidden = true;
  errorMessage.textContent = "";
  button.disabled = true;
  button.textContent = copy("Creating…", "正在创建…");
  try {
    const batch = await json("/api/evaluation/batches", {
      method: "POST",
      body: {
        name,
        context_key: contextKey,
        screening_strategy: screeningStrategy,
        asr_providers: providers,
        pass_1_model: models[0],
        pass_2_model: models[1],
        budget_limit: Number(budgetText.replace(/[^0-9.]/g, "")),
        idempotency_key: runtime.newBatchIdempotencyKey || idempotency("create-batch"),
      },
    });
    runtime.selectedBatchId = batch.id;
    dialog.close();
    renderRun(batch);
    showPage("run");
    notify(copy("Evaluation started. The frozen snapshot is now running.", "评测已启动，正在按冻结快照执行。"));
    await refreshBootstrap({ quiet: true });
  } catch (error) {
    errorMessage.textContent = error.message;
    errorMessage.hidden = false;
    errorMessage.focus();
    notify(error.message);
  } finally {
    updateStartRunAvailability();
    button.textContent = copy("Confirm and start evaluation", "确认并开始评测");
  }
}

async function discardDatasetUpload() {
  try {
    const fixture = await json("/api/evaluation/dataset/pending", { method: "DELETE" });
    runtime.datasetCandidateId = null;
    runtime.datasetAudit = fixture;
    if (runtime.bootstrap) {
      runtime.bootstrap.pending_dataset = null;
      runtime.bootstrap.fixture = fixture;
    }
    fixtureReady(fixture);
    notify(copy("Staged upload deleted. Active source data is unchanged.", "暂存上传已删除，当前正式数据未变。"));
  } catch (error) {
    notify(error.message);
  }
}

function confirmBatchDelete(batch) {
  runtime.pendingDeleteBatchId = batch.id;
  document.querySelector("#delete-batch-message").textContent = copy(
    `Delete ${batch.id}? Its evaluation results, reviews, reports, and cost rows will be removed. Shared source data and configuration will remain.`,
    `确认删除 ${batch.id}？该批次的评测结果、复核、报告和成本记录会被移除，共享来源数据与配置会保留。`,
  );
  document.querySelector("#delete-batch-dialog").showModal();
}

async function deleteBatch() {
  const batch = runtime.bootstrap?.batches.find((item) => item.id === runtime.pendingDeleteBatchId);
  if (!batch) return;
  const button = document.querySelector("#confirm-delete-batch");
  button.disabled = true;
  try {
    await json(`/api/evaluation/batches/${encodeURIComponent(batch.id)}`, {
      method: "DELETE",
      body: {
        expected_version: batch.version,
        idempotency_key: idempotency("delete-batch"),
      },
    });
    runtime.pendingDeleteBatchId = null;
    document.querySelector("#delete-batch-dialog").close();
    await refreshBootstrap({ quiet: true });
    notify(copy("Batch deleted.", "批次已删除。"));
  } catch (error) {
    notify(error.message);
  } finally {
    button.disabled = false;
  }
}

function renderReviews(allReviews, { force = false } = {}) {
  const reviews = runtime.reviewBatchId
    ? allReviews.filter((review) => review.batch_id === runtime.reviewBatchId)
    : allReviews;
  const queue = document.querySelector("#page-review .queue");
  const header = queue.querySelector(".card-title");
  queue.querySelectorAll(".queue-item, .runtime-empty").forEach((item) => item.remove());
  header.querySelector("h2").textContent = `${copy("Pending", "待处理")} ${reviews.length}`;
  if (!reviews.length) {
    queue.insertAdjacentHTML(
      "beforeend",
      `<div class="runtime-empty">${copy("No review cases remain.", "没有待复核样本。")}</div>`,
    );
    document.querySelector("#page-review .review").hidden = true;
    return;
  }
  document.querySelector("#page-review .review").hidden = false;
  if (!reviews.some((item) => item.id === runtime.selectedReviewId)) {
    runtime.selectedReviewId = reviews[0].id;
  }
  reviews.forEach((review) => {
    const reviewCopy = controlledReviewCopy(review);
    queue.insertAdjacentHTML(
      "beforeend",
      `<button class="queue-item runtime-review-item ${review.id === runtime.selectedReviewId ? "active" : ""}" data-review-id="${safe(review.id)}" data-batch-id="${safe(review.batch_id)}"><div class="queue-top"><span class="id">${safe(review.conversation_id)} · ${safe(review.event_id)}</span><span class="pill warn">${copy("Pending", "待复核")}</span></div><b>${safe(reviewCopy.issue)}</b><p>${review.priority}</p></button>`,
    );
  });
  const selected = reviews.find((item) => item.id === runtime.selectedReviewId);
  const reviewCard = document.querySelector("#page-review .review");
  const currentId = reviewCard.dataset.reviewId;
  const currentVersion = Number(reviewCard.dataset.reviewVersion || 0);
  if (force || currentId !== runtime.selectedReviewId || currentVersion !== selected.version) {
    renderReview(selected, reviews);
  }
}

function stopReviewAudio() {
  if (!runtime.audio) return;
  runtime.audio.pause();
  runtime.audio = null;
}

function formatTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remainder = (seconds % 60).toFixed(1).padStart(4, "0");
  return `${String(minutes).padStart(2, "0")}:${remainder}`;
}

function updateAudioProgress(track, review, currentTime) {
  const duration = Math.max(review.end_s - review.start_s, 0.01);
  const progress = Math.min(100, Math.max(0, ((currentTime - review.start_s) / duration) * 100));
  track.setAttribute("aria-valuenow", String(currentTime));
  track.style.setProperty("--runtime-progress", `${progress}%`);
}

function seekReviewAudio(track, clientX) {
  if (!runtime.audio) return;
  const review = runtime.bootstrap.reviews.find((item) => item.id === runtime.selectedReviewId);
  if (!review) return;
  const bounds = track.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (clientX - bounds.left) / Math.max(bounds.width, 1)));
  const currentTime = review.start_s + (review.end_s - review.start_s) * ratio;
  runtime.audio.currentTime = currentTime;
  updateAudioProgress(track, review, currentTime);
}

function renderReview(review, reviews) {
  if (!review) return;
  stopReviewAudio();
  const card = document.querySelector("#page-review .review");
  const index = reviews.findIndex((item) => item.id === review.id) + 1;
  const reviewCopy = controlledReviewCopy(review);
  card.dataset.reviewId = review.id;
  card.dataset.reviewVersion = review.version;
  card.querySelector(".review-head .eyebrow").textContent = `${copy("Target user event", "目标用户句子")} · ${index} / ${reviews.length}`;
  card.querySelector(".review-head h2").textContent = reviewCopy.issue;
  card.querySelector(".review-head .muted").innerHTML = `${copy("Conversation", "对话")} <span class="id">${safe(review.conversation_id)}</span> · ${copy("Event", "事件")} ${safe(review.event_id)}`;
  card.querySelector(".notice").textContent = copy(
    "The production transcript and all provider transcripts are evidence, not ground truth. Listen before deciding.",
    "历史转写与各家评测 ASR 都只是证据，不是真值；请回听后再判定。",
  );
  const evidence = card.querySelectorAll(".evidence-grid .evidence");
  evidence[0].querySelector("label").textContent = `${copy("Historical transcript", "历史转写")} · ${review.event_id}`;
  evidence[0].querySelector("p").innerHTML = arabicComparisonHtml(
    review.batch_id,
    review.production_transcript,
  );
  evidence[1].querySelector("p").textContent = reviewCopy.question;
  evidence[2].querySelector("p").innerHTML = review.context
    .map((turn) => {
      const speaker =
        turn.speaker === "robot"
          ? copy("Robot", "机器人")
          : turn.speaker === "customer"
            ? copy("Customer", "用户")
            : turn.speaker;
      return `<span class="muted">${safe(speaker)} ${safe(turn.event)}${copy(":", "：")}</span>${arabicComparisonHtml(review.batch_id, turn.text)}`;
    })
    .join("<br>");
  card.querySelectorAll(".vendor-grid .vendor").forEach((vendor) => {
    vendor.replaceWith(vendor.cloneNode(true));
  });
  const vendors = card.querySelectorAll(".vendor-grid .vendor");
  vendors.forEach((vendor, providerIndex) => {
    const provider = review.providers[providerIndex];
    if (!provider) {
      vendor.hidden = true;
      return;
    }
    vendor.hidden = false;
    vendor.querySelector("b").textContent = provider.provider;
    vendor.querySelector("p").innerHTML = arabicComparisonHtml(review.batch_id, provider.text);
    vendor.querySelector("small").textContent = copy(
      "Click to use as manual label",
      "点击带入人工标注",
    );
    vendor.dataset.candidate = provider.text;
    vendor.classList.remove("active");
    vendor.setAttribute("aria-pressed", "false");
  });
  card.querySelector("details .id").innerHTML = review.providers
    .map((item) => `${safe(item.segment_id)} · ${item.start_s.toFixed(2)}–${item.end_s.toFixed(2)}s`)
    .join("<br>");
  const languageSelect = card.querySelector(".form-grid .field:nth-child(1) select");
  const languageOptions = [
    ["en", "English", "英语 · English"],
    ["ar", "Arabic · العربية", "阿拉伯语 · العربية"],
    ["mixed", "Arabic-English mixed", "阿英混合"],
  ];
  languageSelect.innerHTML = languageOptions
    .map(
      ([value, en, cn]) =>
        `<option value="${value}" ${review.language === value ? "selected" : ""}>${copy(en, cn)}</option>`,
    )
    .join("");
  const scenarioSelect = card.querySelector(".form-grid .field:nth-child(2) select");
  const scenarioLabels = {
    branches: ["Branch names", "分行名称"],
    confirmation: ["Confirmation and negation", "确认与否定"],
    numbers: ["Numbers and codes", "数字与代码"],
    overlap: ["Overlapping speakers", "说话人重叠"],
    code_switching: ["Language switching", "语言切换"],
  };
  scenarioSelect.innerHTML = Object.entries(scenarioLabels)
    .map(
      ([value, labels]) =>
        `<option value="${value}" ${review.scenario_tag === value ? "selected" : ""}>${copy(labels[0], labels[1])}</option>`,
    )
    .join("");
  const manual = card.querySelector("#manual-label");
  manual.value = "";
  manual.disabled = false;
  manual.closest(".annotation-row").hidden = true;
  card.querySelector(".bad-decision").disabled = true;
  card.querySelector("#current-proposed-label").textContent = copy(
    "Select an ASR candidate or enter manually",
    "请选择 ASR 候选或手动填写",
  );
  card.querySelector(".review-comparison > div:first-child p").innerHTML = arabicComparisonHtml(
    review.batch_id,
    review.production_transcript,
  );
  const oldAudio = card.querySelector("audio.runtime-review-audio");
  oldAudio?.remove();
  const audio = document.createElement("audio");
  audio.className = "runtime-review-audio";
  audio.preload = "metadata";
  audio.src = review.audio_url;
  card.querySelector(".audio").append(audio);
  runtime.audio = audio;
  const play = card.querySelector("#play");
  const range = card.querySelector(".wave");
  range.classList.add("runtime-audio-track");
  range.setAttribute("role", "slider");
  range.setAttribute("tabindex", "0");
  range.setAttribute("aria-valuemin", String(review.start_s));
  range.setAttribute("aria-valuemax", String(review.end_s));
  range.setAttribute("aria-valuenow", String(review.start_s));
  range.setAttribute("aria-label", copy("Audio progress", "音频进度"));
  range.style.setProperty("--runtime-progress", "0%");
  play.textContent = "▶";
  card.querySelector(".audio .time").textContent = `${formatTime(review.start_s)} — ${formatTime(review.end_s)}`;
  audio.addEventListener("loadedmetadata", () => {
    audio.currentTime = Math.min(review.start_s, audio.duration || review.start_s);
  });
  audio.addEventListener("timeupdate", () => {
    updateAudioProgress(range, review, Math.min(review.end_s, audio.currentTime));
    if (audio.currentTime >= review.end_s) {
      audio.pause();
      audio.currentTime = review.start_s;
      play.textContent = "▶";
    }
  });
  audio.addEventListener("pause", () => {
    play.textContent = "▶";
  });
  audio.addEventListener("play", () => {
    play.textContent = "Ⅱ";
  });
  if (card.closest(".page").classList.contains("active")) {
    ensureArabicTranslations(
      review.batch_id,
      [
        review.production_transcript,
        ...review.context.map((turn) => turn.text),
        ...review.providers.map((provider) => provider.text),
      ],
      () => {
        if (runtime.selectedReviewId === review.id) {
          renderReviews(runtime.bootstrap.reviews, { force: true });
        }
      },
    );
  }
}

function reviewLanguage(card) {
  return card.querySelector(".form-grid .field:nth-child(1) select").value;
}

function reviewTag(card) {
  return card.querySelector(".form-grid .field:nth-child(2) select").value;
}

function selectVendorCandidate(vendorCandidate) {
  runtime.reviewDirty = true;
  const card = vendorCandidate.closest(".review");
  card.querySelectorAll(".vendor-grid .vendor").forEach((vendor) => {
    const selected = vendor === vendorCandidate;
    vendor.classList.toggle("active", selected);
    vendor.setAttribute("aria-pressed", String(selected));
  });
  const label = vendorCandidate.dataset.candidate || "";
  const manual = card.querySelector("#manual-label");
  manual.value = label;
  manual.closest(".annotation-row").hidden = false;
  card.querySelector(".bad-decision").disabled = !label.trim();
  card.querySelector("#current-proposed-label").textContent = label;
}

async function submitDecision(decision) {
  const card = document.querySelector("#page-review .review");
  const label = card.querySelector("#manual-label").value.trim();
  if (decision === "bad" && !label) {
    notify(copy("Choose or enter the corrected label first.", "请先选择或填写正确标注文本。"));
    return;
  }
  try {
    const result = await json(
      `/api/evaluation/reviews/${encodeURIComponent(card.dataset.reviewId)}/decision`,
      {
        method: "POST",
        body: {
          decision,
          label: decision === "bad" ? label : null,
          language: reviewLanguage(card),
          scenario_tag: reviewTag(card),
          expected_version: Number(card.dataset.reviewVersion),
          idempotency_key: idempotency(`review-${decision}`),
        },
      },
    );
    notify(
      decision === "unclear"
        ? copy("Reviewed and discarded; no Benchmark was created.", "已完成复核并丢弃，不进入 Benchmark。")
        : copy("Decision saved and Benchmark sample created.", "判定已保存，并已生成 Benchmark 样本。"),
    );
    runtime.selectedReviewId = null;
    runtime.reviewDirty = false;
    await refreshBootstrap({ quiet: true });
    if (!result.remaining && runtime.selectedBatchId) await openReport(runtime.selectedBatchId);
  } catch (error) {
    notify(error.message);
  }
}

async function completeReviewEarly() {
  const selected = runtime.bootstrap?.reviews.find(
    (item) => item.id === runtime.selectedReviewId,
  );
  const batchId = runtime.reviewBatchId || selected?.batch_id || runtime.selectedBatchId;
  const batch = runtime.bootstrap?.batches.find((item) => item.id === batchId);
  if (!batch) {
    notify(copy("Open a batch review queue first.", "请先从批次进入人工复核。"));
    return;
  }
  try {
    await json(`/api/evaluation/batches/${encodeURIComponent(batch.id)}/complete-review`, {
      method: "POST",
      body: {
        expected_version: Number(batch.version),
        idempotency_key: idempotency("complete-review"),
      },
    });
    document.querySelector("#finish-dialog")?.close();
    await refreshBootstrap({ quiet: true });
    await openReport(batch.id);
    notify(copy("Partial final report frozen.", "部分覆盖最终报告已冻结。"));
  } catch (error) {
    notify(error.message);
  }
}

function configureFinishDialog(mode, batch = null) {
  runtime.finishMode = mode;
  runtime.pendingFinishBatchId = batch?.id || null;
  const dialog = document.querySelector("#finish-dialog");
  const metrics = dialog.querySelectorAll(".metric");
  if (mode === "current_results" && batch) {
    const completed = Number(batch.snapshot?.execution_status?.pass_2?.completed || 0);
    const pending = Number(batch.snapshot?.execution_status?.pass_2?.pending || 0)
      + Math.max(0, Number(batch.review_total || 0) - Number(batch.review_completed || 0));
    dialog.querySelector("#finish-dialog-title").textContent = copy(
      "Finish with current results?",
      "使用现有结果结束？",
    );
    dialog.querySelector("#finish-dialog-warning").textContent = copy(
      "Completed Pass 2 decisions, submitted reviews, and existing Benchmark samples will be kept. Pending, failed, or unclippable Cases will be excluded. This freezes an immutable partial report and does not call ASR or LLM services.",
      "已完成的 Pass 2 结论、已提交复核和现有 Benchmark 会保留；待处理、失败或无法可靠裁片的 Case 会被排除。系统将冻结不可变的部分覆盖报告，不会调用 ASR 或 LLM。",
    );
    metrics[0].querySelector(".label").textContent = copy("Completed Pass 2", "已完成 Pass 2");
    metrics[0].querySelector("strong").textContent = completed;
    metrics[0].querySelector("small").textContent = copy("Preserved", "保留现有成功结果");
    metrics[1].querySelector(".label").textContent = copy("Pending / excluded", "待处理 / 排除");
    metrics[1].querySelector("strong").textContent = pending;
    metrics[1].querySelector("small").textContent = copy("No retry will run", "不会执行重试");
    metrics[2].querySelector(".label").textContent = copy("Final report", "最终报告");
    metrics[2].querySelector("strong").textContent = copy("Partial coverage", "部分覆盖");
    metrics[2].querySelector("small").textContent = copy("Immutable", "冻结后不可变");
    dialog.querySelector("#cancel-finish").textContent = copy("Keep processing", "继续处理");
    dialog.querySelector("#confirm-finish").textContent = copy(
      "Finish with current results",
      "确认使用现有结果结束",
    );
  } else {
    const reviewBatchId = runtime.reviewBatchId || runtime.selectedBatchId;
    const reviewBatch = runtime.bootstrap?.batches.find((item) => item.id === reviewBatchId);
    const completed = Number(reviewBatch?.review_completed || 0);
    const total = Number(reviewBatch?.review_total || 0);
    const pending = Math.max(0, total - completed);
    dialog.querySelector("#finish-dialog-title").textContent = copy(
      "Finish manual review early?",
      "提前结束人工复核？",
    );
    dialog.querySelector("#finish-dialog-warning").textContent = copy(
      `${pending} review Cases are still pending. They will not enter the formal Benchmark or manual conclusions.`,
      `仍有 ${pending} 个目标用户句子未复核；这些样本不会进入正式 Benchmark，也不会作为人工确认结论。`,
    );
    metrics[0].querySelector(".label").textContent = copy("Review completion", "复核完成率");
    metrics[0].querySelector("strong").textContent = total
      ? `${Math.round((completed / total) * 100)}%`
      : "100%";
    metrics[0].querySelector("small").textContent = `${completed} / ${total}`;
    metrics[1].querySelector(".label").textContent = copy("Unreviewed", "未复核");
    metrics[1].querySelector("strong").textContent = pending;
    metrics[1].querySelector("small").textContent = copy("Remain excluded", "保持未复核状态");
    metrics[2].querySelector(".label").textContent = copy("Final diagnosis", "最终诊断");
    metrics[2].querySelector("strong").textContent = copy("Partial coverage", "部分覆盖");
    metrics[2].querySelector("small").textContent = copy("Coverage disclosed", "报告披露覆盖范围");
    dialog.querySelector("#cancel-finish").textContent = copy("Continue review", "继续复核");
    dialog.querySelector("#confirm-finish").textContent = copy(
      "Finish early and generate report",
      "确认提前结束并生成报告",
    );
  }
  if (!dialog.open) dialog.showModal();
}

async function completeWithCurrentResults() {
  const batch = runtime.bootstrap?.batches.find(
    (item) => item.id === runtime.pendingFinishBatchId,
  );
  if (!batch) {
    notify(copy("Refresh and select the batch again.", "请刷新后重新选择批次。"));
    return;
  }
  try {
    await json(
      `/api/evaluation/batches/${encodeURIComponent(batch.id)}/complete-with-current-results`,
      {
        method: "POST",
        body: {
          expected_version: Number(batch.version),
          idempotency_key: idempotency("complete-with-current-results"),
        },
      },
    );
    document.querySelector("#finish-dialog")?.close();
    runtime.pendingFinishBatchId = null;
    await refreshBootstrap({ quiet: true });
    await openReport(batch.id);
    notify(copy("Partial final report frozen without provider calls.", "已使用现有结果生成部分覆盖最终报告，未调用外部资源。"));
  } catch (error) {
    notify(error.message);
  }
}

function benchmarkQuery() {
  const rawScenario = document.querySelector("#benchmark-scenario-filter").value;
  return {
    case_type: document.querySelector("#benchmark-case-type-filter").value,
    language: document.querySelector("#benchmark-language-filter").value,
    scenario_tag:
      rawScenario === "branch"
        ? "branches"
        : rawScenario === "customer"
          ? "customer_tier"
          : rawScenario,
    source: document.querySelector("#benchmark-source-filter").value,
    search: document.querySelector("#benchmark-search").value.trim(),
  };
}

function localizeBenchmarkTypeFilter() {
  const options = document.querySelector("#benchmark-case-type-filter")?.options;
  if (!options) return;
  options[0].textContent = copy("All case types", "全部类型");
  options[1].textContent = copy("Good Case", "正确");
  options[2].textContent = copy("Bad Case", "错误");
}

function benchmarkLanguage(value) {
  const labels = {
    ar: ["Arabic", "阿拉伯语"],
    en: ["English", "英语"],
    mixed: ["Arabic-English mixed", "阿英混合"],
  };
  return copy(...(labels[value] || [value, value]));
}

function benchmarkScenario(value) {
  const labels = {
    branches: ["Branch names and cities", "分行名称与城市"],
    numbers: ["Numbers and codes", "数字与代码"],
    customer_tier: ["Customer tier", "客户类别"],
    confirmation: ["Confirmation and negation", "确认与否定"],
    overlap: ["Speaker overlap", "说话人重叠"],
    code_switching: ["Language switching", "语言切换"],
  };
  return copy(...(labels[value] || [value, value]));
}

function renderBenchmarks(result) {
  runtime.benchmarkResult = result;
  runtime.benchmarkTotal = result.total;
  runtime.benchmarkItems = new Map(result.items.map((item) => [item.id, item]));
  const body = document.querySelector("#page-library tbody");
  body.innerHTML = result.items.length
    ? result.items
        .map(
          (item) => `<tr data-benchmark-id="${safe(item.id)}" data-case-type="${safe(item.case_type)}" data-language="${safe(item.language)}" data-scenario="${safe(item.scenario_tag)}" data-source="${safe(item.source)}"><td><input class="benchmark-check runtime-benchmark-check" type="checkbox" value="${safe(item.id)}" aria-label="${copy("Select", "选择")} ${safe(item.id)}" ${runtime.selectedBenchmarkIds.has(item.id) ? "checked" : ""}></td><td><span class="id">${safe(item.id)}</span></td><td><span class="id">${safe(item.conversation_id)} · ${safe(item.event_id)}</span></td><td><span class="pill ${item.case_type === "good" ? "good" : "bad"}">${item.case_type === "good" ? copy("Good Case", "正确") : copy("Bad Case", "错误")}</span></td><td>${safe(benchmarkLanguage(item.language))}</td><td>${safe(benchmarkScenario(item.scenario_tag))}</td><td><span class="pill ${item.source === "manual" ? "blue" : ""}">${item.source === "manual" ? copy("Manual", "人工标注") : copy("AI", "AI 标注")}</span></td><td>${arabicComparisonHtml(item.batch_id, item.label)}</td><td><div class="actions"><button class="btn small runtime-sample-detail" data-benchmark-id="${safe(item.id)}">${copy("View", "查看")}</button><button class="btn small danger runtime-benchmark-delete" data-benchmark-id="${safe(item.id)}">${copy("Delete", "删除")}</button></div></td></tr>`,
        )
        .join("")
    : `<tr><td colspan="9"><div class="runtime-empty">${copy(
        "No Benchmark samples. Samples appear only after a real evaluation or human decision.",
        "暂无 Benchmark 样本；仅在真实评测或人工判定后生成。",
      )}</div></td></tr>`;
  const page = Math.floor(result.offset / result.limit) + 1;
  document.querySelector("#benchmark-page-summary").textContent = `${copy("Page", "第")} ${page} · 20 ${copy("per page", "条/页")} · ${result.total} ${copy("total", "条")}`;
  const pager = document.querySelectorAll("#page-library .library-pager button");
  pager[0].disabled = result.offset === 0;
  pager[1].disabled = result.offset + result.items.length >= result.total;
  document.querySelector("#benchmark-filter-count").textContent = `${result.total} ${copy("filtered", "个筛选结果")}`;
  document.querySelector("#download-filtered-benchmarks").textContent = `${copy("Download all filtered", "下载全部筛选结果")} (${result.total})`;
  document.querySelector("#download-filtered-benchmarks").disabled = result.total === 0;
  updateBenchmarkSelection();
  const translationsByBatch = new Map();
  result.items.forEach((item) => {
    if (!containsArabic(item.label)) return;
    const texts = translationsByBatch.get(item.batch_id) || [];
    texts.push(item.label);
    translationsByBatch.set(item.batch_id, texts);
  });
  if (document.querySelector("#page-library").classList.contains("active")) {
    translationsByBatch.forEach((texts, batchId) => {
      ensureArabicTranslations(batchId, texts, () => {
        if (runtime.benchmarkResult === result) renderBenchmarks(result);
      });
    });
  }
}

function renderBenchmarkDetailText(item, event) {
  const dialog = document.querySelector("#sample-dialog");
  const evidence = dialog.querySelectorAll(".evidence");
  evidence[0].querySelector("p").innerHTML = arabicComparisonHtml(
    item.batch_id,
    event?.text || copy("Unavailable", "不可用"),
  );
  evidence[1].querySelector("p").innerHTML = arabicComparisonHtml(item.batch_id, item.label);
}

async function openBenchmarkDetail(button) {
  const item = runtime.benchmarkItems.get(button.dataset.benchmarkId);
  if (!item) return;
  runtime.activeBenchmarkId = item.id;
  const dialog = document.querySelector("#sample-dialog");
  const conversation = await json(
    `/api/evaluation/conversations/${encodeURIComponent(item.conversation_id)}`,
  );
  const event = conversation.events.find((entry) => entry.event_id === item.event_id);
  dialog.querySelector(".eyebrow").textContent = item.id;
  dialog.querySelector("h3 .id").textContent = `${item.conversation_id} · ${item.event_id}`;
  const evidence = dialog.querySelectorAll(".evidence");
  evidence[0].querySelector("label").textContent = copy("Production transcript", "历史转录");
  evidence[1].querySelector("label").textContent = `${copy("Label text", "标注文本")} · ${item.source === "manual" ? copy("Manual", "人工标注") : copy("AI", "AI 标注")}`;
  renderBenchmarkDetailText(item, event);
  evidence[2].querySelector("label").textContent = copy("Language", "语种");
  evidence[2].querySelector("p").textContent = benchmarkLanguage(item.language);
  evidence[3].querySelector("label").textContent = copy("Scenario", "场景");
  evidence[3].querySelector("p").textContent = benchmarkScenario(item.scenario_tag);
  dialog.querySelector("#benchmark-edit-label").value = item.label;
  dialog.querySelector("#benchmark-edit-language").value = item.language;
  dialog.querySelector("#benchmark-edit-scenario").value = item.scenario_tag;
  dialog.querySelector("#benchmark-edit-form").hidden = true;
  dialog.querySelector(".benchmark-edit").hidden = false;
  dialog.querySelector(".benchmark-cancel-edit").hidden = true;
  dialog.querySelector(".benchmark-save").hidden = true;
  const audioBox = dialog.querySelector(".audio");
  audioBox.innerHTML = item.audio_url
    ? `<div class="audio-row"><button class="play runtime-benchmark-play" type="button" aria-label="${copy("Play Benchmark clip", "播放 Benchmark 片段")}">▶</button><div class="wave"></div><span class="time">${formatTime(item.audio_start_s)} — ${formatTime(item.audio_end_s)}</span></div><audio class="runtime-benchmark-audio" preload="metadata" src="${safe(item.audio_url)}"></audio>`
    : `<p class="muted">${copy("Clip unavailable", "音频片段不可用")}: ${safe(item.clip_error || item.clip_status)}</p>`;
  const audio = audioBox.querySelector("audio");
  const play = audioBox.querySelector(".runtime-benchmark-play");
  if (audio && play) {
    play.addEventListener("click", async () => {
      if (audio.paused) await audio.play();
      else audio.pause();
    });
    audio.addEventListener("play", () => { play.textContent = "Ⅱ"; });
    audio.addEventListener("pause", () => { play.textContent = "▶"; });
    audio.addEventListener("error", () => {
      notify(copy("This Benchmark clip cannot be played.", "该 Benchmark 片段无法播放。"));
    }, { once: true });
  }
  dialog.showModal();
  ensureArabicTranslations(
    item.batch_id,
    [event?.text || "", item.label],
    () => {
      if (runtime.activeBenchmarkId === item.id && dialog.open) {
        renderBenchmarkDetailText(item, event);
      }
    },
  );
}

function setBenchmarkEditMode(editing) {
  const dialog = document.querySelector("#sample-dialog");
  dialog.querySelector("#benchmark-edit-form").hidden = !editing;
  dialog.querySelector(".benchmark-edit").hidden = editing;
  dialog.querySelector(".benchmark-cancel-edit").hidden = !editing;
  dialog.querySelector(".benchmark-save").hidden = !editing;
  if (editing) dialog.querySelector("#benchmark-edit-label").focus();
}

async function saveBenchmarkRevision() {
  const item = runtime.benchmarkItems.get(runtime.activeBenchmarkId);
  if (!item) return;
  const dialog = document.querySelector("#sample-dialog");
  const label = dialog.querySelector("#benchmark-edit-label").value.trim();
  if (!label) {
    notify(copy("Label text is required.", "标注文本不能为空。"));
    return;
  }
  try {
    await json(`/api/evaluation/benchmarks/${encodeURIComponent(item.id)}`, {
      method: "PATCH",
      body: {
        label,
        language: dialog.querySelector("#benchmark-edit-language").value,
        scenario_tag: dialog.querySelector("#benchmark-edit-scenario").value,
        expected_revision: Number(item.revision),
      },
    });
    dialog.close();
    runtime.activeBenchmarkId = null;
    await refreshBenchmarks();
    notify(copy("Saved as a new immutable Benchmark revision.", "已保存为新的不可变 Benchmark 修订。"));
  } catch (error) {
    notify(error.message);
  }
}

function requestBenchmarkDeletion(benchmarkId) {
  const item = runtime.benchmarkItems.get(benchmarkId);
  if (!item) return;
  runtime.pendingDeleteBenchmarkId = benchmarkId;
  const detailDialog = document.querySelector("#sample-dialog");
  if (detailDialog.open) detailDialog.close();
  document.querySelector("#delete-benchmark-message").textContent = copy(
    `Benchmark ${benchmarkId} will be permanently deleted.`,
    `Benchmark ${benchmarkId} 将被永久删除。`,
  );
  document.querySelector("#delete-benchmark-dialog").showModal();
}

async function confirmBenchmarkDeletion() {
  const benchmarkId = runtime.pendingDeleteBenchmarkId;
  if (!benchmarkId) return;
  const button = document.querySelector("#confirm-delete-benchmark");
  button.disabled = true;
  try {
    await json(`/api/evaluation/benchmarks/${encodeURIComponent(benchmarkId)}`, {
      method: "DELETE",
    });
    runtime.selectedBenchmarkIds.delete(benchmarkId);
    runtime.activeBenchmarkId = null;
    runtime.pendingDeleteBenchmarkId = null;
    document.querySelector("#delete-benchmark-dialog").close();
    await refreshBootstrap({ quiet: true });
    notify(copy("Benchmark sample deleted.", "Benchmark 样本已删除。"));
  } catch (error) {
    notify(error.message);
  } finally {
    button.disabled = false;
  }
}

function updateBenchmarkSelection() {
  const count = runtime.selectedBenchmarkIds.size;
  const pageChecks = [...document.querySelectorAll("#page-library .runtime-benchmark-check")];
  const selectedOnPage = pageChecks.filter((check) => check.checked).length;
  const selectAll = document.querySelector("#select-all-benchmarks");
  selectAll.checked = pageChecks.length > 0 && selectedOnPage === pageChecks.length;
  selectAll.indeterminate = selectedOnPage > 0 && selectedOnPage < pageChecks.length;
  selectAll.disabled = pageChecks.length === 0;
  const button = document.querySelector("#download-benchmarks");
  button.disabled = count === 0;
  button.textContent = count
    ? `${copy("Download selected", "下载已选")} (${count})`
    : copy("Download selected", "下载已选");
  document.querySelector("#benchmark-selection-count").textContent = count
    ? `${count} ${copy("selected", "个已选")}`
    : copy("No samples selected", "未选择样本");
}

async function refreshBenchmarks() {
  const query = benchmarkQuery();
  const params = new URLSearchParams({ ...query, limit: "20", offset: "0" });
  try {
    params.set("limit", "20");
    params.set("offset", String(runtime.benchmarkOffset));
    renderBenchmarks(await json(`/api/evaluation/benchmarks?${params}`));
  } catch (error) {
    notify(error.message);
  }
}

async function downloadBenchmarks(allFiltered) {
  const query = benchmarkQuery();
  try {
    notify(copy("Preparing ZIP…", "正在生成 ZIP…"));
    let exportJob = await json("/api/evaluation/benchmarks/export", {
      method: "POST",
      body: {
        sample_ids: allFiltered ? [] : [...runtime.selectedBenchmarkIds],
        ...query,
      },
    });
    for (let attempt = 0; exportJob.status === "pending" && attempt < 120; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 500));
      exportJob = await json(exportJob.status_url);
    }
    if (exportJob.status !== "ready" || !exportJob.download_url) {
      const reason = exportJob.error || copy(
        "The export did not finish within one minute.",
        "导出未能在一分钟内完成。",
      );
      throw new Error(reason);
    }
    const blob = await (await api(exportJob.download_url)).blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "asr-benchmark.zip";
    anchor.click();
    URL.revokeObjectURL(url);
    notify(copy("Benchmark ZIP downloaded.", "Benchmark ZIP 已下载。"));
  } catch (error) {
    notify(error.message);
  }
}

function installEvents() {
  document.querySelector("#drawer-audio")?.addEventListener("timeupdate", syncRuntimeDrawerAudio);
  document.addEventListener(
    "change",
    async (event) => {
      if (event.target.matches("#dataset-upload-input, #dataset-repair-input")) {
        event.stopImmediatePropagation();
        const file = event.target.files?.[0];
        const repair = event.target.id === "dataset-repair-input";
        if (file) await uploadDatasetFile(file, repair);
        event.target.value = "";
        return;
      }
      if (event.target.matches(".model-provider, .model-name-select")) {
        invalidateLlmPricing(event.target.closest("tr"));
      }
      if (event.target.matches(".batch-asr")) {
        updateStartRunAvailability();
      }
      if (!event.target.matches("#select-all-benchmarks")) return;
      event.stopImmediatePropagation();
      document
        .querySelectorAll("#page-library .runtime-benchmark-check")
        .forEach((check) => {
          check.checked = event.target.checked;
          event.target.checked
            ? runtime.selectedBenchmarkIds.add(check.value)
            : runtime.selectedBenchmarkIds.delete(check.value);
        });
      updateBenchmarkSelection();
    },
    true,
  );
  document.addEventListener(
    "click",
    async (event) => {
      const testSource = event.target.closest(".test-source");
      if (testSource) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await testAsrCapability(testSource);
        return;
      }
      const previewContext = event.target.closest(".preview-context");
      if (previewContext) {
        event.preventDefault();
        event.stopImmediatePropagation();
        openPersistedRequestPreview(previewContext.dataset.contextId);
        return;
      }
      const previewPass = event.target.closest("#request-preview-dialog [data-preview-pass]");
      if (previewPass) {
        event.preventDefault();
        event.stopImmediatePropagation();
        runtime.previewPass = Number(previewPass.dataset.previewPass);
        renderPersistedRequestPreview();
        return;
      }
      const previewField = event.target.closest("#request-field-map-grid [data-preview-map]");
      if (previewField) {
        event.preventDefault();
        event.stopImmediatePropagation();
        runtime.previewField = previewField.dataset.previewMap;
        renderPersistedRequestPreview();
        return;
      }
      const editContext = event.target.closest(".edit-context");
      if (editContext) {
        event.preventDefault();
        event.stopImmediatePropagation();
        openPersistedContextEditor(editContext.dataset.contextId);
        return;
      }
      const defaultContext = event.target.closest(".context-default");
      if (defaultContext) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await updatePersistedContextStatus(defaultContext.dataset.contextId, {
          is_default: true,
        });
        return;
      }
      const contextStatus = event.target.closest(".context-status");
      if (contextStatus) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await updatePersistedContextStatus(contextStatus.dataset.contextId, {
          enabled: contextStatus.dataset.enabled === "true",
        });
        return;
      }
      if (event.target.closest("#new-context")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        openPersistedContextEditor();
        return;
      }
      if (event.target.closest("#save-context")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await savePersistedContext();
        return;
      }
      const editDictionary = event.target.closest(".edit-dictionary");
      if (editDictionary) {
        event.preventDefault();
        event.stopImmediatePropagation();
        openPersistedDictionaryEditor(editDictionary.dataset.dictionaryId);
        return;
      }
      if (event.target.closest("#new-dictionary")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        openPersistedDictionaryEditor();
        return;
      }
      if (event.target.closest("#save-dictionary")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await savePersistedDictionary();
        return;
      }
      const promptHistory = event.target.closest(".prompt-history");
      if (promptHistory) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await openPromptHistory(promptHistory.dataset.promptKey);
        return;
      }
      const promptVersion = event.target.closest(".prompt-version-item");
      if (promptVersion) {
        event.preventDefault();
        event.stopImmediatePropagation();
        renderPromptHistorySelection(Number(promptVersion.dataset.version));
        return;
      }
      if (event.target.closest(".restore-prompt-version")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await restorePromptVersion();
        return;
      }
      const savePrompt = event.target.closest(".save-prompt");
      if (savePrompt) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await savePersistedPrompt(savePrompt);
        return;
      }
      if (event.target.closest("#new-tag")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        openScenarioTagEditor();
        return;
      }
      const tagCard = event.target.closest("#scenario-tag-grid .tag-card");
      if (tagCard) {
        const tag = scenarioTagById(tagCard.dataset.tagId);
        if (!tag) return;
        if (event.target.closest(".runtime-edit-tag")) {
          event.preventDefault();
          event.stopImmediatePropagation();
          openScenarioTagEditor(tag);
          return;
        }
        if (event.target.closest(".runtime-toggle-tag")) {
          event.preventDefault();
          event.stopImmediatePropagation();
          await toggleScenarioTag(tag);
          return;
        }
        if (event.target.closest(".runtime-delete-tag")) {
          event.preventDefault();
          event.stopImmediatePropagation();
          confirmScenarioTagDelete(tag);
          return;
        }
      }
      if (event.target.closest("#save-tag")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await saveScenarioTag();
        return;
      }
      if (event.target.closest("#confirm-delete-tag")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await deleteScenarioTag();
        return;
      }
      if (event.target.closest("#new-run")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await openNewEvaluationDraft();
        return;
      }
      const asrPricingButton = event.target.closest("#sync-asr-pricing");
      if (asrPricingButton) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await syncOfficialPricing("asr", asrPricingButton);
        return;
      }
      const llmPricingButton = event.target.closest("#sync-llm-pricing");
      if (llmPricingButton) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await syncOfficialPricing("llm", llmPricingButton);
        return;
      }
      if (event.target.closest("#save-costs")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await savePricingVersion();
        return;
      }
      if (event.target.closest("#choose-dataset-package")
          || (event.target.closest("#dataset-dropzone")
            && !event.target.closest("#discard-dataset-upload"))) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!runtime.datasetUploading) {
          document.querySelector("#dataset-upload-input").click();
        }
        return;
      }
      if (event.target.closest("#choose-dataset-repair")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!runtime.datasetUploading) {
          document.querySelector("#dataset-repair-input").click();
        }
        return;
      }
      if (event.target.closest("#discard-dataset-upload")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await discardDatasetUpload();
        return;
      }
      if (event.target.closest("#download-template")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        downloadDatasetFile(
          "/api/evaluation/dataset/template",
          "evaluation-upload-template.zip",
        );
        return;
      }
      if (event.target.closest("#download-dataset-issues")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const query = runtime.datasetCandidateId
          ? `?candidate_id=${encodeURIComponent(runtime.datasetCandidateId)}`
          : "";
        downloadDatasetFile(
          `/api/evaluation/dataset/issues.csv${query}`,
          "evaluation-issues.csv",
        );
        return;
      }
      const finishCurrentButton = event.target.closest(".runtime-finish-current");
      if (finishCurrentButton) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const batchId = finishCurrentButton.closest("tr")?.dataset.batchId
          || runtime.selectedBatchId;
        const batch = runtime.bootstrap.batches.find((item) => item.id === batchId);
        if (batch) configureFinishDialog("current_results", batch);
        return;
      }
      const batchButton = event.target.closest(".runtime-batch-action");
      if (batchButton) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const batchId = batchButton.closest("tr").dataset.batchId;
        const batch = runtime.bootstrap.batches.find((item) => item.id === batchId);
        runtime.selectedBatchId = batchId;
        if (batchButton.dataset.action === "report") {
          await openReport(batchId);
        } else if (batchButton.dataset.action === "partial_results") {
          await openReport(batchId, true);
        } else if (batchButton.dataset.action === "open") {
          renderRun(batch);
          showPage("run");
        } else {
          await runBatchAction(batchId, batchButton.dataset.action, batchButton.dataset.version);
        }
        return;
      }
      const deleteBatchButton = event.target.closest(".runtime-delete-batch");
      if (deleteBatchButton) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const batchId = deleteBatchButton.closest("tr").dataset.batchId;
        const batch = runtime.bootstrap.batches.find((item) => item.id === batchId);
        if (batch) confirmBatchDelete(batch);
        return;
      }
      if (event.target.closest("#confirm-delete-batch")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await deleteBatch();
        return;
      }
      const runReport = event.target.closest(".runtime-run-report");
      if (runReport) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await openReport(runReport.dataset.batchId);
        return;
      }
      const openBatch = event.target.closest(".runtime-open-batch");
      if (openBatch) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const batchId = openBatch.closest("tr").dataset.batchId;
        const batch = runtime.bootstrap.batches.find((item) => item.id === batchId);
        runtime.selectedBatchId = batchId;
        renderRun(batch);
        showPage("run");
        return;
      }
      const runAction = event.target.closest(".runtime-run-action");
      if (runAction) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await runBatchAction(
          runtime.selectedBatchId,
          runAction.dataset.action,
          runAction.dataset.version,
        );
        return;
      }
      if (event.target.closest(".runtime-open-review")) {
        event.preventDefault();
        runtime.reviewBatchId = runtime.selectedBatchId;
        runtime.selectedReviewId = null;
        runtime.reviewDirty = false;
        showPage("review");
        renderReviews(runtime.bootstrap.reviews, { force: true });
        return;
      }
      if (event.target.closest('.nav[data-page="review"]')) {
        runtime.reviewBatchId = null;
        runtime.selectedReviewId = null;
        runtime.reviewDirty = false;
        window.setTimeout(() => renderReviews(runtime.bootstrap.reviews, { force: true }));
      }
      if (event.target.closest('.nav[data-page="library"]')) {
        window.setTimeout(() => renderBenchmarks(runtime.benchmarkResult || runtime.bootstrap.benchmarks));
      }
      const reviewItem = event.target.closest(".runtime-review-item");
      if (reviewItem) {
        event.preventDefault();
        event.stopImmediatePropagation();
        runtime.selectedReviewId = reviewItem.dataset.reviewId;
        runtime.reviewDirty = false;
        renderReviews(runtime.bootstrap.reviews, { force: true });
        return;
      }
      const vendorCandidate = event.target.closest("#page-review .vendor-grid .vendor");
      if (vendorCandidate) {
        event.preventDefault();
        event.stopImmediatePropagation();
        selectVendorCandidate(vendorCandidate);
        return;
      }
      if (event.target.closest("#start-run")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await createBatch();
        return;
      }
      if (event.target.closest("#page-review #play")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!runtime.audio) return;
        const review = runtime.bootstrap.reviews.find(
          (item) => item.id === runtime.selectedReviewId,
        );
        if (runtime.audio.paused) {
          if (
            runtime.audio.currentTime < review.start_s ||
            runtime.audio.currentTime >= review.end_s
          ) {
            runtime.audio.currentTime = review.start_s;
          }
          await runtime.audio.play();
        } else {
          runtime.audio.pause();
        }
        return;
      }
      const audioTrack = event.target.closest("#page-review .runtime-audio-track");
      if (audioTrack) {
        event.preventDefault();
        seekReviewAudio(audioTrack, event.clientX);
        return;
      }
      if (event.target.closest(".good-decision")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await submitDecision("good");
        return;
      }
      if (event.target.closest(".bad-decision")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await submitDecision("bad");
        return;
      }
      if (event.target.closest("#mark-unclear")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await submitDecision("unclear");
        return;
      }
      if (event.target.closest("#finish-early")) {
        configureFinishDialog("review");
        return;
      }
      if (event.target.closest("#confirm-finish")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (runtime.finishMode === "current_results") {
          await completeWithCurrentResults();
        } else {
          await completeReviewEarly();
        }
        return;
      }
      const check = event.target.closest(".runtime-benchmark-check");
      if (check) {
        check.checked
          ? runtime.selectedBenchmarkIds.add(check.value)
          : runtime.selectedBenchmarkIds.delete(check.value);
        updateBenchmarkSelection();
        return;
      }
      const benchmarkDetail = event.target.closest(".runtime-sample-detail");
      if (benchmarkDetail) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await openBenchmarkDetail(benchmarkDetail);
        return;
      }
      const benchmarkDelete = event.target.closest(".runtime-benchmark-delete");
      if (benchmarkDelete) {
        event.preventDefault();
        event.stopImmediatePropagation();
        requestBenchmarkDeletion(benchmarkDelete.dataset.benchmarkId);
        return;
      }
      if (event.target.closest("#sample-dialog .benchmark-delete")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        requestBenchmarkDeletion(runtime.activeBenchmarkId);
        return;
      }
      if (event.target.closest("#confirm-delete-benchmark")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await confirmBenchmarkDeletion();
        return;
      }
      if (event.target.closest("#sample-dialog .benchmark-edit")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        setBenchmarkEditMode(true);
        return;
      }
      if (event.target.closest("#sample-dialog .benchmark-cancel-edit")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        setBenchmarkEditMode(false);
        return;
      }
      if (event.target.closest("#sample-dialog .benchmark-save")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await saveBenchmarkRevision();
        return;
      }
      if (event.target.closest("#download-benchmarks")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await downloadBenchmarks(false);
        return;
      }
      if (event.target.closest("#download-filtered-benchmarks")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await downloadBenchmarks(true);
        return;
      }
      const conversationLink = event.target.closest(".runtime-conversation-link");
      if (conversationLink) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await openRuntimeConversation(conversationLink);
        return;
      }
      const conversationTurn = event.target.closest(".runtime-conversation-turn");
      if (conversationTurn) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const audio = document.querySelector("#drawer-audio");
        audio.currentTime = Number(conversationTurn.dataset.timeS || 0);
        syncRuntimeDrawerAudio();
        return;
      }
      if (event.target.closest("#close-conversation-drawer") && runtime.drawerConversation) {
        runtime.drawerConversation = null;
      }
      const reportAudio = event.target.closest(".runtime-report-audio");
      if (reportAudio) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await toggleReportAudio(reportAudio);
        return;
      }
      const proposedTagNavigation = event.target.closest(".runtime-open-proposed-tags");
      if (proposedTagNavigation) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const details = document.querySelector("#proposed-tag-details");
        details?.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      const proposedTag = event.target.closest(".runtime-create-proposed-tag");
      if (proposedTag) {
        event.preventDefault();
        event.stopImmediatePropagation();
        await createReportProposedTag(proposedTag);
      }
    },
    true,
  );
  document.addEventListener("input", (event) => {
    if (event.target.matches("#page-costs .custom-model")) {
      invalidateLlmPricing(event.target.closest("tr"));
    }
    if (event.target.matches("#page-review #manual-label")) {
      runtime.reviewDirty = true;
      const value = event.target.value.trim();
      const card = event.target.closest(".review");
      card.querySelector(".bad-decision").disabled = !value;
      card.querySelector("#current-proposed-label").textContent =
        value || copy("Waiting for manual entry", "等待手动填写");
    }
  });
  document.addEventListener(
    "keydown",
    (event) => {
      const conversationTurn = event.target.closest(".runtime-conversation-turn");
      if (conversationTurn && ["Enter", " "].includes(event.key)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const audio = document.querySelector("#drawer-audio");
        audio.currentTime = Number(conversationTurn.dataset.timeS || 0);
        syncRuntimeDrawerAudio();
        return;
      }
      const vendorCandidate = event.target.closest("#page-review .vendor-grid .vendor");
      if (vendorCandidate && ["Enter", " "].includes(event.key)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        selectVendorCandidate(vendorCandidate);
        return;
      }
      const audioTrack = event.target.closest("#page-review .runtime-audio-track");
      if (audioTrack && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const review = runtime.bootstrap.reviews.find(
          (item) => item.id === runtime.selectedReviewId,
        );
        if (!review || !runtime.audio) return;
        const current = runtime.audio.currentTime || review.start_s;
        const target =
          event.key === "Home"
            ? review.start_s
            : event.key === "End"
              ? review.end_s
              : Math.min(
                  review.end_s,
                  Math.max(review.start_s, current + (event.key === "ArrowRight" ? 1 : -1)),
                );
        runtime.audio.currentTime = target;
        updateAudioProgress(audioTrack, review, target);
      }
    },
    true,
  );
  ["benchmark-case-type-filter", "benchmark-language-filter", "benchmark-scenario-filter", "benchmark-source-filter"].forEach(
    (id) => {
      document.querySelector(`#${id}`).addEventListener("change", () => {
        runtime.benchmarkOffset = 0;
        refreshBenchmarks();
      });
    },
  );
  localizeBenchmarkTypeFilter();
  let benchmarkSearchTimer;
  document.querySelector("#benchmark-search").addEventListener("input", () => {
    clearTimeout(benchmarkSearchTimer);
    benchmarkSearchTimer = setTimeout(() => {
      runtime.benchmarkOffset = 0;
      refreshBenchmarks();
    }, 200);
  });
  const benchmarkPager = document.querySelectorAll("#page-library .library-pager button");
  benchmarkPager[0].addEventListener("click", () => {
    runtime.benchmarkOffset = Math.max(0, runtime.benchmarkOffset - 20);
    refreshBenchmarks();
  });
  benchmarkPager[1].addEventListener("click", () => {
    if (runtime.benchmarkOffset + 20 < runtime.benchmarkTotal) {
      runtime.benchmarkOffset += 20;
      refreshBenchmarks();
    }
  });
  document.addEventListener("change", (event) => {
    if (event.target.matches(".runtime-report-filter")) {
      filterReportCases(event.target.value);
    }
  });
  document.querySelectorAll(".language-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      window.setTimeout(() => {
        localizeBenchmarkTypeFilter();
        renderPricingStatus("asr");
        renderPricingStatus("llm");
        if (runtime.bootstrap) {
          modeBanner(runtime.bootstrap.fixture);
          renderSummary(runtime.bootstrap.summary);
          renderBatches(runtime.bootstrap.batches);
          renderReviews(runtime.bootstrap.reviews, { force: true });
          renderBenchmarks(runtime.bootstrap.benchmarks);
          renderScenarioTags(runtime.bootstrap.scenario_tags || []);
          renderEvaluationConfiguration();
          if (runtime.datasetAudit) fixtureReady(runtime.datasetAudit);
        }
        if (runtime.currentReport) renderReport(runtime.currentReport);
        if (runtime.drawerConversation) {
          renderRuntimeConversationDrawer();
          if (zh() && !runtime.drawerConversation.translations) {
            requestRuntimeDrawerTranslations(runtime.drawerConversation);
          }
        }
      });
    });
  });
}

async function initialize() {
  if (new URLSearchParams(window.location.search).get("gate2") === "1") return;
  installDatasetUploadShell();
  // Replace frozen prototype fixtures before any asynchronous setup so they
  // are never mistaken for live API data on a slow local service.
  renderBootstrapPlaceholder(copy("Loading real evaluation data…", "正在加载真实评测数据…"));
  await installPricingVersionControls();
  installEvents();
  installAccessibility();
  await refreshBootstrap();
  if (runtime.bootstrap) {
    fixtureReady(runtime.bootstrap.fixture);
  }
  runtime.poll = window.setInterval(() => {
    const hasRunning = runtime.bootstrap?.batches.some((batch) => batch.status === "running");
    if (hasRunning) refreshBootstrap({ quiet: true });
  }, 2000);
  runtime.elapsedPoll = window.setInterval(refreshVisibleElapsedTimes, 1000);
  refreshVisibleElapsedTimes();
}

initialize();
