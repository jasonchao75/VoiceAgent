# CI/CD 与自动化质检

## 简单理解

- **CI (持续集成)** = 自动化质检（在你提交代码时自动帮你检查有没有写错）。
- **CD (持续部署)** = 自动化上线（在你通过所有检查后，自动把代码发布到体验环境或生产环境）。
- **三层防线的区别**:
  - **本地 Hook** (当前已有): OpenCode 修改文件后自动运行的轻量守卫，不离开你的电脑，比如检查你刚写完的 JSON 或 Python 文件。
  - **GitHub CI**: 当代码 push 到 GitHub 或提起 PR 时，自动运行全量非付费检查，确保不破坏主干。
  - **CD**: `main` 的 CI 全绿后，自动把同一个已验证 commit 部署到 DigitalOcean。

## 当前状态

- ✅ **已有**: OpenCode 内部运行的本地轻量 Hook（见 `docs/engineering/hooks.md`）。
- ✅ **已有**: README.md 中已开通本文档的入口。
- ✅ **已有**: GitHub CI 在 push/PR 时运行安全检查、format、lint、typecheck、unit test、前端 build 和生产镜像 build。
- ✅ **已有**: English Flux Voice Agent 自动 CD workflow；只接受主仓库 `main` push 的成功 CI，包含部署串行化、commit 校验、健康检查和失败回滚。
- ⏳ **尚未实现**: 真实厂商 API 测试目前主要依赖在本地手动执行脚本进行（例如手动跑 `scripts/vendor/xxx_test.py`），尚未被自动化接管。
- ⏳ **待一次性配置**: `platform.voiceagentdemo.org` DNS/HTTPS、GitHub Environment Secrets 和服务器 deploy 身份；完成后自动 CD 才会实际运行。

部署总开关是仓库变量 `PLATFORM_DEPLOY_ENABLED`。首次初始化完成前保持非 `true`；完成 Secrets、服务器和 HTTPS 验证后设置为 `true`，后续 `main` 的健康提交即可自动发布。

DigitalOcean 上的 `deploy` 用户不加入 Docker group。GitHub Actions 只能通过 sudoers 执行 root 管理的 `/usr/local/sbin/deploy-voiceagent-platform`，commit SHA 通过标准输入传递；脚本会再次验证该提交属于远端 `main` 后才调用 Docker。

## 核心仓库与 Demos 仓库的 CI/CD 边界

**重要说明**: `VoiceAgent` 主仓库与 `demos/` 目录下的演示项目（如 `demos/realtimeasr-en-arabic`）是相互独立的 Git 仓库，它们的自动化策略完全不同。
- **VoiceAgent 主仓库**: 负责核心组件、适配器、流水线质检，以及本仓库 English Flux Voice Agent 的 `platform.voiceagentdemo.org` 部署。
- **Demos 独立仓库**: 负责自身业务逻辑的 Smoke Test、运行验证以及 Demo 的自动化部署（CD）。

## 自动运行与手动运行的边界

- **本地 Hook**: 会在 OpenCode **修改文件后自动运行**，无感知防御。
- **基础 GitHub CI** (当前已有): 每次 **push 或 Pull Request 时自动运行**，作为团队合码前的刚性防线。
- **自动 CD**: 仅主仓库 `main` push 的 CI 全绿后运行；PR、fork 和失败 CI 不部署。workflow 同时保留手动重跑入口。
- **真实厂商 API 测试**: 由于调用外部 API 会产生计费且耗时较长，因此不进入每次 push 的 CI；继续由用户以 BYOK 方式人工验收。

## 基础 CI 计划 (阶段 1)

未来基础 CI 将在每次 push / PR 时自动运行，主要针对 **VoiceAgent 主仓库**（排除 `demos/` 目录）检查以下几项**不依赖真实厂商 API** 的内容：
1. **Python 语法与规范**: 执行 `ruff` 或 `flake8` 等基础语法检查。
2. **JSON 配置验证**: 检查所有 `configs/vendor/*.json` 的格式与基础字段是否完备。
3. **敏感信息防泄漏**: 全量扫描代码库，防止将 API Key 误 push 到云端。
4. **基础单元测试**: 运行针对核心类、工具函数的快速单元测试。

