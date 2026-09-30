# Design: Mobile WebRTC Demo Sharing

## Goals

- 让管理员把一个可运行的 Bot 发布为稳定的二维码/Web Link。
- 让访客在手机浏览器中无需登录或填写 Key 即可主动发起低摩擦语音演示。
- 只新增 Transport 与公开入口，复用现有 Bot snapshot、ASR、LLM、TTS、barge-in、语速、录音、历史和指标。
- 保留现有 Chat/Web call WebSocket 测试，不为演示另造第二套 Pipeline。

## Current State

- 单个 FastAPI 服务承载网站登录、Bot API、Session Store、历史和 WebSocket Pipeline。
- 前端使用 `@pipecat-ai/client-js` + `@pipecat-ai/websocket-transport`；后端使用 `FastAPIWebsocketTransport`。
- `run_voice_agent_session()` 在函数内直接构造 WebSocket transport，尚不能注入其他 transport。
- `SessionRequest.session_type` 只允许 `web_call` / `chat_test`。
- Bot 没有 Published 状态，页面 `Publish` 目前只是视觉按钮；没有 Demo Link 存储或公开路由。
- 当前 Python 依赖只安装 `pipecat-ai[...,websocket]==1.8.1`，本地环境缺少 `aiortc`；前端也未安装 Small WebRTC transport。
- Docker 只映射 TCP 8000；WebRTC UDP/ICE 在当前部署中尚未验证。

## Product and Service Boundaries

```text
Authenticated admin browser
  └─ Bot Settings / Share
       └─ Publish snapshot + manage one Demo Link

Unauthenticated mobile browser
  └─ /demo/{public_id}
       ├─ read safe public metadata
       ├─ request microphone after user click
       ├─ create one mobile_web_call lease
       └─ negotiate Small WebRTC

Existing FastAPI service (same first-release process)
  ├─ ProductAuthMiddleware
  │    ├─ protects admin/share routes
  │    └─ explicitly allows only the public demo allowlist
  ├─ BotStore + DemoLinkStore
  ├─ SessionStore (shared 3-session limit)
  ├─ SmallWebRTC request handler / connection registry
  └─ shared Pipeline runner
       └─ ASR → LLM → TTS → history/metrics
```

首版不新增 VM 或独立业务服务。是否需要单独媒体网关由 Checkpoint B 的真实手机网络和服务器资源证据决定；不得仅因设计存在就宣称当前 DigitalOcean 部署已满足 WebRTC UDP 可达性。

## Data Model

### Bot publication

`bots` 增加发布元数据：

- `is_published`
- `published_at`
- `published_revision`
- `published_snapshot` 或等价的不可变版本化快照引用
- `public_title_draft` / `public_description_draft`
- 已发布快照中的 `public_title` / `public_description`

`public_title_draft` 首次由 Bot name 自动带入且可编辑；`public_description_draft` 可选，空值表示公开页不展示介绍。它们不回写 Bot name、Opening Message 或 System Prompt。

发布前必须通过与真实 Bot Session 相同的配置与保存凭证检查。发布在单一事务中保存完整 Bot 配置快照、公开文案、revision 与 Demo Link；失败时保留上一个已发布版本。普通 Bot 保存只改变草稿，公开 Session 始终从已发布快照创建。快照不复制凭证明文或密文，只保存 Bot+component+provider 凭据引用；同 Provider Key 轮换立即供旧快照使用，未发布 Provider 草稿切换不改变旧快照，清除被引用 Key 时公开 Demo 变为 unavailable。公开 API 永远不返回 Prompt、Provider Key 或内部配置对象。

### Demo links

在现有 Bot SQLite 数据库新增 `demo_links`：

| Field | Rule |
|---|---|
| `id` | 内部 UUID，不公开 |
| `bot_id` | 外键且唯一；一个 Bot 最多一个 link |
| `public_id` | 至少 128-bit CSPRNG 编码，不可枚举；URL 中唯一公开标识 |
| `is_active` | 停用/启用，不更换 `public_id` |
| `created_at` / `updated_at` | UTC 时间 |

