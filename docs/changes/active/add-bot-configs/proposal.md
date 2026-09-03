# add-bot-configs

## Why（为什么要做）

当前公网 Demo 每次发起会话都要重新填写 System Prompt、Opening Script、LLM 参数和两类 BYOK API Key，重复成本高。
入口 Basic Auth 已改为固定密码（见 `chore: relax basic auth password minimum to 8 characters`），"每次全手填"成为主要摩擦点。
需要一个"机器人（Bot）"配置实体：把 ASR/TTS/LLM 选择和 Prompt 保存在机器人里；API Key 可由用户选择加密保存在机器人维度（保存后免填），或不保存保持每次会话 BYOK。
同时，某些机器人后续会有更多定制化配置（如厂商专属参数、业务能力开关等），需要一个可持续演进的持久化载体；Bot 实体与其存储层正是为此打底，本次先落地最小配置面。

## What（这次要做什么）

- 新增 Bot 实体与持久化存储：SQLite（aiosqlite 异步访问），DB 文件落在 `VOICE_AGENT_DATA_DIR`（容器内 `/data`，Docker named volume 挂载）。
- Bot 配置面：名称、ASR provider、TTS provider、TTS voice（通用音色字段，当前仅 Flux 音色）、LLM provider/base URL/model、System Prompt（上限放宽至 30000 字符）、Opening Script；配置校验复用现有 Catalog 白名单。前端界面文案一律使用英文。
- Bot 维度可选保存 API Key：勾选保存时，Deepgram/LLM Key 经 Fernet（AES）加密后落库；主密钥来自新环境变量 `VOICE_AGENT_STORAGE_KEY`；不勾选则 Key 列为空，保持每次会话 BYOK。
- 新增 Bot 管理 API：`GET/POST/PUT/DELETE /api/bots`；任何响应不得包含 Key 明文，只返回 `has_saved_keys` 布尔标记；更新接口支持 Key 的保留/替换/清除。
- 扩展 `POST /api/sessions`：支持以 `bot_id` 发起会话（已存 Key 的 Bot 免填 Key；未存 Key 的 Bot 当次请求临时带 Key，仅入内存）；不带 `bot_id` 的现有全字段内联模式保持兼容，作为 Quick start 通道。
- 前端同页改造：左侧配置区改为"机器人列表 + 新建/编辑/删除"，编辑表单含"加密保存 API Key"勾选项；选中 Bot 直接开始通话（BYOK Bot 当次补填 Key）；保留 Quick start 折叠入口（现有全字段表单）。
- 部署联动：`compose.yaml` 增加 named volume 与新环境变量、`Dockerfile` 预建 `/data`、`.env.example`/`.gitignore` 更新；服务器 `.env` 一次性补 `VOICE_AGENT_STORAGE_KEY`。
- 未配置 `VOICE_AGENT_STORAGE_KEY` 时：纯 BYOK Bot 与 Quick start 全部可用，仅"保存 Key"功能明确报错关闭（优雅降级，不影响启动）。

## Delivery Strategy（交付策略）

1. **本地阶段**：完成存储层、API、前端与自动化测试，本地跑通 Bot 全流程人工验收。
2. **公网阶段**：合并 `main` 经 CI/CD 自动部署；部署前服务器 `.env` 一次性补 `VOICE_AGENT_STORAGE_KEY`（随机生成，不写入仓库）。
3. 服务器 `.env` 修改与真实 Key 保存动作，需在执行前取得用户确认。

## Out of Scope（这次明确不做什么）

- 不做用户体系、注册登录、多租户；Bot 在 Basic Auth 保护后的实例内全员共享。
- 不接入新的 ASR/TTS/LLM 厂商；Bot 的 provider 字段预留，下拉只列当前已实现厂商。
- 不做主密钥轮换工具、Key 使用审计和配额管理（文档中列为后续项）。
- 不改动 Basic Auth 机制本身；不改动现有 Pipeline、打断与延迟探针逻辑。
- 不接 FreeSWITCH / 电话线路。

## Success Criteria（成功标准）

- 用户可创建、编辑、删除 Bot；Bot 配置在重启容器后仍然保留（volume 持久化）。
- 勾选保存 Key 的 Bot：创建会话无需再填 Key，直接开始通话；库文件中 Key 为密文。
- 未保存 Key 的 Bot：发起会话时当次填写 Key，会话结束即清除，行为与现有 BYOK 一致。
- Quick start 通道不建 Bot 也可直接发起一次性会话，现有行为不回归。
- 任何 API 响应、日志、异常详情中均不出现 API Key 明文；`GET /api/bots*` 只暴露 `has_saved_keys`。
- 未配置 `VOICE_AGENT_STORAGE_KEY` 的部署可正常启动，保存 Key 的请求返回明确错误。
- 本地与公网自动化测试全绿；现有 21 个测试不回归。

## Relevant References（相关参考）

- `AGENTS.md`（红线与 Change 机制）
- `docs/changes/active/add-english-flux-voice-agent/spec.md`（BYOK 生命周期与白名单校验的既有约定）
- `src/session.py`（SessionRequest / SessionStore / build_session_config）
- `src/config.py`（Catalog 模型与白名单来源）
- `docs/engineering/english-flux-voice-agent.md`
