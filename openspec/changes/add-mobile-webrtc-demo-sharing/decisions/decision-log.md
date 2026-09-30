# Decision Log

## Status

- Recorded decisions: 15
- Last reviewed: 2026-09-30

## Decisions

### D-001：首版采用手机 Web 页面而非 App 或 SIP

- Status: Confirmed
- Date: 2026-09-29
- Source question: Product discovery
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，本 Change 前置对话
- Confirmation quote: “不用验证未来电话接入架构。只是想做demo演示”
- Decision: 首版提供移动浏览器主动通话，不实现 SIP、FreeSWITCH 或原生 App。
- Reason: 降低演示门槛和资质/线路依赖。
- Consequences: 使用 WebRTC；无电话号码、后台来电或锁屏接听。
- Updated artifacts: PRD、proposal、mobile-web-call Delta Spec、原型。
- Verification: 手机浏览器可从链接进入并完成主动通话。

### D-002：单个 Published Bot 对应二维码与 Web Link

- Status: Confirmed
- Date: 2026-09-29
- Source question: PRD confirmation
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，PRD 确认消息
- Confirmation quote: “prd文档已确认。”
- Decision: 每个 Published Bot 首版只有一个 Demo Link；二维码编码同一链接，不增加 PIN。
- Reason: 演示路径最短，管理员仍可按 Bot 控制入口。
- Consequences: 链接需稳定持久化且不得携带 Provider 凭证。
- Updated artifacts: PRD、bot-config/voice-session Delta Specs、Share 原型。
- Verification: QR 与 Web Link 打开同一 Bot，均不要求访客登录。

### D-003：保留现有录音、历史和并发策略

- Status: Confirmed
- Date: 2026-09-29
- Source question: PRD confirmation
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，PRD 确认消息
- Confirmation quote: “prd文档已确认。”
- Decision: 用户录音保留 7 天，文本/指标保留 30 天，首版最多 3 路并发；移动来源为 `mobile_web_call`。
- Reason: 复用现有治理与容量边界。
- Consequences: 移动页面必须在开始前披露保留期；历史可按来源区分。
- Updated artifacts: PRD、call-history/voice-session Delta Specs。
- Verification: 历史记录和清理测试覆盖新 session_type。

### D-004：移动页采用英文并保留完整 Transcript

- Status: Confirmed
- Date: 2026-09-29
- Source question: PRD and prototype review
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，原型批注与确认消息
- Confirmation quote: “对的，就是这样。”
- Decision: 首版 UI 使用英文；通话主界面展示最近多句对话并渐隐，完整 Transcript 通过抽屉查看。
- Reason: 与现有平台及英文演示 Bot 保持一致。
- Consequences: 字幕关闭只影响显示，不影响采集和历史。
- Updated artifacts: PRD、mobile-call 原型、mobile-web-call Delta Spec。
- Verification: 主界面至少展示 Maya/You 各两句，抽屉可纵向查看完整会话。

### D-005：首版不引入 TURN

- Status: Confirmed
- Date: 2026-09-29
- Source question: PRD confirmation item 11
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，PRD 确认消息
- Confirmation quote: “prd文档已确认。”
- Decision: 首版仅配置直连/ STUN 所需 ICE 能力，不部署 TURN；通过真实移动网络连接成功率决定后续补充。
- Reason: Demo 阶段先验证价值并控制服务器与带宽成本。
- Consequences: 对称 NAT、严格企业网或部分跨境网络可能连接失败，页面必须提供安全失败和 Retry。
- Updated artifacts: PRD、design、tasks、verification plan。
- Verification: 多种真实手机网络记录 ICE 类型、连接成功率和失败分类；结果不得伪造成已覆盖 TURN。

### D-006：后台 Share 原型纳入 Gate 1

- Status: Confirmed
- Date: 2026-09-29
- Source question: Admin Share prototype review
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，当前消息
- Confirmation quote: “可以，没问题。补进去吧。”
- Decision: Bot 后台增加 Share 标签，展示二维码与 Web Link，并支持复制、下载、预览、停用和重新启用。
- Reason: 管理员需要一个完整、可演示的分享入口。
- Consequences: Share 管理受后台登录保护；公开链接不要求登录。
- Updated artifacts: PRD V0.1.1、admin-share 原型、bot-config Delta Spec。
- Verification: 三种 Share 状态和所有主操作进入 UI 状态矩阵。

### D-007：公开名称与介绍在 Share 页显式配置

