# Tasks: Add Streaming ASR Providers

## 0. User Gate 1 — PRD and Prototype

- [x] 创建评审版 PRD。
- [x] 创建 Delta Specs、design、decision files 与 delivery manifest。
- [x] 创建可直接运行的 ASR Drawer 高保真原型。
- [x] 创建原型映射、UI annotations、状态矩阵和验收清单。
- [x] 按当前 Deepgram UI 与四家真实参数修订 Provider 下拉、Language 控件和 Advanced 原型。
- [x] 以 Speechmatics Feature Discovery 校正完整 Language Pack、domain 联动与 `model=enhanced` 字段。
- [x] 以 Soniox Get models Catalog 校正 `language_hints[]` 的可搜索多选、移除与空值交互。
- [x] 按 Deepgram V1/V2 官方契约新增 Nova-3 PRD/原型分支，并与 Flux 的语言、Turn 和 Advanced 参数彻底分离。
- [x] 关闭 Q-001，并同步 PRD/Spec/design/prototype。
- [x] 关闭 Q-002，并同步 PRD/Spec/design/prototype。
- [x] 关闭 Q-003，并同步 PRD/Spec/design/prototype。
- [x] 用户确认 Gate 1，记录确认原话、来源、日期并冻结唯一 SHA-256 baseline。
- [x] 关闭 Q-004：Soniox 固定 Provider native；Nova-3 固定 Off；同步 PRD/Spec/design/prototype。
- [x] 纠正 Off 契约：Speechmatics 映射 Fixed + 正数 silence trigger；Nova-3 保留正数 endpointing；AssemblyAI 因无 Provider-side VAD-only 模式而禁用 Off。
- [x] 校正 Speechmatics 句子 Segment、Maximum EOU delay 和 punctuation overrides 的原型/PRD/Spec 契约。
- [x] 统一原型 Switch 为现网页 34×20 px 样式，并防止长文案导致控件收缩。
- [x] 关闭 Q-005：AssemblyAI Mode 自动回填三个 Turn 预设值并允许修改；`vad_threshold` 保持独立。

## 1. Configuration and Credentials

- [x] 实现四家 Provider、五个模型分支的 discriminated ASR config 与 Catalog 验证。
- [x] 关闭 Q-006：D-015 取消全局 Connection，本期凭证按 Bot、组件与 Provider 保存。
- [x] 扩展 Bot 级 Provider-aware 凭证持久化并保留旧 Deepgram Bot 行为。
- [x] 更新 Session Request/Lease/secret clearing 与安全错误。

## 2. ASR Registry and Adapters

- [x] 新增 ASR Service 抽象与 Provider Registry，并让 Pipeline 通过 Registry 构造服务。
- [x] 新增 Provider capability 声明并保证 Native/Off 只有一个最终裁决来源。
- [x] 为各 Provider/model 实现 Native/Off 能力映射；Off 仅消费可证明的 VAD/固定静音完整边界，普通分块 Final 不误触发 LLM，Self-developed/Flux `ForceEndTurn` 不在本 Change 范围。
- [x] 接入 Speechmatics Realtime Enhanced adapter 与独立自测。
- [x] 定向验证并修正 Pipecat 1.8.1 `split_sentences` → `speech_segment_config.emit_sentences` 路径：无 Key 构造与 mock frame 已证明 `AddSegment` 不触发 LLM、`EndOfTurn` 仅提交一次；external-real 仍由 4. Verification 的授权任务单独跟踪。
- [x] 接入 Soniox stt-rt-v5 adapter 与独立自测。
- [x] 接入 AssemblyAI universal-3-5-pro adapter、Agent Context 与独立自测。
- [x] 验证 Assistant Turn 向 TTS 与 AssemblyAI Context 并行分发，任一失败不串行阻塞另一分支。
- [x] 保持 Deepgram Flux regression coverage。
- [x] 接入 Deepgram Nova-3 V1 Streaming adapter、独立自测与 Flux/Nova 参数隔离回归。

## 3. Production UI — Engineering Checkpoint A/B

- [x] Checkpoint A：正式 Bot route/DOM 使用固定 fixture，对照冻结原型。
- [x] 实现 Provider/model/language Catalog 联动与专属字段。
- [x] 实现 Advanced 后的当前 Bot Key keep/replace 状态与字段级错误。
- [x] Checkpoint B：同一页面接真实 API、SQLite、刷新/重启与失败恢复。

## 4. Verification — Engineering Checkpoint C

- [x] 单元、API、Pipeline、migration、security、history 回归。
- [x] 桌面/390px 状态矩阵、无横向溢出、键盘与可访问性检查。
- [x] 取得逐次授权后执行四个目标分支 external-real 最小连通测试。
- [x] 运行 `python3 scripts/quality/verify_change.py add-streaming-asr-providers`。
- [x] 委派独立 Change Verifier 并取得 `PASS`。
- [x] 提交 User Gate 2；不得自行填写产品接受。

## 5. User Gate 2 feedback revision

- [x] 实现 D-019 紧凑次级 Catalog 刷新按钮及 hover/loading/disabled 状态。
- [x] 实现 D-020 Soniox/AssemblyAI `code (language name)` Catalog 与 UI 显示。
- [x] 更新冻结原型 SHA-256、PRD、Delta Spec、design 与验收文件。
- [x] 复跑桌面/390px UI、后端回归、Change gate 与独立验收。
- [x] 产品负责人通过 User Gate 2（D-021），允许合并主规格并归档 Change。
