# AGENTS.md — VoiceAgent 项目协作协议

> 本项目级协议覆盖 VoiceAgent（ASR + LLM + TTS 三段式语音机器人）的开发与迭代。与全局 AGENTS.md 冲突时，以本文件为准。

---

## 1. 项目概述

基于 ASR + LLM + TTS 三段式架构，搭建支持多语种、多 ASR 厂商的实时语音机器人。核心目标：**解决抗噪差、无法自动化评测、端到端延迟高、机器人抢话严重**四大痛点。通过统一 ASR 适配层、VAD/Turn-Detection 策略优化、跨模块时序重叠、自动化评测框架，实现低延迟、高自然度的语音对话体验。当前阶段通过前端 Web 页面进行功能验证与测试，电话接入能力作为后续扩展预留。

---

## 2. 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.11+ | asyncio TaskGroup 对实时流式处理友好 |
| 通信框架 | FastAPI + WebSocket | 实时音频流双向通信 |
| VAD | 优先使用厂商内置 VAD，必要时以 WebRTC VAD 补充 | 各厂商效果不统一，需灵活补充 |
| ASR 适配 | 统一抽象接口 + 各厂商适配器 | 覆盖 Speechmatics/Deepgram/Azure/Tencent/Soniox |
| LLM | 三方资源 Streaming API | 流式输出 |
| TTS 适配 | 统一抽象接口 + ElevenLabs / Minimax | 语音合成 |
| 音频处理 | librosa / soundfile / numpy | 重采样、格式转换、评测加噪 |
| 评测 | jiwer (WER/CER) + 自定义延迟探针 | 自动化量化抗噪、延迟、流畅度 |
| 部署 | Docker + docker-compose | 多服务本地联调与一致性交付 |
| 电话接入（未来） | FreeSWITCH | 后续可扩展支持电话呼叫接入，当前阶段仅通过 Web 页面测试 |

---

## 3. 编码规范

- 遵循 **PEP 8**，命名使用 **snake_case**，类名使用 **PascalCase**。
- 函数与类必须包含 **Google 风格 docstring**，说明参数、返回值、可能抛出的异常。
- **禁止裸 print()**，统一使用标准库 `logging`。
- 所有涉及外部服务调用的函数，必须显式声明超时参数（如 `timeout: float = 10.0`）。
- 代码注释必须为英文，侧重解释 Why。

---

## 4. 项目结构

```
voice-agent/
├── .opencode/
│   ├── agents/           # Agent 角色定义与工作记录
│   └── skills/           # 可复用的 Agent 技能脚本
├── src/
│   ├── asr/              # ASR 统一抽象层 + 各厂商适配器
│   ├── llm/              # LLM 接口 + Streaming 衔接
│   ├── tts/              # TTS 统一抽象层 + ElevenLabs / Minimax 适配器
│   ├── pipeline/         # 三段式编排核心（ASR → LLM → TTS）
│   └── evaluation/       # 自动化评测框架（Evaluation-Engineer）
├── frontend/             # 前端界面（Web UI / 管理后台）
├── configs/
│   ├── vendor/           # 厂商接口验证配置（Vendor-Researcher）
│   └── runtime/          # 生产运行时配置（Integration-Developer）
├── tests/                # 单元测试 + 集成测试 + 模块自测（Integration-Developer）
├── benchmarks/           # 评测数据集与结果
├── scripts/
│   ├── vendor/           # 厂商接口验证脚本（Vendor-Researcher）
│   └── evaluation/       # 评测工具脚本（Evaluation-Engineer）
├── docs/
│   ├── prd/              # PRD 与产品原型文件
│   ├── references/
│   │   ├── general/      # 通用参考资料、竞品分析
│   │   └── vendor/       # 厂商 API 速查手册（Vendor-Researcher）
│   └── reports/
│       ├── vendor/       # 调研报告、选型决策矩阵（Vendor-Researcher）
│       └── evaluation/   # 评测报告（Evaluation-Engineer）
├── AGENTS.md             # 本项目级协作协议（本文件）
└── .gitignore            # 敏感配置与生成文件排除
```

---

## 5. Agent 角色概览

| 角色 | 核心职责 | 解决痛点 |
|------|---------|---------|
| **Vendor-Researcher** | 调研 ASR/TTS/LLM 厂商接口，验证可用性，输出对接设计与选型矩阵 | 抗噪差、多语种覆盖、LLM 选型 |
| **Integration-Developer** | 实现 ASR/TTS/LLM 适配器、前端、pipeline、对话状态机，交付全部代码与自测 | 端到端延迟高、抢话严重、代码落地 |
| **Evaluation-Engineer** | 搭建自动化评测框架，量化抗噪/延迟/流畅度，输出独立评测报告 | 无法自动化评测 |

> 分工边界：Researcher 只输出规范和调研报告；Developer 负责所有编码、前端与自测；Evaluation-Engineer 负责独立评测。

---

## 6. 红线（绝对禁止）

- **禁止在核心 pipeline 中使用同步阻塞 I/O**：所有音频流、网络请求必须使用 asyncio 异步处理。
- **禁止硬编码任何厂商 API Key 或 Token**：统一使用 `.env` 环境变量；`.env` 与 `configs/` 下的敏感配置文件必须加入 `.gitignore`。
- **禁止未经自动化评测的 ASR/TTS 适配器直接合入主干**：必须通过 WER、延迟、抗噪基准测试后方可上线。
- **禁止忽略音频采样率与格式转换**：所有 ASR/TTS 适配器必须显式校验并正确处理音频采样率与格式。当前电话场景为 **8KHz / 16bit / 单声道 PCM**，需确保与目标厂商要求一致，必要时进行重采样。
- **禁止交付无自测用例的 ASR/TTS 适配器及 pipeline 模块**：每个适配器和核心 pipeline 模块必须包含可独立运行的测试脚本，验证连通性与基本能力。
- **禁止随意删减厂商官方原始文档（防幻觉红线）**：在整理厂商 API 规范（如 ASR/TTS 调研）时，必须采用“结构化摘要在顶部，原始 YAML/Markdown 源码兜底在底部”的双轨制做法。严禁为了精简篇幅而删除官方原始文档内容。原始规范是后续解决参数疑问或拦截大模型幻觉的终极事实锚点。

---

> 本项目遵循全局 AGENTS.md 的协作原则：Agent 负责技术实现，用户负责需求定义与产品验收。代码变更通过 git 管理，关键里程碑由 Agent 协助提交并推送到远程仓库。