`public_id` 是公开 bearer-like locator，不是管理凭证：公开读取仅得到安全展示字段；发布、启停和管理读取仍要求后台 Cookie。删除 Bot 时以外键/事务使链接立即失效。

## API Surface

### Authenticated admin

- `GET /api/bots/{bot_id}/share`：返回草稿/已发布 public copy、revision、是否有未发布变更、完整 Demo URL 和 link active 状态。
- `POST /api/bots/{bot_id}/publish`：接收并校验 public title/description，验证 Bot 配置与凭证，原子创建新发布快照；首次发布同时创建 Demo Link。
- `POST /api/bots/{bot_id}/share/enable`：恢复同一 link。
- `POST /api/bots/{bot_id}/share/disable`：阻止新的公开 Session；不强制中断已连接通话。

所有写操作使用现有网站 Cookie，并保持安全、幂等的状态语义。二维码由前端根据 API 返回的绝对 Demo URL 本地生成。

### Public demo

- `GET /api/public/demos/{public_id}`：返回 active/unavailable 与安全 public metadata。
- `POST /api/public/demos/{public_id}/sessions`：零配置创建 `mobile_web_call`，返回 `session_id`、短时单次 `connection_url` 和过期时间。
- `POST/PATCH {connection_url}`：Small WebRTC offer/ICE request handler；URL 内的 opaque capability 只能成功认领一次。

公开会话请求体为空或仅含协议版本；任何 Bot ID、Provider、Prompt、voice 或 Key 字段都按 `extra=forbid` 拒绝。公开路由使用精确 allowlist 加入 `ProductAuthMiddleware`，不得用宽泛 `/api/public/*` 规则意外开放管理 API。

## Transport Refactor

### Shared runner

将现有函数拆为两个边界：

1. `create_voice_transport(...)`：现有测试路径创建 `FastAPIWebsocketTransport`；移动路径接收已建立的 `SmallWebRTCConnection` 并创建 `SmallWebRTCTransport`。
2. `run_voice_agent_pipeline(transport, lease, ...)`：只依赖 Pipecat `BaseTransport` 的 input/output processors，不感知 WebSocket/SDP/ICE。

ASR、LLM、TTS、上下文聚合器、Opening Message、barge-in、动态语速、CallCapture 和 Pipeline Worker 保持单份实现。旧 `run_voice_agent_session()` 可作为 WebSocket 兼容 wrapper，避免一次性改写全部现有调用与测试。

### Small WebRTC signaling

- 后端保持 Pipecat `1.8.1`，增加其 `webrtc` extra；但不将上游 request handler 直接暴露为公开端点。在外层实现 `SessionBoundSmallWebRTCHandler`，将 offer/PATCH 与短时 Session capability 绑定。
- 本地静态审阅确认上游 `handle_web_request()` 会捕获 callback 异常后继续返回 SDP answer。适配层必须在响应前确认 Pipeline task 已登记；登记失败时关闭 peer connection、释放 lease 并返回可重试的安全错误，不得把“有 answer 但无 Bot”当成成功。
- 上游 DEBUG 路径会输出 request、signaling message 和 ICE candidate。生产日志配置必须对这些 logger 降噪/过滤；本项目自有日志只记录 request/session 关联 ID 与安全错误类别，不记录 SDP、candidate 或 IP。
- `PATCH` 不能只依赖客户端提供的 `pc_id`；路由先校验 session capability，再校验 capability 所属 connection 与 `pc_id` 一致。
- 前端不盲目采用 npm latest。先对当前 `@pipecat-ai/client-js@1.13.0` 执行无付费的实际 offer/PATCH/data-message 兼容性验证，再锁定 `@pipecat-ai/small-webrtc-transport` 的确切版本。
- `SessionStore.claim()` 与 offer 处理必须形成单一原子认领边界，避免同一 token 启动两个 Pipeline。
- WebRTC handler 与 FastAPI 现有 lifespan 合并；关闭服务时先停止接收 offer，再关闭 connections/tasks，最后清除 leases 和凭证。
- 客户端只有在 transport `connected/ready` 后进入 Live；ICE checking 不等于已连接。

