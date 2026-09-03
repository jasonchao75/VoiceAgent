# Spec: Bot Configs（机器人配置实体）

## 1. Product Boundary（产品边界）

本 Change 为受 Basic Auth 保护的单实例 Demo 增加"机器人"配置实体，解决每次会话重复填写 Prompt 与 API Key 的问题。
Bot 是实例内共享的配置模板，不是多租户资源；不引入用户体系。
保存 API Key 是**用户显式勾选的可选项**，默认仍是会话级 BYOK；现有"Key 仅内存、随会话清除"的安全模型对未保存 Key 的路径完全不变。

## 2. Bot Entity and Persistence（实体与持久化）

### Requirement: Bot schema

新增 `src/bots/` 模块。Bot 实体字段：

| 字段 | 约束 | 说明 |
|------|------|------|
| `id` | uuid4 | 主键，创建时生成 |
| `name` | 1–100 字符，允许重名 | 显示名 |
| `asr_provider` | 白名单 | 当前仅 `deepgram_flux` |
| `tts_provider` | 白名单 | 当前仅 `deepgram_flux` |
| `tts_voice` | 必须属于所选 `tts_provider` 的音色 Catalog | 通用 TTS 音色字段；当前仅 Flux 音色（如 `flux-alexis-en`），后续新 TTS 厂商接入自己的音色 Catalog，字段不改名 |
| `llm_provider` | 必须在 LLM Provider Catalog 内 | 含 `custom` |
| `llm_base_url` | HTTPS 校验沿用 `LLMConfig` 规则；非 custom 必须与 Catalog 一致 | |
| `llm_model` | 1–200 字符 | |
| `system_prompt` | 1–30000 字符 | 上限对齐线上系统；存量 `SessionRequest`/`RuntimeConfig` 的 12000 上限本次一并放宽 |
| `opening_script` | 0–2000 字符 | |
| `encrypted_deepgram_key` | nullable | Fernet 密文；为空 = BYOK Bot |
| `encrypted_llm_key` | nullable | 同上 |
| `created_at` / `updated_at` | UTC ISO-8601 | |

- 两个 Key 列必须同时为空或同时非空（ASR 与 TTS 当前共用 Deepgram Key，缺一不可建会话）。
- Bot 数量不设上限；名称不做唯一性约束。
- 配置校验必须复用与 `build_session_config()` 相同的 Catalog 白名单来源（Voice Catalog / LLM Provider Catalog / TTS Registry），不得另建一套规则。

### Requirement: SQLite storage

- 使用 `aiosqlite` 异步访问；DB 文件路径为 `$VOICE_AGENT_DATA_DIR/bots.db`（默认 `./data`，容器内 `/data`）。
- 启动时自动建表（`CREATE TABLE IF NOT EXISTS`），无迁移框架；本 Change 为首个版本，无历史数据。
- 存储访问全部集中在 `src/bots/` 内，API 层与 Pipeline 不直接操作 SQL。
- Bot 的读写发生在 HTTP 会话创建路径上，**不得**进入实时音频 Pipeline 的热路径。

### Scenario: Persistence across restarts

WHEN 用户创建 Bot 后重启容器
THEN Bot 列表与配置完整保留
AND 已保存 Key 的 Bot 在主密钥未变更时可直接发起会话

## 3. Secret Storage（Key 加密存储）

### Requirement: Fernet encryption with server master key

- 主密钥来自环境变量 `VOICE_AGENT_STORAGE_KEY`（Fernet key，32 字节 urlsafe base64）；生成方式写入 `.env.example` 注释，**不得**把真实值提交仓库。
- 保存 Key 时：API 入参用 `SecretStr` 接收 → 复用现有占位符拒绝校验 → Fernet 加密 → 仅存密文。
- 使用 Key 时：仅在 `POST /api/sessions` 处理中于内存解密，封装进现有 `SessionCredentials`，会话结束按现有生命周期清除；解密后的明文不得落盘、不得入日志。
- 任何 API 响应不得包含 Key 明文或密文；列表/详情只返回 `has_saved_keys: bool`。

### Requirement: Graceful degradation without master key

WHEN 部署未配置 `VOICE_AGENT_STORAGE_KEY`
THEN 应用正常启动
AND 创建/更新 Bot 时请求保存 Key 返回 400 与明确错误信息
AND 纯 BYOK Bot 的增删改查与 Quick start 全部可用
AND 若 DB 中已存在加密 Key（如密钥被误删），发起会话返回明确错误而非崩溃

### Scenario: Key never exposed

WHEN 客户端调用 `GET /api/bots` 或 `GET /api/bots/{id}`
THEN 响应包含 `has_saved_keys` 布尔标记
AND 响应体任何位置不出现 Key 明文、密文或前后缀

## 4. API（接口）

### Requirement: Bot management endpoints

| 端点 | 行为 |
|------|------|
| `GET /api/bots` | 列表（按 `updated_at` 倒序），不含 Key |
| `POST /api/bots` | 创建；`save_keys=true` 时必须同时提供两个 Key 且主密钥已配置；201 返回详情 |
| `GET /api/bots/{id}` | 详情；404 于不存在 |
| `PUT /api/bots/{id}` | 全量更新配置；Key 三态：不传字段=保留、传新值=替换、传 `null` 且 `save_keys=false`=清除 |
| `DELETE /api/bots/{id}` | 删除；204 |

- 所有写接口校验失败返回 400/422，错误信息不得回显 Key。
- 接口沿用现有 Basic Auth 保护，无需新增鉴权。

### Requirement: Session creation from bot