## 中期核心验证 (阶段 2 & 4)

在高级自动化流水线建立之前，我们依赖以下更轻量的方式保障核心链路：
1. **Speechmatics demo 手动验证 (阶段 2)**: **[独立在 demos/realtimeasr-en-arabic 仓库中实现]** 优先在本地或目标服务器上手动运行 `Smoke Test`，确保真实 API 的连通性与核心音频链路可用。
2. **pytest 与 mock pipeline (阶段 4)**: **[VoiceAgent 主仓库]** 引入 `pytest` 编写无需真实网络的单元与集成测试，低成本验证核心状态机流转。

## CD 计划 (阶段 3, 6, 7)

当前核心目标是快速提供稳定的内部体验环境，同时不把付费厂商测试放入无人值守流程。

1. **English Flux Voice Agent CD (阶段 3, 已实现 workflow)**:
   - **目标**: 将本仓库已经通过 CI 的 `main` commit 自动更新到 `platform.voiceagentdemo.org`，而不是做完整的生产级高可用发布。
   - **前置条件**: 
     - demo 已经在本地或服务器手动跑通过至少一次。
     - 目标服务器信息明确。
     - 启动 / 重启命令明确。
     - 敏感的 API Key 绝对不写入代码仓库，已配置在服务器环境变量或 GitHub Secrets 中。
     - 至少通过了基础 CI 或最小的 Smoke Check (冒烟测试)。
2. **Docker 部署 (阶段 6)**: 自动将 Pipeline、Frontend 打包成标准化的 Docker 镜像发布。
3. **环境隔离 (阶段 7)**: 后续逐渐分离 Staging (预发环境，供内部体验评测) 和 Production (正式生产环境)。

## 高级 CI 计划 (阶段 5)

在基础架构和 Demo 跑通，并且完善了基础 mock 测试后，规划在特定环节（如发版或手动触发）运行耗时更长、更复杂的质量体系测试（后续阶段）：
1. **厂商 API 连通性测试**
2. **ASR 性能评测 (WER/CER)**
3. **端到端延迟监测**
4. **智能打断 (Barge-in) 及 Turn Detection**
5. **复杂场景压测 (多语种/环境噪声)**

## API Key 管理规范

为了保证系统的安全性，本项目对敏感信息有严格要求：
- **绝对禁止**: API Key 绝不能直接写死在代码或配置文件中并推送到 Git。
- **本地开发**: 使用 `.env` 文件存储本地测试所需的 Key（`.env` 已加入 `.gitignore`）。
- **GitHub 自动化**: CI 测试所需要的 Key 必须通过 **GitHub Secrets** 配置并在运行时注入环境。
- **服务器部署**: 生产环境统一从环境变量中读取凭证。

## 后续演进路线图

以下是推荐的落地顺序：
1. **[当前已有] 阶段 1：基础 CI** - 搭建语法、格式、防泄漏的门禁。
2. **[当前] 阶段 2：Speechmatics demo 手动验证 / Smoke Test** - 确保各链路初步跑通。
3. **[当前已实现 workflow，待环境初始化] 阶段 3：轻量 Demo CD** - CI 全绿后自动部署并做健康检查/失败回滚。
4. **[当前已有] 阶段 4：pytest 与 mock pipeline** - 不调用付费 API 验证核心机制。
5. **[后续阶段] 阶段 5：高级 CI (WER/CER/延迟)** - 建设抗噪、延迟等量化指标的高级评测流水线。
6. **[后续阶段] 阶段 6：Docker 部署** - 完善容器化打包镜像的规范。
7. **[后续阶段] 阶段 7：staging / production 分环境** - 规划完善的多环境发布体系。
