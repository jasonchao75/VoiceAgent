# Engineering Assumptions

仅记录不改变用户可观察产品行为、风险低且容易回退的工程细节。涉及结果口径、费用、合规或用户体验的内容必须升级到 `open-questions.md`。

## Status

- Active assumptions: 3
- Rejected product assumptions: 6
- Last reviewed: 2026-09-17

## Active reversible engineering assumptions

### EA-001 — 本地 Engineering Checkpoint B 验证采用单进程异步执行与 SQLite

- Scope: local test environment only
- Rationale: 可在不改变产品契约的前提下验证任务编排、检查点与页面状态。
- Reversal: 生产部署前可替换为独立 worker/queue 和生产数据库；不得把本地进程存活当作生产可靠性证据。

### EA-002 — 页面采用短轮询读取服务端状态

- Scope: local batch progress UI
- Rationale: 服务端仍是状态真相源，轮询仅影响刷新方式。
- Reversal: 后续可替换为 SSE/WebSocket，不改变阶段状态机和结果口径。

### EA-003 — UI 只展示分类后的安全错误

- Scope: user-visible diagnostics
- Rationale: 原始供应商响应可能含敏感内容或凭证信息；详细响应仅进入受控审计证据，不进入普通日志和页面。
- Reversal: 可增加经脱敏、授权的诊断视图，但不能降低密钥与数据保护要求。

## Rejected as engineering assumptions

以下内容会改变产品行为、成本或验收结论，不能由开发默认决定：

- 第二轮按每个 candidate event 发起一次外部请求；已升级为 Q-001。
- `candidate entries` 等同于唯一 Case 或外部调用次数；真实数据存在重复项，不能等同。
- 每次 LLM 调用固定 `$0.02` 可代表实际成本；它只是预算预留估算。
- 发生真实供应商调用即可证明 Checkpoint B/C 或 User Gate 2 完成；真实调用不等于结果正确、幂等、可恢复或已验收。
- 敏感数据留存不是工程假设；用户已在 PD-011 确认固定留存 10 年且不提供设置入口。
- Checkpoint A fixture 中的数量或文案可作为真实运行目标；fixture 只用于核对冻结页面基线，不证明真实业务结果。
