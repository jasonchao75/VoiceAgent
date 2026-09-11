# Change: Redesign Voice Bot Configuration and Testing

## Why

当前 Bot 编辑器把机器人自身配置、ASR/LLM/TTS 厂商参数和凭证混在同一页面，配置项过多且层级不清。测试入口与历史页面也未完整反映真实的 ASR → LLM → TTS 链路：Chat test 缺少 TTS、逐 Turn 延迟没有就近展示，Web call 缺少实时字幕，Sessions 无法在列表之外查看录音、字幕和指标详情。

本 Change 从单一“通话内语速控制”扩展为一次完整的 Voice Bot 配置与测试体验改版，并将语速控制、Flux ASR Bot 级参数、LLM Thinking、测试页和历史详情作为同一套交互基线管理。

当前实现已出现与确认原型不一致但静态检查仍通过的问题。本 Change 同时补充轻量 UI 交付保障：精确标注、状态矩阵、固定 fixture、分阶段 Gate、固定视口截图和人工确认的视觉 baseline；不改变原有业务目标。

## What Changes

### Bot 编辑器信息架构

- 采用组件化 Voice pipeline：ASR、LLM、TTS 独立选择，点击卡片后在非模态右侧抽屉配置，抽屉挤压而非遮挡主工作区。
- Bot settings 主页面只保留 Bot 自身配置（名称、Opening message、System prompt）；删除重复的 Primary language。
- 所有 provider/model 参数及 API Key 归入对应组件抽屉；组件卡片只展示有明确来源的配置摘要，不展示虚构 latency。
- 左侧产品栏本期仅展示 VoiceAgent，并支持图标态与图标+名称态收缩/展开；账户和 SIP line 管理延期。
- 顶部仅保留 Bot settings、Sessions、Advanced；Advanced 本期仅承载 Bot 的 LLM timeout Fallback script，Evaluation 延期。

### ASR 配置

- 本期仅支持 Deepgram / Flux ASR；provider、model、language 由后端 capability catalog 提供。
- Language 仅有 English 与 Automatic；Automatic 明确仅覆盖十种语言，并支持可空、多选的 language hints。
- Flux ASR 业务参数按 Bot 保存，禁止使用全局配置：EOT threshold、EOT timeout、keyterms、profanity filter、numerals、redact。
- Keyterms 使用未转义的逐行文本，空格由系统编码；不暴露未被当前 Pipeline 消费的 Eager EOT，也不添加 Flux 不支持的 endpointing、smart detection 或 noise suppression。
- 当前 WebCall 输入固定为 mono Linear16 PCM 16 kHz，不提供 8 kHz 选项。

### LLM 配置与诊断

- LLM Advanced 提供 Thinking override：Provider default、Off、Minimal。Model 为自由输入时前端不得根据名称猜测支持能力。
- Streaming 保持默认开启，不作为配置项展示。
- 保留 `Test LLM connection`，使用当前未保存的 endpoint/model/key/Thinking 配置进行真实探测，并展示连通状态和实测 TTFT；不兼容参数由诊断结果明确返回。

### TTS 配置与通话内语速

- 基础配置截至 Initial speed；其后统一收进一个 Advanced，顺序为 TTS text aggregation、Conversational speed control、provider-specific tuning。
- ElevenLabs 与 Deepgram Flux TTS 必须完整联动 model、Key、Voice Library、Speed 范围和 Advanced 参数。
- ElevenLabs Voice Library 需先提供 Key 才加载账户音色，并保留 Custom voice ID；Deepgram Flux 官方音色目录无需 Key 即可浏览，且不展示 Custom voice ID。
- Voice Library 支持搜索、语言/口音和性别筛选；列表和已选音色以名称首字母自动生成 A–Z 头像。
- 新增 Bot 级通话内语速控制及步长；运行时状态仅属于当前会话，并分别映射到 Flux `Configure` 与 ElevenLabs 非 v3 `voice_settings`。Eleven v3 不伪装支持精确语速。

### Test bot 与 Sessions

- Test bot 提供独立 Chat test 与 Web call test 二级页面。
- Chat test 仅绕过 ASR，仍执行 LLM + TTS；支持 Start/End、Opening message 播报、TTS playback 和文本发送。Agent 播放期间发送文本记录为 barge-in。
- Web call test 展示 Caller 与 Agent 双向实时字幕；原型中的 `Simulate caller turn` 仅用于交互演示，正式产品不得出现。
- 每条 Agent 回复下方就近展示所属 Turn 的 E2E latency 与分项。Chat 包含 LLM splicing、LLM TTFT、TTS initial、TTS TTFT、playback；Web call 在相同结构上增加 ASR final。
- Sessions 保持逐条列表和时间筛选；点击 View 后打开可收起的非模态右侧详情抽屉，展示历史用户上行录音、字幕及逐 Turn 指标。录音不包含 Agent TTS；Chat test 无用户录音。

### UI 交付保障

- 原型必须记录基准视口、断点、视觉 token、容器尺寸、间距和完整交互状态，并映射到 Delta Scenario。
- 原型与正式页面使用同一份稳定 fixture；动态时间、动画、远程数据和密钥不得进入视觉基线。
- Gate 1 确认规格、原型、标注、状态矩阵和 baseline；Gate 2 验收静态页面壳；Gate 3 完成功能、可访问性与视觉回归后提交最终验收。
- 视觉回归优先采用 Playwright 固定视口截图的轻量方案；新增 dev dependency、CI job 和 baseline 生成命令必须在本 Change 再次确认后实施。

## Deferred / Not in Scope

- Evaluation 页面、Bot/Customer speaks first、System prompt 自动生成。
- 账户管理、SIP line 管理、8 kHz WebCall 输入。
- 基于 Eager EOT 的 speculative LLM 执行、取消和上下文回滚。
- 将原型示例延迟或 `Simulate caller turn` 带入生产。

## Impact

- Affected specs: `bot-config`, `voice-pipeline`, `call-history`
- Affected code: Bot schema/storage/API、capability catalog、Bot editor、LLM diagnostic、Chat/Web call test、Sessions、ASR/TTS adapters、session speed controller、UI tests and observability
- Provider dependencies: Deepgram Flux ASR、Deepgram Flux TTS `/v2/speak`、ElevenLabs streaming TTS、Custom OpenAI-compatible LLM endpoints
- Change dependencies: `add-flux-voice-controls` and `add-call-history-and-metrics` establish existing provider controls and retained recording/metric contracts and must be reconciled before archive

## Delivery artifact changes

- Change-local: update `proposal.md`, Delta Specs, `design.md`, `tasks.md`, `prototypes/README.md` and `verification/ui-checklist.md`; add `prototypes/ui-annotations.md`, `prototypes/ui-state-matrix.md`, `verification/visual-diffs.md` and baseline/actual/diff evidence directories.
- Repository reusable: update `AGENTS.md`; add `docs/engineering/ui-prototype-delivery.md` and templates under `docs/engineering/templates/ui-delivery/`; add deterministic fixture guidance and sample data under `tests/ui/fixtures/`.
- Pending Gate 1 approval: Playwright configuration, screenshot/diff scripts, frontend dev dependency and any CI workflow modification. None are introduced by this proposal update.
