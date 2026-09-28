# Independent Change Review

## Verdict

**PASS** — 归档前独立验收通过。此前 B-001/B-002 已修复并复验；产品验收决定、两用户 Gate、三研发检查点和已披露证据边界均可追溯。

Review date: 2026-09-27
Reviewer role: independent Change verifier
Scope: `redesign-voice-bot-configuration-and-testing`

## Resolved findings

### B-001 — Voice Bot UI 固定 fixture 已可复现

- `frontend/tests/ui/voice-bot.spec.js` 现显式读取 `tests/ui/fixtures/voice-bot-editor.json`，只拦截 Bot/History 数据接口；页面仍访问正式 `/` 路由并操作正式组件/DOM，不是另造静态页面壳。
- fixture 以固定 ID、时间、两种 TTS provider 和一条 Session 覆盖 Bot editor、provider 切换、Sessions 与 Advanced 状态，不包含密钥或外部调用。
- 独立复验使用隔离的空 `VOICE_AGENT_DATA_DIR` 和临时 evidence 目录；桌面 `1440×1000` 与窄屏 `1024×1000` 共 14/14 通过。
- Checkpoint A 的固定 fixture 页面、Checkpoint B 的真实 API/持久化历史证据，以及 Checkpoint C 的功能/可访问性/响应式复验保持区分；fixture 与真实路径共享正式 UI。

### B-002 — 工程运行文档已与当前登录行为一致

- `docs/engineering/english-flux-voice-agent.md` 现明确描述产品内登录页和安全 Cookie 会话，不再把浏览器 Basic Auth challenge 当作产品入口。
- 历史环境变量名仅作为共享账号凭证来源保留，与 D-002 和当前实现一致。

## Accepted decisions and evidence boundaries

- **D-001 valid:** 决策记录包含日期、当前任务链接和用户原话；用户明确接受现有产品交付，以及 UV-001/UV-002 两项历史证据边界。
- **D-002 valid:** 产品内登录页 + Cookie 会话、Deepgram Flux speed `0.5–1.5` 均可由当前代码与测试验证，是已实现事实，不是风险或未验证项。
- **UV-001 honest exclusion:** 真实麦克风 WebCall/声学打断没有 retained external-real 证据；文档未把它写成已测试通过。
- **UV-002 honest exclusion:** 没有不可变截图 baseline、checksum 和像素 diff ratio；`baseline/` 与 `diff/` 未伪造产物，`visual-diffs.md` 使用 `—` 并明确说明边界。
- `tasks.md` 已将 2026-09-10 Gate 3 记录改为明确的历史时点和过去时，并链接 D-001 的最终处置，不再与当前状态冲突。

## Reproduced checks

| Check | Result | Evidence boundary |
|---|---|---|
| Change delivery gate | PASS | `python3 scripts/quality/verify_change.py redesign-voice-bot-configuration-and-testing` → 0 errors, 0 warnings |
| Delta strict validation | PASS | `openspec validate redesign-voice-bot-configuration-and-testing --strict` |
| Backend targeted tests | PASS | 41 passed: auth, bot persistence/validation, speed control, pipeline, session |
| Frontend production build | PASS | Vite build completed |
| Auth Playwright suite | PASS | 4/4 across 1440×1000 and 1024×1000; product login, Cookie/Bearer separation, logout and overflow |
| Voice Bot Playwright suite | PASS | 14/14 against an isolated empty database; fixed Bot/History fixture on production route/components/DOM |

No external provider call, paid API call, production mutation, credential read, or baseline update was performed.

## Trace of implemented facts

- Cookie website session and call Bearer separation: `src/auth.py`, `src/api.py`, `frontend/tests/ui/auth.spec.js`.
- Deepgram Flux range `0.5–1.5`: `src/bots/models.py`, `src/bots/validation.py`, `src/session.py`, `src/pipeline/voice_agent.py`, `frontend/src/main.js`, and `tests/test_bots.py`.
- Fixture/production UI boundary: `frontend/tests/ui/voice-bot.spec.js` consumes `tests/ui/fixtures/voice-bot-editor.json`, intercepts only Bot/History data, and exercises the production `/` route, components and DOM.

## Archive disposition

The Change is eligible for main-spec merge and archive. UV-001/UV-002 remain explicitly accepted evidence boundaries and must stay recorded in the archived Change; they are not converted into completed external-real or pixel-diff verification.