- Status: Confirmed
- Date: 2026-09-29
- Source question: Q-001
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，当前用户消息
- Confirmation quote: “Q1和Q2都选A，可以”
- Decision: Share 页增加 `Public title` 和可选 `Public description`。首次默认值由 Bot 名称生成，但两字段与内部 Bot 名称、Opening Message 和 System Prompt 分离，只在管理员发布时进入公开页。
- Reason: 保留首次发布的低操作成本，同时让管理员明确控制访客文案。
- Consequences: Share 需要可编辑表单；公开 API 只返回已发布的 title/description，description 为空时移动页隐藏。
- Updated artifacts: PRD V0.1.2、bot-config/mobile-web-call Delta Specs、design、Share 原型和状态矩阵。
- Verification: 首次默认、编辑不改内部 Bot 名称、空 description 和公开 API 裁剪测试。

### D-008：公开 Demo 使用显式发布快照

- Status: Confirmed
- Date: 2026-09-29
- Source question: Q-002
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，当前用户消息
- Confirmation quote: “Q1和Q2都选A，可以”
- Decision: 发布时原子生成不可变配置快照；后续保存 Bot 只改草稿，公开 Demo 继续使用上一个发布快照，直到管理员点击 `Publish updates`。
- Reason: 防止未经验证的 Bot 编辑静默改变对外演示。
- Consequences: Share 页需要 Published/Unpublished changes 状态；公开 Session 从已发布快照创建，而不是当前 Bot 草稿。
- Updated artifacts: PRD V0.1.2、bot-config/voice-session Delta Specs、design、Share 原型和状态矩阵。
- Verification: 发布、草稿修改、重新发布、失败回滚、重启持久化与 Session 快照隔离测试。

### D-009：批准 WebRTC 与二维码生产依赖

- Status: Confirmed
- Date: 2026-09-29
- Source question: Q-003
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，当前用户消息
- Confirmation quote: “原型确认，依赖选 A”
- Decision: 批准 `pipecat-ai[webrtc]==1.8.1`/`aiortc`、`@pipecat-ai/small-webrtc-transport@1.10.7` 与 `qr@0.7.0`，先执行不调用付费 Provider 的本地兼容性验证。
- Reason: 使用官方 WebRTC 客户端传输和无运行时依赖的本地 QR 编码器，避免自研媒体/二维码协议。
- Consequences: Python 与前端 lockfile 增长；兼容性实验失败时必须更换候选版本而不得伪造通过。
- Updated artifacts: design、tasks、dependency manifests/lockfiles（待实现）、compatibility evidence。
- Verification: 依赖安装、import/build、offer/PATCH/data-message 与 QR 生成/下载测试。

### D-010：User Gate 1 基线确认

- Status: Confirmed
- Date: 2026-09-29
- Source question: Synchronized Gate 1 prototype review
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，当前用户消息
- Confirmation quote: “原型确认，依赖选 A”
- Decision: 确认同步 Q1-A/Q2-A 后的移动通话与后台 Share 原型，冻结为 User Gate 1 实现基线。
- Reason: 产品范围、行为契约、公开文案、发布快照和页面状态已唯一化。
- Consequences: 开发可进入 Checkpoint A–C；任何有意视觉或产品行为偏离必须先更新 Change 并重新确认。
- Updated artifacts: prototypes/README.md、verification/gate-1-review.md、verification/ui-checklist.md、tasks.md、delivery-status.json。
- Verification: 冻结 `mobile-call.html` SHA-256 `4dfa2c9d85b1e821c76691972f1b67ac0c30201d284f6d82e13da0e820f0c4de` 和 `admin-share.html` SHA-256 `cf15954f60f53218e6b3d3d06b8ccc0cad6b2982730eff88f3a30fe1fcc01040`。

### D-011：公开 Demo 凭据跟随 Bot 的 Provider 凭据库

- Status: Confirmed
- Date: 2026-09-29
- Source question: Q-004
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，当前用户消息
- Confirmation quote: “跟着bot走啊”
- Decision: 发布快照不复制 API Key，只引用 Bot+component+provider 凭据；替换同 Provider Key 立即供已发布 Demo 使用，未发布的 Provider 草稿切换不改变旧快照；显式清除旧快照依赖的 Key 时 Demo 变为 unavailable，恢复该 Key 或重新发布后恢复。
- Reason: 凭据生命周期归属于 Bot，同时保留已确认的不可变配置发布快照和明确撤销能力。
- Consequences: Bot 存储需保留各组件各 Provider 的加密凭据；公开 Session 按发布快照中的 Provider 引用解析当前 Bot 凭据；公开端永不接收或返回 Key。
- Updated artifacts: PRD、bot-config/voice-session Delta Specs、design、tasks、delivery status。
- Verification: 覆盖同 Provider 轮换、未发布 Provider 切换、清除/恢复已引用 Key、重新发布和重启持久化。

