# VoiceAgent Core

基于 ASR + LLM + TTS 三段式架构构建的低延迟、可打断实时语音交互机器人（Voice Agent）。

## 🌟 核心特性与项目目标

本项目旨在解决传统语音机器人的四大痛点：**抗噪差**、**端到端延迟高**、**机器人抢话严重**、**无法自动化评测**。

- **极低延迟 (Thinking Ahead)**：不再等待用户一句话完全说完（Final），而是利用 ASR 吐出的中间结果（Partial）提前异步请求 LLM 进行思考。
- **智能打断 (Barge-in & Smart Turn Detection)**：结合 VAD 与语义分析，当用户开口时瞬间中断 TTS 播放和 LLM 生成，避免机器人“自说自话”。
- **全异步流式管道 (Pipecat)**：底层彻底抛弃复杂的锁与状态机，采用 **Pipecat** 框架。将音频流、文本流抽象为 Frame，在各个处理器（Processor）中并发流转。
- **传输层无关**：解耦底层传输协议，支持通过 WebSocket 直连 FreeSWITCH / SIP 电话网关。

## 🏗 技术栈

- **核心调度框架**: [Pipecat](https://github.com/pipecat-ai/pipecat)
- **开发语言**: Python 3.11+ (纯 `asyncio` 架构)
- **ASR (语音识别)**: 统一适配器接口，当前重点支持 Speechmatics、Azure、Soniox 等。
- **LLM (大语言模型)**: 流式对接各类大模型。
- **TTS (语音合成)**: 统一适配器接口，支持 ElevenLabs / Minimax 等。
- **测试与评测**: 自定义基于 jiwer 的 WER/CER 自动化评测与延迟探针。

## 📂 项目结构概览

```text
voice-agent/
├── src/
│   ├── asr/              # ASR 厂商流式适配层
│   ├── llm/              # LLM 接口与思考策略层
│   ├── tts/              # TTS 厂商流式适配层
│   └── pipeline/         # Pipecat 核心并发管道编排
├── configs/              # 厂商及运行时配置 (不入库敏感信息)
├── docs/                 # PRD、选型报告、会议记录
├── scripts/              # 本地测试与自动化评测脚本
├── benchmarks/           # 评测用音频数据集
└── AGENTS.md             # AI Agent 开发协作规范与红线
```

## 🚀 快速开始 (WIP)

*本项目正处于核心 Pipeline 重构与 Pipecat 落地阶段，完整运行脚手架即将发布。*

1. **环境准备**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt # (待提供)
   ```

2. **配置密钥**:
   复制 `.env.example` 到 `.env`，填入相应的厂商 API Keys：
   ```bash
   SPEECHMATICS_API_KEY=your_key
   SONIOX_API_KEY=your_key
   # ...
   ```

3. **运行基础管道自测 (规划中)**:
   ```bash
   python tests/pipeline/pipecat_minimal_test.py
   ```

## 📜 团队协作规范

本项目开发由 OpenCode Agent 深度参与协作。请在开发前务必阅读项目根目录的 [`AGENTS.md`](./AGENTS.md) 以及 `.opencode/skills` 下的相关 SOP。
- **核心红线**：禁止在核心管道使用同步阻塞代码；禁止将未验证的厂商适配器直接合入主干。

## 🤖 Agents & Skills 团队协作指南

在 OpenCode 工作流中，合理的 Agent 角色切换与 Skill 调用是保证项目质量的关键。我们的项目沉淀了多种专门的角色（Agents）和标准作业程序（Skills），供团队成员在不同开发阶段使用。

### 1. 核心 Agent 角色介绍

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

### 2. 现有的 Skills (技能) 矩阵

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

### 3. 规划中的 Skills (Roadmap)

随着项目的推进，我们计划逐步固化以下领域的 SOP：

- 🚧 `tts-survey`: TTS 厂商流式合成接口调研、延迟与自然度对比的标准流程 SOP。
- 🚧 `asr-evaluation`: ASR 专项自动化评测技能，涵盖各语种测试集跑测、WER/CER 计算及抗噪表现量化。
- 🚧 `freeswitch-integration`: FreeSWITCH / SIP 电话网关与 WebSocket 的对接规范、音频重采样(8KHz/16KHz)及信令控制 SOP。
- 🚧 `evaluation-metrics`: 通用评测指标及环境加噪脚本的标准用法（将与 asr-evaluation 等专项评测配合使用）。
- 🚧 `turn-detection-strategy`: 结合 VAD 信号与 LLM 语义的智能断句（Smart Turn Detection）算法调优指南。

### 4. 调用机制与建议

- **隐式调用（默认）**：直接通过自然语言下发指令（如：“去调研 Speechmatics”）。Agent 会根据关键字自动匹配并加载对应的 Skill 规范。
- **显式调用（推荐）**：对于明确的阶段任务，建议在对话开始时显式切换（如：“当前角色：Integration-Developer。请加载 `pipecat-integration` 技能，开始搭建基础管道”）。这能让 Agent 极度聚焦，避免代码跑偏。
