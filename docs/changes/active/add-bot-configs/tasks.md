# Tasks: Bot Configs（机器人配置实体）

## 1. Storage Layer（存储层）

- [x] 新增依赖 `aiosqlite` 与 `cryptography`，锁定版本并更新依赖清单
- [x] 新建 `src/bots/` 模块：Bot pydantic 模型（请求/响应/内部实体）
- [x] 实现 SQLite 存储层（建表、CRUD、`$VOICE_AGENT_DATA_DIR/bots.db`）
- [x] 实现 Fernet 加解密封装：主密钥加载、加密保存、内存解密、未配置/密钥错误的明确异常
- [x] Bot 配置校验复用 Catalog 白名单（voice/provider/base URL），与 `build_session_config()` 同源

## 2. API

- [x] 实现 `GET /api/bots`、`POST /api/bots`、`GET /api/bots/{id}`、`PUT /api/bots/{id}`、`DELETE /api/bots/{id}`
- [x] 所有响应模型只含 `has_saved_keys`，禁止输出 Key 明文/密文
- [x] `PUT` 支持 Key 保留/替换/清除三态
- [x] 扩展 `POST /api/sessions`：可选 `bot_id`，与内联配置互斥；已存 Key Bot 免填、BYOK Bot 当次必填
- [x] 放宽 `system_prompt` 上限至 30000（`SessionRequest` 与 `RuntimeConfig` 一并调整）
- [x] 会话创建时把 Bot 配置快照进 `SessionConfig`；进行中的会话不受后续 Bot 修改影响
- [x] 未配置 `VOICE_AGENT_STORAGE_KEY` 时保存 Key 返回 400 明确错误；DB 已有密文但密钥缺失/错误时发起会话返回明确错误

## 3. Frontend

- [x] 左侧配置区改为机器人列表（名称、model、voice、已存 Key 徽章）+ 选中/新建/编辑/删除（删除需确认）
- [x] Bot 编辑器：名称、ASR/TTS provider 下拉（仅已实现）、TTS voice 下拉（当前仅 Flux 音色）、LLM 三件套、Prompt（上限 30000）、Opening Script
- [x] 前端全部界面文案使用英文
- [x] "加密保存 API Key"勾选框与 Key 遮罩输入；编辑时留空=保留原值的语义提示
- [x] 新建 Bot 用 catalogs defaults 预填
- [x] Start 流程：已存 Key 直接开打；BYOK Bot 当次补填 Key（不保存、提交后清空）
- [x] 保留 Quick start 折叠区（现有全字段表单不回归）
- [x] 更新 Key 保存相关静态文案（加密存储 vs 仅本次会话）

## 4. Deployment

- [x] `compose.yaml`：named volume `voiceagent-data:/data` + `VOICE_AGENT_DATA_DIR` / `VOICE_AGENT_STORAGE_KEY` 环境变量
- [x] `Dockerfile`：预建 `/data` 并 chown 非 root 运行用户
- [x] `.env.example` 新增两项说明（含主密钥生成命令）；`.gitignore` 忽略 `data/`
- [x] 确认 CI（镜像构建、测试）无需改动即可通过

## 5. Automated Verification

- [x] 加解密往返、错误主密钥、未配置主密钥的单元测试
- [x] Bot CRUD + Catalog 白名单校验测试（非法 voice/provider/base URL 拒绝）
- [x] `PUT` Key 三态测试；两 Key 列同空/同非空约束测试
- [x] 会话创建三路测试：已存 Key Bot / BYOK Bot / Quick start 兼容
- [x] 响应无 Key 明文/密文测试（列表、详情、错误响应）
- [x] 降级模式测试：无 STORAGE_KEY 启动正常、保存 Key 报错、BYOK 正常
- [x] 现有测试全绿；运行 format、lint、typecheck、unit test、前端 build
- [x] 扫描仓库与构建产物，确认无密钥与临时文件

## 6. Local Acceptance

- [x] 本地完成验收场景 1–8（含直接读 DB 文件核验密文、降级模式）
- [x] 汇报测试日志与临时产物路径并清理

## 7. Public Deployment

- [ ] 用户确认后：服务器 `.env` 补随机 `VOICE_AGENT_STORAGE_KEY`，`docker compose up -d`
- [ ] 提醒用户把主密钥备份到密码管理器
- [ ] 公网完成 Bot 全流程人工验收（建 Bot 存 Key → 免填开打 → 重启保留）

## 8. Closeout

- [x] 更新 `README.md`（BYOK 表述改为"可选加密保存"）与 `docs/engineering/english-flux-voice-agent.md`（新使用流程）
- [x] 更新 `AGENTS.md` 项目结构（新增 `src/bots/`）与红线表述（可选加密存储的例外说明）
- [ ] 对照 `spec.md` 完成最终检查并记录偏差
- [ ] 用户验收通过后归档到 `docs/changes/archive/`
- [ ] 评估是否把"Fernet 密钥管理 / SQLite 持久化落地"经验提炼到 `.opencode/skills/`
