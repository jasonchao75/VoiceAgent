# Engineering Assumptions

## Status

- Active assumptions: 5
- Last reviewed: 2026-09-30

## Assumptions

### A-001：同一 FastAPI 服务承载管理页、公开页和 WebRTC 信令

- Status: Active
- Assumption: 首版不增加独立应用服务；现有 FastAPI 进程新增公开路由和 Small WebRTC handler。
- Basis: 当前会话、Bot、历史和 Pipeline 都在同一进程边界，首版并发上限仅 3。
- Why it is low risk: 不改变已确认用户流程，部署拓扑后续可拆分。
- Affected work: API 路由、lifespan、部署端口与健康检查。
- Validation: 3 路并发下事件循环、CPU、内存和 UDP 端口验证。
- Rollback: 将公开路由与 WebRTC handler 移到独立进程，保持 API 契约不变。

### A-002：二维码由前端本地编码 Demo Link

- Status: Active
- Assumption: Share 页使用固定版本的本地 QR 编码库生成 SVG/Canvas 和下载文件，服务端只提供 URL。
- Basis: 二维码不含额外数据，避免新增图片存储和文件清理路径。
- Why it is low risk: 二维码只是同一 URL 的表现形式，可切换为服务端生成而不改变产品契约。
- Affected work: Share 页面依赖与下载交互。
- Validation: 真实手机相机扫描、纠错级别和长 URL 回归。
- Rollback: 改为服务端按 link_id 生成 PNG/SVG。

### A-003：WebSocket 测试路径继续存在

- Status: Active
- Assumption: `web_call`/`chat_test` 继续使用现有 FastAPI WebSocket transport；只有 `mobile_web_call` 使用 Small WebRTC。
- Basis: 已生效主规格与现有自动化测试依赖 WebSocket 路径。
- Why it is low risk: 新路径是增量能力，不改变现有测试体验。
- Affected work: Transport factory 与 session_type 分支。
- Validation: 现有 WebSocket 回归与新增 WebRTC 回归并行通过。
- Rollback: 关闭公开路由即可完全回退新路径。

### A-004：STUN 地址由部署环境显式配置

- Status: Active
- Assumption: 首版通过 `VOICE_AGENT_STUN_URLS` 将同一组 STUN 地址传给浏览器和 aiortc；生产值按 D-014 配置 Cloudflare 公共 STUN，代码仍不内置固定第三方地址。
- Basis: D-005 已确认直连/STUN 且不引入 TURN，D-014 已确认首版生产使用 Cloudflare 公共 STUN。
- Why it is low risk: 只改变部署配置，不改变公开产品流程；错误配置会在启动时拒绝，且只接受 `stun:`/`stuns:`。
- Affected work: WebRTC handler、公开 Session 响应、移动客户端 transport 和部署检查。
- Validation: DigitalOcean 上记录 candidate 类型，并分别用 Wi-Fi/移动网验证。
- Rollback: 清空环境变量恢复仅主机候选；若成功率不足则按 D-005 重新决策 TURN。

### A-005：DigitalOcean 首版使用 Linux host networking 暴露 aiortc UDP

- Status: Active
- Assumption: 仅生产部署叠加 `compose.webrtc.yaml`，让 VoiceAgent 容器使用 Linux host networking，并让 HTTP 服务继续监听宿主机 8020；本地 `compose.yaml` 仍使用原有 bridge/端口映射。
- Basis: aiortc 当前从 Linux ephemeral UDP range 动态分配媒体端口，项目没有可靠的应用级端口范围配置；Change design 已明确优先在单 VM 上使用 host networking。
- Why it is low risk: 不改变 API、Session 或用户流程，且生产覆盖文件可单独移除；部署启动校验会阻止漏配 STUN/host-network 声明。
- Affected work: production Compose、部署脚本、健康检查、DigitalOcean/UFW UDP 放行说明。
- Validation: Compose 合并配置、容器内预检、DigitalOcean candidate/真实手机矩阵。
- Rollback: 部署脚本移除生产覆盖文件并恢复 bridge；在再次开放移动 Demo 前另行实现固定 UDP 映射或 TURN/媒体网关。
