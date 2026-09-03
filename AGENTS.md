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
│   ├── bots/             # 机器人配置实体：SQLite 持久化 + Fernet 加密 Key 存储
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
│   ├── engineering/      # 工程实践、自动化质检、部署、Hooks、测试、Agent 工作流等详细文档
│   ├── changes/archive/  # OpenSpec 引入前的历史 Change（只读）
│   ├── prd/              # PRD 与产品原型文件
│   ├── references/
│   │   ├── general/      # 通用参考资料、竞品分析
│   │   └── vendor/       # 厂商 API 速查手册（Vendor-Researcher）
│   └── reports/
│       ├── vendor/       # 调研报告、选型决策矩阵（Vendor-Researcher）
│       └── evaluation/   # 评测报告（Evaluation-Engineer）
├── openspec/
│   ├── specs/            # 当前已生效行为的主规格库（Source of Truth）
│   └── changes/          # 新 Change、Delta Specs 与归档记录
├── AGENTS.md             # 本项目级协作协议（本文件）
├── demos/                # 另一个子项目，一些临时演示demo和对应代码，推git时候也要ignore
└── .gitignore            # 敏感配置与生成文件排除
```

### 核心文档分工说明

为了保持项目结构的清晰，本项目的核心文档按以下职责进行严格划分：
- **`README.md`**：项目首页与团队导航。
- **`AGENTS.md`**：AI Agent 执行协议、红线和协作规则（本文件）。
- **`docs/engineering/`**：工程实践与操作手册的承接点。涵盖 CI/CD、Hooks、测试、部署、Agent 工作流等详细文档（注：部分如 CI/CD、部署相关文档目前为规划中，后续将逐步补充）。

**工程文档原则**：可复用的工程规范和操作流程应沉淀到 `docs/engineering/`，`README.md` 仅保留概览与导航。
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
- **禁止硬编码任何厂商 API Key 或 Token**：统一使用 `.env` 环境变量；`.env` 与 `configs/` 下的敏感配置文件必须加入 `.gitignore`。用户在机器人维度**显式选择保存**的 Key 是唯一例外：必须经 Fernet 加密后落 SQLite，主密钥仅存于 `VOICE_AGENT_STORAGE_KEY` 环境变量，任何 API 响应与日志不得出现明文。
- **禁止未经自动化评测的 ASR/TTS 适配器直接合入主干**：必须通过 WER、延迟、抗噪基准测试后方可上线。
- **禁止忽略音频采样率与格式转换**：所有 ASR/TTS 适配器必须显式校验并正确处理音频采样率与格式。当前电话场景为 **8KHz / 16bit / 单声道 PCM**，需确保与目标厂商要求一致，必要时进行重采样。
- **禁止交付无自测用例的 ASR/TTS 适配器及 pipeline 模块**：每个适配器和核心 pipeline 模块必须包含可独立运行的测试脚本，验证连通性与基本能力。
- **禁止随意删减厂商官方原始文档（防幻觉红线）**：在整理厂商 API 规范（如 ASR/TTS 调研）时，必须采用“结构化摘要在顶部，原始 YAML/Markdown 源码兜底在底部”的双轨制做法。严禁为了精简篇幅而删除官方原始文档内容。原始规范是后续解决参数疑问或拦截大模型幻觉的终极事实锚点。

---

> 本项目遵循全局 AGENTS.md 的协作原则：Agent 负责技术实现，用户负责需求定义与产品验收。代码变更通过 git 管理，关键里程碑由 Agent 协助提交并推送到远程仓库。

---

## 6.1 Vendor 测试脚本与评测产物规范

- `scripts/vendor/<vendor>/` 只能保留单条测试 Python 脚本、批量测试 Python 脚本和 `logs/` 目录；禁止存放 CSV、Excel、缓存、独立评测算法或数据分析辅助脚本。
- 单条与批量日志统一保存在对应 vendor 的 `logs/` 中，历史日志全部保留；日志不得包含 API Key、Token 或其他凭证。
- 批量测试结果统一保存到 `benchmarks/<library>/test-results/<vendor>/`，每个自然日只保留一组 `<YYYYMMDD>.xlsx`、`<YYYYMMDD>.csv`（逐条明细）与 `<YYYYMMDD>_summary.csv`（汇总指标）。同日后续运行必须按 `benchmark_id` 增量合并：新 ID 追加，重复 ID 用最新结果覆盖，然后原子覆盖当日三份文件，不得创建新的结果文件；跨日创建新的一组。XLSX 的 `details` 工作表和明细 CSV 固定且仅包含 7 列：`benchmark_id`、`audio_path`、`annotated_text`、`transcript`、`normalized_annotated_text`、`normalized_transcript`、`wer`；XLSX 可继续保留 `summary`、`run_metadata` 以及用于可靠合并的隐藏状态工作表。禁止在 vendor 脚本目录生成结果表格。
- 音频与 Benchmark ID 的对应关系必须读取 benchmark 清单中的音频路径字段，不得假设音频文件名等于 Benchmark ID。
- 计算 ASR 字准率前，必须先读取目标 library 目录内已有的计算脚本和说明。`library_ar` 必须直接使用 `benchmarks/library_ar/asr_char_accuracy.py` 及同目录说明，禁止修改其逻辑或在 vendor 目录复制另一套算法。
- 如果目标 library 缺少字准率脚本或计算口径，必须先询问用户；确认后在该 library 目录补写说明和可运行脚本并完成自检，禁止静默套用其他语种或语料库规则。
- `scripts/vendor/` 中的历史 CSV 不保留、不迁移；确认不再需要后直接删除。benchmark 原始清单不属于此规则，禁止误删。

---

## 7. OpenSpec 与 Change 执行约束（Agent 必读）

为了让 Agent 同时掌握“系统当前行为”和“本次准备改变的行为”，新需求采用 OpenSpec 目录与 Delta Spec 机制。OpenCode 必须遵守以下协议：

- **先读主规格**：`openspec/specs/<capability>/spec.md` 是已经验收并生效行为的 Source of Truth。修改系统行为前，Agent 必须先读取相关主规格；主规格与代码或测试冲突时不得自行覆盖，必须查明原因并向用户说明。
- **主动触发 Change**：开发核心功能或修改可观察系统行为时，必须先在 `openspec/changes/{change-name}/` 创建 `proposal.md`、capability 级 Delta Specs、必要的 `design.md` 与 `tasks.md`。
- **分离 WHAT 与 HOW**：Delta Spec 只用 `ADDED`、`MODIFIED`、`REMOVED`、`RENAMED` 表达行为契约及验收场景；模块选择、数据结构、迁移和实现取舍写入 `design.md`。
- **禁止无凭据编码**：用户确认 Change 的范围、行为规格、设计和任务之前，Agent 绝对禁止开始编写核心逻辑代码。
- **验证后合并**：实现完成后必须对照 Delta Specs 验证。用户验收通过后，先将 Delta 合并到主规格，再把 Change 移至 `openspec/changes/archive/{YYYY-MM-DD-change-name}/`；主规格必须反映最终实现，而非原始计划。
- **旧 Change 只读**：OpenSpec 引入前的 Change 已归档在 `docs/changes/archive/`，仅用于历史追溯；所有新 Change 使用 `openspec/changes/`。
- **免长流程特权**：普通文档整理、厂商报告、Skill 修补、单点参数和一句话可验收的小 bug 不强制开启 Change；若它们改变主规格中的行为，仍必须更新相应 Spec。
- **经验提炼与闭环**：归档后如产生长期可复用的工程经验，应主动建议提炼到 `.opencode/skills/`，不得把一次性需求细节写入 Skill。

---

## 任务完成前检查
涉及代码、配置、部署、CI/CD、测试脚本或核心文档的改动完成后，Agent 必须运行与本次改动相关的本地检查；如已推送远端，应查看 GitHub Actions 结果并修复失败项。
测试过程中如产生临时文件、日志、缓存、测试录音或测试数据库，Agent 必须汇报路径；除非这些文件需要作为证据保留，否则不得提交，并应清理无用脏数据。

## Git 推送方式约定

推送前必须先确认当前仓库 remote：

```bash
git remote -v
```

当推送包含 `.github/workflows/` 的改动时，如果 remote 是 HTTPS，且 push 报错：

```text
refusing to allow a Personal Access Token to create or update workflow ... without `workflow` scope
```

说明当前 HTTPS Personal Access Token 缺少 `workflow` 权限。此时应改用 SSH remote：

```bash
git remote set-url origin git@github.com:jasonchao75/VoiceAgent.git
ssh -T git@github.com
git push origin main
```

原因：HTTPS 推送依赖 Personal Access Token；SSH 推送使用本机已授权的 GitHub SSH Key，可正常推送 workflow 文件。
推送前仍必须运行相关本地检查，并确认没有提交 `.env`、私钥、API Key、日志、录音、缓存等敏感或临时文件。