## Audio Contract

- 浏览器 WebRTC 媒体通常使用 Opus；编解码和抖动缓冲停留在 WebRTC/aiortc transport。
- Pipeline 输入继续是 mono PCM16 16 kHz，输出继续是 mono PCM16 24 kHz；Transport 负责与 WebRTC media track 之间的转换。
- `AudioRecorder` 继续录制进入 ASR 前的用户 PCM，不录制 Agent 下行。
- 不向 ASR 暴露浏览器原始 codec，也不改变现有 Provider sample-rate 映射。

## ICE, Network and Deployment

- D-005 已确认首版不引入 TURN relay；这意味着严格 NAT、企业防火墙或部分跨境移动网络可能失败。
- Checkpoint B 前必须验证 DigitalOcean 主机、Docker 网络与云防火墙的 UDP/ICE 可达性；当前只映射 TCP 8000，不能视为已满足。
- 优先保持单 VM：为 WebRTC 配置明确的 ICE/STUN、主机候选与 UDP 防火墙策略。若 aiortc 无法在当前容器网络下发布可达 candidate，可改用 Linux host networking 或独立同机进程，但 API 契约不变。
- 不静默接入公共 TURN 或付费媒体服务。若直连成功率达不到 PRD 的 95% 建议目标，登记产品问题并请求是否引入 TURN/媒体网关。
- 生产必须使用 HTTPS；麦克风权限与 WebRTC 信令不支持降级到公网 HTTP。
- D-014 已确认首版生产配置 Cloudflare 公共 STUN `stun:stun.cloudflare.com:3478`；该服务只参与地址发现，不提供 TURN 中继或成功率保证。
- 生产部署叠加 `compose.webrtc.yaml`：VoiceAgent 使用 Linux host networking，Uvicorn 监听
  宿主机 8020 供现有 Nginx 反代；本地基础 Compose 继续使用 bridge，不改变开发体验。
- 生产启动必须同时具备非空 STUN 配置与 host-network 声明；容器预检只输出 STUN 数量和
  Linux ephemeral UDP range，不输出 URL、SDP、candidate、IP 或 Key。Cloud Firewall/UFW
  仍需按目标 Droplet 的真实范围人工配置和 external-real 验证。

## Frontend Design

### Admin Share

- 在正式 Bot 顶层导航加入 `Share`，复用现有 rail、Bot selector、topbar、色彩与响应式变量。
- Active 显示 QR、只读 Web Link、Copy、Download QR、Open demo page 与 Disable。
- Share 页编辑 Public title 和可选 Public description；title 首次由 Bot name 带入，后续独立编辑。
- 修改草稿后显示 `Unpublished changes`，访客继续看到上一个发布版本；点击 `Publish updates` 成功后才更新公开 Demo。
- Disabled 保留同一 link 的展示但清楚标记不可用，并提供 Enable。
- Unpublished/credential-incomplete 不展示可用二维码，不允许生成 Session。

### Mobile call

- 新建正式移动 route/组件，而不是在管理后台 CSS 上叠加临时壳。
- 生产 UI 通过数据适配层支持 fixture/real API；Checkpoint A 与 B 必须使用相同 route、components 和 DOM。
- 页面状态机：Ready → Permission → Connecting → Live → Reconnecting/Error/Ended。
- Pipecat transport callbacks 驱动连接状态；Pipeline transport messages/现有事件驱动字幕与 Listening/Thinking/Speaking。
- 主字幕显示最近 4 句并渐隐；完整 Transcript 抽屉保存当前连接期间的确认文本，不伪造原型示例消息。