`POST /api/sessions` 请求模型扩展：

- 新增可选 `bot_id`；提供 `bot_id` 时**禁止**同时提交内联配置字段（`llm_provider` 等），二者互斥，违反返回 422。
- Bot 已存 Key：请求不得再提交 Key；后端取 Bot 配置 + 内存解密 Key 创建会话。
- Bot 未存 Key：请求必须提交 `deepgram_api_key` 与 `llm_api_key`（仅入内存，沿用现有 SessionRequest 校验），配置取自 Bot。
- 不带 `bot_id` 的现有全字段内联请求（Quick start）行为完全不变。
- Bot 配置在创建会话时快照进 `SessionConfig`；之后修改 Bot 不影响进行中的会话。

### Scenario: Start session from a saved-key bot

WHEN 用户对已存 Key 的 Bot 调用 `POST /api/sessions {"bot_id": "..."}`
THEN 后端解密 Key 并创建会话，返回 session token
AND 会话结束后内存中的 Key 引用被清除
AND 日志中不出现 Key

### Scenario: Start session from a BYOK bot

WHEN 用户对未存 Key 的 Bot 调用 `POST /api/sessions` 但未提交 Key
THEN 返回 422 并提示需要当次提供 Key

## 5. Frontend（前端）

### Requirement: Bot-first configuration panel

- 左侧配置区改为机器人列表：名称、LLM model、voice、"已存 Key"徽章；支持选中、新建、编辑、删除（删除需确认）。
- 编辑器表单：名称、ASR provider（下拉，仅已实现厂商）、TTS provider + TTS voice 下拉（当前仅 Flux 音色，复用现有带特征描述的数据源）、LLM provider/base URL/model（复用现有预设与 custom 逻辑）、System Prompt（上限 30000 字符）、Opening Script。
- 前端所有界面文案（列表、表单、按钮、提示、错误信息）一律使用英文。
- "加密保存 API Key 到服务器"勾选框：勾选时显示两个 Key 遮罩输入框与加密存储说明；编辑已存 Key 的 Bot 时 Key 框留空表示保留原值，并明确提示该语义。
- 新建 Bot 时各字段用 `/api/catalogs` 的 defaults 预填。

### Requirement: Start conversation

- 选中 Bot 后点击 Start：已存 Key 直接 `POST /api/sessions {bot_id}`；未存 Key 弹出当次 Key 填写区（遮罩、不保存、提交后清空前端引用）。
- 保留 Quick start 折叠区：展开后为现有全字段表单（Key 每次手填），行为不回归。
- 更新原"Key 不会保存"的静态文案：区分"保存 Key（加密存储）"与"仅本次会话（BYOK）"两种模式。

### Scenario: Edit a bot without touching keys

WHEN 用户编辑已存 Key 的 Bot，仅修改 System Prompt 并保存
THEN Bot 的 Key 保持原值不变
AND 之后发起的会话仍免填 Key

## 6. Deployment（部署联动）

- `compose.yaml`：新增 named volume（如 `voiceagent-data:/data`）与环境变量 `VOICE_AGENT_DATA_DIR=/data`、`VOICE_AGENT_STORAGE_KEY=${VOICE_AGENT_STORAGE_KEY:-}`；保留 `read_only: true`（可写卷不受影响）。
- `Dockerfile`：以 root 阶段预建 `/data` 并 `chown` 给非 root 运行用户，保证 named volume 首次挂载权限正确。
- `.env.example`：新增 `VOICE_AGENT_DATA_DIR` 与 `VOICE_AGENT_STORAGE_KEY` 注释说明（含生成命令）；`.gitignore` 忽略本地 `data/`。
- 服务器一次性操作（需用户确认）：`.env` 补随机生成的 `VOICE_AGENT_STORAGE_KEY` 后 `docker compose up -d`；**生成后必须备份到密码管理器，丢失则已存 Key 全部无法解密**。
- 现有 CI/CD 流程不变；CD 部署不触碰 named volume 数据。

## 7. Security Invariants（安全不变量）

- API Key 明文只允许出现在：遮罩输入框、HTTPS 请求体、内存解密后的瞬时变量；禁止出现在 URL、浏览器存储、任何响应体、日志、异常详情、git 仓库。
- SQLite 文件中 Key 必须为密文；验收时直接读取 DB 文件核验。
- 沿用现有 `SecretStr`、占位符拒绝、422 不回显输入、`compare_digest` 等既有防护。
- 主密钥不提交仓库、不写入 GitHub Secrets；仅存服务器 `.env` 与用户密码管理器。

## 8. Acceptance Scenarios（验收场景）

1. **Bot CRUD**：创建/编辑/删除 Bot，重启容器后配置保留。
2. **Saved-key session**：保存 Key 的 Bot 一键开始通话，完成至少三轮对话；DB 文件中 Key 为密文。
3. **BYOK bot session**：未存 Key 的 Bot 当次填 Key 开始通话；会话结束后内存清除、Key 不落盘。
4. **Quick start**：不建 Bot，全字段内联发起一次性会话，现有行为不回归。
5. **Key 三态**：编辑 Bot 时保留/替换/清除 Key 均符合预期；清除后再次发起会话要求当次填 Key。
6. **Degraded mode**：移除 `VOICE_AGENT_STORAGE_KEY` 重启后，应用正常启动，保存 Key 返回明确错误，BYOK 路径正常。
7. **Catalog 校验**：提交非法 voice/provider/base URL 被 400/422 拒绝。
8. **No leak**：检查全部 API 响应、服务端日志、DB 文件、仓库，无 Key 明文。
