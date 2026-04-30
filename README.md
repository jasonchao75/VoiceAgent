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

## 📜 协作规范

本项目开发由 OpenCode Agent 深度参与协作。请在开发前务必阅读项目根目录的 [`AGENTS.md`](./AGENTS.md) 以及 `.opencode/skills` 下的相关 SOP。
- **核心红线**：禁止在核心管道使用同步阻塞代码；禁止将未验证的厂商适配器直接合入主干。

## 🤖 Agents & Skills 使用规范

在 OpenCode 工作流中，合理的 Agent 角色切换与 Skill 调用是保证项目质量的关键。

### 1. Agent 的隐式与显式调用

- **隐式调用（默认行为）**：在开始新任务时，您可以直接通过自然语言下发指令（如：“去调研 Speechmatics 的流式接口”）。OpenCode 的主 Agent 会自动判断任务性质并执行。
- **显式调用（角色切换，推荐）**：对于明确的阶段性任务（例如调研结束进入开发阶段），建议在对话开始时通过**身份设定**进行显式切换（如：“当前角色：Integration-Developer。请开始搭建 Pipecat 基础管道”）。这种方式能让 Agent 更聚焦于当前阶段的核心职责，避免在写代码时被调研思维干扰。

### 2. Skills (技能) 的调用机制

Skills 是项目中沉淀的标准作业程序（SOP）、架构规范和防坑指南（位于 `.opencode/skills/` 目录下）。

- **隐式触发**：OpenCode 主 Agent 在理解您的意图时，会根据关键字（如“对接 Pipecat”、“调研 ASR”）自动从后台匹配并加载相应的 Skill 规范。
- **显式触发**：您可以在对话中直接指令 Agent：“请查阅并加载 `pipecat-integration` 技能，然后检查当前代码是否符合规范”。
- **调用时机建议**：
  - **新模块启动时**：主动加载开发规范（如 `pipecat-integration`）以确保架构不跑偏。
  - **对接外部厂商时**：加载依赖的 Vendor 技能（如 `vendor-speechmatics`, `vendor-azure`），获取特殊的鉴权陷阱和文档兜底。
  - **长对话卡顿或阶段性结束时**：利用 `session-handoff` 技能（隐式或显式），生成结构化的上下文快照并开启新对话，防止长对话造成的记忆遗忘和幻觉。