### D-012：本地与 DigitalOcean Storage Key 全部轮换并保留业务数据

- Status: Confirmed
- Date: 2026-09-30
- Source question: Q-005
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，当前用户消息
- Confirmation quote: “行啊，那就用A吧。听你的，我就是需要重新填写各provider 的 API Key，对吧”
- Decision: 选择 Q-005 Option A；为本地和 DigitalOcean 分别生成新的 `VOICE_AGENT_STORAGE_KEY`，保留 Bot、历史、录音与公开链接，不删除数据。轮换后由用户重新填写各 Bot 已保存的 ASR/TTS/LLM Provider API Key。
- Reason: 无法排除已暴露 Key 曾用于服务器，采用全范围轮换可关闭泄露风险，同时避免破坏业务数据。
- Consequences: 轮换完成到 Provider Key 重新录入之前，依赖已保存凭据的 Bot 和公开 Demo 会暂时不可用；BYOK 路径不受影响。
- Updated artifacts: open-questions、tasks、delivery status、deployment evidence。
- Verification: 新 Key 不输出到日志；本地与服务器进程均加载新 Key；数据库和公开链接保持；已保存 Provider 凭据重新录入后公开 Demo 恢复。

### D-013：授权部署新版到 DigitalOcean 后再配置 Provider Key

- Status: Confirmed
- Date: 2026-09-30
- Source question: Production deployment authorization
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，当前用户消息
- Confirmation quote: “可以，你部署吧”
- Decision: 先将当前确认版本部署到 DigitalOcean，再由用户在新版线上后台重新填写两个 Bot 的 Provider API Key。
- Reason: 避免在旧版后台重复录入，并将后续真实通话验证统一放在最终生产版本上执行。
- Consequences: 部署和重新录入完成前，现有两个 Bot 的保存凭据通话保持暂时不可用；本次部署不得调用付费 Provider。
- Updated artifacts: decision log、deployment evidence、delivery status。
- Verification: 生产部署健康、数据保留、WebRTC 前置检查通过；Provider Key 重新录入后再进行外部真实通话验证。

### D-014：首版生产使用 Cloudflare 公共 STUN

- Status: Confirmed
- Date: 2026-09-30
- Source question: Q-006
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，当前用户消息
- Confirmation quote: “那就先选A吧，用Cloudflare STUN，先试试”
- Decision: DigitalOcean 生产环境配置 `stun:stun.cloudflare.com:3478`，并授权在服务器 UFW 放行实际媒体 UDP 范围 `32768–60999`；首版仍不启用 TURN。
- Reason: 公共 STUN 无需新增服务或账号，适合先完成 Demo 的生产链路，再以中国大陆真实网络数据决定是否升级。
- Consequences: 依赖 Cloudflare 公共 STUN；严格 NAT、企业网或部分大陆移动网络仍可能直连失败。若 DigitalOcean Cloud Firewall 已启用，还需同步开放媒体 UDP 范围。
- Updated artifacts: assumptions、design、deployment documentation、delivery status。
- Verification: 生产启动预检、UFW 状态、STUN 地址数量、WebRTC offer/PATCH，以及 iOS/Android 的 Wi-Fi/移动网短通话矩阵。

### D-015：保留并确认现有 Evaluation 卷为生产数据

- Status: Confirmed
- Date: 2026-09-30
- Source question: Q-007
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0eafe-96b8-7852-ab43-84923e45ca53`，当前用户消息
- Confirmation quote: “选 A，保留并确认为生产数据”
- Decision: 在服务器内先备份现有 Evaluation SQLite 数据库，然后只写入 `deployment.provenance=production` 与 `deployment.empty_history_verified=true`；保留现有 8 个批次、12 份报告、29 条评审和 153 条基准结果。
- Reason: 这些记录位于专用生产卷，且未命中仓库记录的已知本地验收批次；产品方明确选择保留。
- Consequences: 既有评测历史继续在线可见；部署预检将把该卷作为生产数据接受，不会执行空历史清理。
- Updated artifacts: open-questions、decision log、delivery status、production deployment evidence。
- Verification: 备份与原库完整性检查通过；标记写入后数据行数不变；部署预检和容器内 verify 通过。