## Session, History and Telemetry

- `SessionRequest` / `SessionLease` / history model 扩展 `mobile_web_call`。
- 公开会话创建时立即占用共享 pending/active 容量；失败或过期必须释放。
- 历史仅在真实事件发生后写入 Turn/录音/指标；连接前失败可以保留 attempt 状态，但不得出现伪造文本或音频。
- 现有浏览器 playback/telemetry 事件通过 WebRTC data/transport message 或受 Bearer 保护的 HTTP endpoint 上报；实现阶段必须选择一个单一来源，避免重复计时。
- 新增无敏感信息的漏斗事件：view、start click、permission result、connected、end、safe error。不得记录 Transcript、音频、完整 IP 或指纹。

## Security

- 管理 Cookie 与公开 Demo Link/Session token 三种权限边界分开；任何公开标识都不能调用管理 API。
- Demo Link 只定位 Published Bot；真实 Provider keys 仅在服务端从加密存储解析并进入内存 lease。
- SDP/ICE、Provider payload、Key 与音频内容不得写入普通日志。
- 对公开创建 Session 增加按 link/IP 的轻量速率限制与全局 3 路容量保护；只记录桶化/短时计数，不形成持久指纹。
- CORS/Origin、CSRF 与缓存头按公开读取、公开创建、后台管理分别配置；公开 metadata 不缓存失效状态过久。

## Failure and Recovery

| Failure | Behavior |
|---|---|
| Link/Bot unavailable | 公开统一 unavailable，不暴露内部原因 |
| Microphone denied/missing | 不创建有效会话；本地指导并 Retry |
| Capacity full | Busy + later retry；不显示最大并发数 |
| Offer/ICE timeout | 清理 lease/connection；Retry 创建新 Session |
| Short ICE interruption | 显示 Reconnecting；有界恢复成功后回 Listening |
| Unrecoverable disconnect | 结束旧会话、保存准确状态、允许新 Session |
| Provider failure | 安全分类；停止媒体与 Pipeline，不显示 Key/URL/raw payload |
| Admin disables link mid-call | 阻止新会话；已连接会话允许正常结束 |

## Dependency Plan

- Python: 将锁定依赖改为 `pipecat-ai[...,webrtc,websocket]==1.8.1`，由 lockfile 固定 `aiortc`/相关传递依赖。
- Frontend candidate: `@pipecat-ai/small-webrtc-transport@1.10.7`；其 peer range `client-js ~1.13.0` 与当前 1.13.0 匹配，但安装后仍必须通过隔离的无付费 offer/PATCH/data-message 验证才能确定。
- QR candidate: `qr@0.7.0`，使用 encoding-only 入口本地生成 SVG，需下载时在浏览器转 PNG；无 runtime dependency，MIT/Apache-2.0 双许可。
- 上述两个前端包和 Python WebRTC extra/`aiortc` 均尚未安装，取得新增生产依赖的用户确认后才能修改 lockfile。
- 不升级 Pipecat/client-js 主版本，不同时迁移现有 WebSocket transport。

## Evidence Plan

- `static`: PRD、Delta Specs、design、依赖签名、auth allowlist、SQL migration 审阅。
- `fixture`: 正式管理/移动 route 使用固定 Published/Disabled/Unavailable/Live/Error 数据。
- `mock`: SDP/ICE handler、single-use claim、transport callbacks、disconnect cleanup、public override rejection。
- `local-real`: 本机真实浏览器麦克风与 Small WebRTC，使用受控本地服务，不调用付费 Provider时可用 mock services。
- `external-real`: DigitalOcean + iOS Safari/Android Chrome + Wi-Fi/4G/5G，真实 Provider 与短通话；需要逐次授权并限制数据、次数和费用。

## Open Design Dependencies

None. Q-001/Q-002 were confirmed as Option A on 2026-09-29; Gate 1 baseline can be frozen after the synchronized prototype is reviewed and its unique hashes are recorded.
