# Independent Review — Qwen native DashScope and grouped LLM reliability

- Status: **PASS**
- Date: 2026-09-21
- Scope: PD-045 grouped LLM reliability plus PD-046 Qwen native/compatible integration (`KI-130` through `KI-148`)
- Reviewer boundary: independent verification only; no product implementation, paid provider call, deployment, push, or production-data mutation was performed

## Decision

The reviewed increment passes deterministic independent verification. The implementation now preserves the administrator-selected Qwen protocol, accepts the approved shared, premium and workspace-native URL families, routes `qwen3.8-max` to native multimodal generation, and keeps compatible mode available. Both evaluation passes use a model-specific 1,000,000-token context policy, total reasoning-plus-answer output caps, JSON Object where the selected Qwen generation supports it, application schema validation, durable attempt numbering, cost reservation, usage accounting and stable idempotency keys.

The earlier specification conflict is closed: verified `qwen3.8-*` models enable JSON Object with Thinking, while older unverified Qwen models retain the conservative no-JSON-mode fallback. This PASS covers static, mock and local deterministic evidence only. It does not claim a real paid `qwen3.8-max` diagnostic/evaluation or current-source dual-viewport browser run; those remain disclosed as `UV-023` and `UV-022`.

## Verified behavior

- URL and routing: shared `dashscope.aliyuncs.com/api/v1`, user-confirmed `prem.dashscope.aliyuncs.com/api/v1`, and workspace `*.maas.aliyuncs.com/api/v1` register as Qwen; unsupported schemes, hosts, paths, credentials, ports, query strings and fragments are rejected before an external call. Native `qwen3.8-max` uses `services/aigc/multimodal-generation/generation`; compatible-mode remains on the OpenAI client.
- Model/catalog/UI: `qwen3.8-max` is visible in Resource Connections, Cost Settings and New Evaluation. Successful Qwen connection/model tests request exact catalog registration, saved `*.maas.aliyuncs.com` Bot connections are recognized, and executor fallback resolves the predefined Qwen 3.8 family.
- Output and Thinking: native and compatible Qwen 3.8 requests use `max_completion_tokens`; Pass 1 disables Thinking, Pass 2 enables it, both send JSON Object, and legacy Qwen keeps `max_tokens` plus the conservative Thinking fallback. SDK retries are disabled so the application owns retry count and ledger identity.
- Packing/checkpoints: Pass 1 keeps whole conversations atomic and uses exact minimum-safe grouping; Pass 2 keeps whole conversation/Case units atomic. The qwen3.8 policy uses the official 1,000,000 context and 131,072 output ceilings, keeps a 120k batch in one group, and rejects a 970k unit after output/reasoning/safety reserves. Failed groups retain membership, checkpoint every paid attempt, and resume with monotonic attempt numbers.
- Usage/cost/idempotency: independent executor mocks exercised native and compatible Pass 1/Pass 2. Both parsed 100 input / 40 cached / 30 reasoning / 20 visible-output tokens, recorded the expected CNY cost, used distinct reserve and ledger keys per stage/attempt, and released no settled reservation.
- Diagnostics: native synchronous diagnostics no longer fabricate first-token latency, HTTP 400/401/404/429 retain actionable categories, reasoning-only provider responses are accepted, and diagnostic clients do not multiply retries.
- UI semantics: durable conversation checks and external request groups are presented separately. Static UI contracts and the production frontend build pass.
- Shared workspace: no unrelated user change was reverted or overwritten by this verification.

## Contract sources

- Alibaba Model Studio Base URL overview: `https://help.aliyun.com/en/model-studio/base-url`
- Alibaba native DashScope API reference: `https://help.aliyun.com/en/model-studio/qwen-api-via-dashscope`
- Alibaba Qwen3.8 Max model limits: `https://help.aliyun.com/en/model-studio/qwen3-8-max`
- Alibaba structured output reference: `https://help.aliyun.com/en/model-studio/qwen-structured-output`
- Alibaba OpenAI-compatible chat reference: `https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions`

## Reproducible evidence

- Change gate: **PASS**, 0 errors, 10 disclosed warnings and 1 intentionally open supplier-bill reconciliation task.
- Focused Qwen/evaluation/API/UI-contract suite: **134 passed**, with the two already disclosed dependency deprecation warnings.
- Full repository suite: **220 passed**, with the same two warnings.
- Scoped Ruff: **PASS**.
- Mypy across `src/llm/qwen_dashscope.py`, `src/llm/diagnostics.py`, `src/evaluation`, and `src/api.py`: **PASS** (15 source files).
- Frontend production build: **PASS**.
- Independent native executor mock: **PASS** for Pass 1/Pass 2 request URL/body, Thinking, JSON Object, `max_completion_tokens`, cached/reasoning usage, CNY cost and reserve/ledger idempotency.
- Independent compatible executor mock: **PASS** for Pass 1/Pass 2 request body, zero SDK retries, Thinking, JSON Object, `max_completion_tokens`, cached/reasoning usage, CNY cost and reserve/ledger idempotency.

## Remaining boundaries

- `UV-023`: no external-real request was sent to `prem.dashscope.aliyuncs.com` or `qwen3.8-max` in this review.
- `UV-022`: the current source was not exercised through the dual-viewport browser suite; static UI contracts and the production build passed.
- Existing unrelated/open warnings remain recorded in `delivery-status.json`; none is newly hidden by this PASS.
