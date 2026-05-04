# 团队协作与 Agents & Skills 指南

本项目开发由 OpenCode Agent 深度参与协作。请在开发前务必阅读项目根目录的 [`AGENTS.md`](../../AGENTS.md) 以及 `.opencode/skills` 下的相关 SOP。
- **核心红线**：禁止在核心管道使用同步阻塞代码；禁止将未验证的厂商适配器直接合入主干。

在 OpenCode 工作流中，合理的 Agent 角色切换与 Skill 调用是保证项目质量的关键。我们的项目沉淀了多种专门的角色（Agents）和标准作业程序（Skills），供团队成员在不同开发阶段使用。

## 1. 核心 Agent 角色介绍

项目中定义了三个核心 Agent 角色，各自负责生命周期的不同阶段，互不越界：

- 🕵️ **Vendor-Researcher (厂商调研员)**
  - **职责**: 负责调研 ASR/TTS/LLM 厂商接口，验证可用性，输出对接设计与选型矩阵。
  - **使用时机**: 当你需要接入一个新模型、新厂商，或者遇到厂商 API 报错需要翻阅官方文档时。
- 👷 **Integration-Developer (集成开发者)**
  - **职责**: 实现适配器、前端、Pipeline 管道以及对话状态机，交付全部代码与自测用例。
  - **使用时机**: 调研结束，明确了架构选型后，进入实质性的代码编写阶段。
- ⚖️ **Evaluation-Engineer (评测工程师)**
  - **职责**: 搭建自动化评测框架，量化抗噪、延迟、流畅度，输出独立评测报告。
  - **使用时机**: 新的 ASR/TTS 模块开发完成后，需要进行客观指标压测时。

## 2. 现有的 Skills (技能) 矩阵

Skills 是沉淀在 `.opencode/skills/` 目录下的 SOP、架构规范和防坑指南。

**核心架构与流程类**:
- `pipecat-integration`: **(核心，尚未完成)** 提供 Pipecat 框架的并发原则、帧流转规范及“提前思考(Thinking Ahead)”/“打断(Barge-in)”机制的实现 SOP。（尚未完成，只是AI写了初稿，待更新）
- `asr-survey`: 调研接入新 ASR 厂商或新模型的标准流程编排。

**厂商防坑指南 (Vendor Docs)**:
- `vendor-speechmatics`, `vendor-azure`, `vendor-soniox`, `vendor-tencent`, `vendor-deepgram`, `vendor-qwen`: 包含各厂商专属的 API 参数陷阱、签名鉴权避坑指南以及结构化文档兜底。开发或调研对应厂商时建议主动加载。

**协作辅助类**:
- `session-handoff`: 生成结构化的进度快照，以便结束长对话并在新会话中无缝续传。
- `write-a-skill`: 提取当前优秀实践，生成并固化新的 Skill。
- `to-prd`: 将讨论的上下文转换为 PRD 并提交为 Issue。

## 3. 规划中的 Skills (Roadmap)

随着项目的推进，我们计划逐步固化以下领域的 SOP：

- 🚧 `tts-survey`: TTS 厂商流式合成接口调研、延迟与自然度对比的标准流程 SOP。
- 🚧 `asr-evaluation`: ASR 专项自动化评测技能，涵盖各语种测试集跑测、WER/CER 计算及抗噪表现量化。
- 🚧 `freeswitch-integration`: FreeSWITCH / SIP 电话网关与 WebSocket 的对接规范、音频重采样(8KHz/16KHz)及信令控制 SOP。
- 🚧 `evaluation-metrics`: 通用评测指标及环境加噪脚本的标准用法（将与 asr-evaluation 等专项评测配合使用）。
- 🚧 `turn-detection-strategy`: 结合 VAD 信号与 LLM 语义的智能断句（Smart Turn Detection）算法调优指南。

## 4. Skills & SubAgent 调用机制与建议

- **隐式调用（默认）**：直接通过自然语言下发指令（如：“去调研 Speechmatics”）。Agent 会根据关键字自动匹配并加载对应的 Skill 规范。
- **显式调用（推荐）**：对于明确的阶段任务，建议在对话开始时显式切换（如：“当前角色：Integration-Developer。请加载 `pipecat-integration` 技能，开始搭建基础管道”）。这能让 Agent 极度聚焦，避免代码跑偏。

## 5. Change 文档使用规范 (产品经理指南)

**核心是借用OpenSpec工作流程**
- **explore**：直接让 AI 问 5 个边界问题
- **new**：手动或让 AI 创建 `docs/changes/active/add-xxx/`
- **ff**：让 AI 根据 proposal 生成 `spec.md` 和 `tasks.md`
- **apply**：确认后让 AI 按 tasks 执行
- **verify**：让 AI 对照 spec 检查实现
- **archive**：完成后把目录移到 archive

Change 是本次开发任务的轻量级“需求说明书”。请注意，**Change 文档不是每个需求都要写**。

**5.1 简单判断标准**
- 如果只是“改一下”，不用写 Change。
- 如果需要“先对齐做什么、不做什么、什么算做对”，就开 Change。
- 凡是 AI 可能自作主张、做偏、做多的需求，一定要先写 Change 钉住边界。

**5.2 什么时候必须写 Change？**
适用于“需要先想清楚边界”的需求，尤其是：
- 搭建或调整核心 pipeline；
- 接入新的 ASR / TTS / LLM adapter；
- 实现 barge-in 打断、turn detection；
- 建立自动化评测；
- 做 WebSocket demo UI；
- 会影响延迟、稳定性、音频格式、评测指标的改动。

**5.3 什么时候不需要写 Change？**
- 改 README 或普通说明文档；
- 补厂商调研报告；
- 修 typo；
- 调整一个测试脚本参数；
- 小范围更新 skill；
- 一句话就能验收的小 bug。

**5.4 产品经理与 AI 的分工**
- **产品经理**：负责写清楚业务意图、核心边界和验收标准。
- **AI 助手**：可以协助您把凌乱的想法整理成结构化的 `proposal.md`、`spec.md` 和 `tasks.md`。
- **执行规范**：产品经理确认这些文档无误后，再让 AI 或研发开始写核心代码执行。

**5.5 目录与文档结构**
开 Change 时，请在以下目录建立三个轻量级文档（做完后会整体移动到 archive 归档）：
```text
docs/changes/active/{change-name}/
├── proposal.md  # 提案
├── spec.md      # 技术方案
└── tasks.md     # 执行步骤清单
```

## 常用任务收尾提示词

```text
完成后请运行与本次改动相关的本地检查；如果已推送，请查看 GitHub Actions 结果并修复失败项。测试过程中如果产生临时文件、日志、缓存、测试录音或测试数据库，请汇报路径；除非这些文件需要作为证据保留，否则不要提交，并清理无用脏数据。
```