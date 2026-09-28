# User Gate 2 产品验收单

- Change：`add-streaming-asr-providers`
- 提交日期：2026-09-28
- 当前状态：**User Gate 2 已通过（D-021）**
- 当前行为规格：PRD V1.0.17
- 冻结原型 SHA-256：`b6835ca7da9f0ee120081bb682a319f60be296029800c6b83e28a111b400b277`
- User Gate 1 依据：D-014，以及 Bot 维度凭证修订 D-015
- 独立验收结论：PASS

## 本次验收范围

1. 正式 Bot Settings 的 ASR 配置抽屉支持 Deepgram Flux/Nova-3、Speechmatics Enhanced、Soniox `stt-rt-v5` 和 AssemblyAI Universal-3.5 Pro，并按照服务端 Catalog 展示和校验各 Provider/model 的专属字段。
2. API Key 按 Bot、组件和 Provider 相互隔离，经加密后保存；API 响应和日志均不返回明文或密文。
3. 统一 ASR Service 会把各厂商结果转换为公共 Final 和 Turn 事件；AssemblyAI Agent Context 与 TTS 并行更新，具备超时控制、Turn 归属和历史记录。
4. Engineering Checkpoint A/B/C 均已通过：348 项 Python 测试、Ruff、mypy、前端生产构建、18/18 项桌面与窄屏正式页面测试，以及四个目标分支的真实外部流式验证。
5. 独立 Change Verifier 已给出 PASS；当前没有 Open 的已知问题、未验证项或未披露事项。

## 建议重点检查

1. 进入 **Bot Settings → ASR 配置**，依次切换 Deepgram、Speechmatics、Soniox、AssemblyAI。
2. 检查 Model、Language、Turn Detection、Advanced 字段是否符合 PRD 与原型。
3. 检查 API Key 位于 Advanced 之后，并且不同 Bot、不同组件和不同 Provider 之间不会串用。
4. 检查桌面与窄屏抽屉没有横向滚动，字段、开关和错误状态可正常使用。
5. 检查 AssemblyAI 的 Mode、Turn 参数和 Agent Context 行为是否符合产品预期。

## 验收证据

- `verification/independent-review.md`：独立验收报告
- `verification/external-real-asr-2026-09-28.md`：四个目标分支的真实流式验证
- `verification/ui-checklist.md`：UI 验收清单
- `verification/actual-gate-2-*.png`：各 Provider 的桌面与窄屏截图
- `decisions/decision-log.md`：产品决策记录

## 产品负责人操作

请检查上述产品行为与证据：

- 如果符合预期，请明确回复：**“通过 User Gate 2”**。
- 如果不符合预期，请说明具体 Provider、字段、状态或交互问题。

产品负责人已于 2026-09-28 明确回复“通过User Gate2”。该确认记录为 D-021，并授权合并 Delta Specs 与归档 Change。
