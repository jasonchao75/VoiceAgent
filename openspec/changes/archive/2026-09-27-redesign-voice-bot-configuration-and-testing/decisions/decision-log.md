# Decision Log

## Status

- Recorded decisions: 2 confirmed
- Open product decisions: 0
- Last reviewed: 2026-09-27

## Decisions

### D-001 — 接受当前产品交付及已披露的证据边界

- Status: Confirmed
- Date: 2026-09-27
- Source question: 主体功能已验收后，是否接受缺少真实麦克风 WebCall/声学打断证据和历史不可变像素基线的边界并收口归档
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务 `codex://threads/01a0a4bf-81a0-74e3-84ac-159a97f0640c`；本轮归档确认消息
- Confirmation quote: “我已经验收过了，暂时没发现问题。”；“行，那你弄吧，接受已披露的内容”
- Decision: User Gate 2 通过。真实麦克风 WebCall/声学打断和历史不可变像素 baseline/diff ratio 保留为已接受的证据边界，不要求产品负责人补测，不阻塞本 Change 归档，也不得表述为已完成自动化验证。
- Reason: 当前功能已由产品负责人实际验收；缺口属于历史交付证据，不是已发现的产品缺陷。
- Consequences: 当前已有功能、API、浏览器测试、截图和真实 Chat/BYOK smoke 作为验收依据；未来若需要严格声学或像素回归，应作为独立验证工作补充。
- Updated artifacts: `tasks.md`、`verification/ui-checklist.md`、`verification/visual-diffs.md`、`verification/delivery-status.json`。
- Verification: 归档前运行 Change gate、独立验收和 OpenSpec 严格校验。

### D-002 — 主规格以当前已实现行为为准

- Status: Confirmed
- Date: 2026-09-27
- Source question: 旧主规格与已验收实现对登录方式和 Deepgram Flux 语速范围的描述不一致时采用哪一项
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务 `codex://threads/01a0a4bf-81a0-74e3-84ac-159a97f0640c`；用户针对规格冲突的批注与确认
- Confirmation quote: “这个可以直接用已实现的来吧？？”；“有的比如注释里面这个都已经是既定事实了。就不是未验证项了吧？”
- Decision: 登录方式以产品登录页和安全 Cookie 会话为准，不再以浏览器 Basic Auth challenge 作为产品入口；Deepgram Flux `/v2/speak` 语速范围以已实现并验收的 `0.5–1.5` 为准。
- Reason: 两项均为当前线上/代码的既定行为，而非待验证方案。
- Consequences: 合并 Delta 时直接修正主规格中的旧 Basic Auth 和 `0.85–1.15` 表述；不得把这种文档校准登记为风险或未验证项。
- Updated artifacts: `openspec/specs/bot-config/spec.md`、`openspec/specs/call-history/spec.md`、本 Change Delta 与归档记录。
- Verification: 合并后严格校验主规格，确认旧表述不再与当前行为冲突。
