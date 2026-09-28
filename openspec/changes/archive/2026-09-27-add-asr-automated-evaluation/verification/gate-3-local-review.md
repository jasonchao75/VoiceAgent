# Engineering Checkpoint B 本地集成运行时 — 当前状态

状态：最新源码已按 PD-025 授权重建并运行；Checkpoint C 与 User Gate 2 尚未完成
更新日期：2026-09-17
入口：`http://127.0.0.1:8000/evaluation.html`

## 当前真实状态

- 端口 8000 正在运行本轮最新验收容器，健康检查通过；保存的资源连接和真实 56 通源数据在容器重建后仍可用。
- 运行时解析真实的 56 份逐通 Excel、56 份完整 MP3 和 56 份纯用户 WAV，共 853 个事件，其中用户事件 381 个。
- 数据包当前为 0 个阻断问题、55 个参考警告、56/56 通可运行。历史时间倒退和 duration 偏差只作审计提示，不再阻止开始。
- `EV-20260916-1400` 已按 PD-010 标记为 audit-only：只保留可追溯证据，正式报告接口拒绝访问，且不计入正式指标、人工复核、Benchmark 或 Gate 3。真实 ASR/LLM 新结果只能由用户在平台显式启动后产生。
- Soniox、Speechmatics、ElevenLabs、DeepSeek 和 Qwen 的加密连接在容器重建后仍存在；API 只返回脱敏元数据。
- Benchmark 已支持 All/Good/Bad 筛选、每页 20 条、详情、编辑为不可变新修订、跨页选择和异步 ZIP 导出。
- 批次费用按 ASR/LLM 分账，保留供应商原币，并使用批次冻结的 CNY→USD 汇率计算统一美元总额。

## 本轮验证证据

- 全量 Python 测试：166 passed；其中 Evaluation 定向测试 57 passed，质量门禁测试 13 passed。
- Evaluation Playwright：70 passed，覆盖 desktop 与 narrow 两个视口。
- 本 Change 涉及的 Evaluation 代码 Ruff、Mypy 与前端生产构建通过；前端已按应用、Pipecat client 和 transport 拆包，最大生产 chunk 为 359.47 kB，不再触发 500 kB 警告。仓库全量 Ruff 仍被范围外旧脚本的 69 项既有问题阻断（KI-048）。
- 执行过程新增不含转写、音频或密钥的结构化指标：阶段/供应商请求、重试、Schema 失败、耗时、队列深度及分账成本。
- Change 门禁：0 errors；仍有公开警告和未完成任务，不构成 Checkpoint C 或 User Gate 2 完成声明。

## 尚未完成

- 真实三家 ASR、两轮 LLM、真实 token 账单和厂商失败恢复未由本构建重新验证；PD-018 禁止 Agent 代用户执行付费重测。
- 动态 Token 装箱的模型特定上限仍需平台真实运行验证。
- Q-009 已按 PD-025 选择分组输出：冻结 Prompt、原型、运行时预览和执行器统一使用 `request_group_id`、`results[]` 与 `positioning_quality`；后端 57 项和定向双视口浏览器回归通过，尚未进行真实厂商重测。
- audit-only 页面已在本地浏览器验证：隔离说明、历史阶段/成本证据和候选明细可读；正式 Manual review 与 Benchmark 总数均为 0。
- 独立验收尚未通过，产品尚未给出 User Gate 2 最终验收。

## 验收边界

用户现在可以检查页面、配置、导入、筛选、编辑、播放和任务控制。点击“确认并开始评测”会触发真实外部调用并产生费用，应由用户自行决定何时执行。当前文档不得用于宣称 Checkpoint C 或 User Gate 2 已通过。
