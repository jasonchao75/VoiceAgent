# Tasks: Add Mobile WebRTC Demo Sharing

## 0. User Gate 1 — Contract and Baseline

- [x] 更新 PRD，纳入后台 Share 页面、二维码/Web Link 与已确认原型。
- [x] 创建 proposal、Delta Specs、design、decision files 和 delivery manifest。
- [x] 将移动通话与后台 Share 原型复制到 Change 内并建立追溯映射。
- [x] 创建 UI annotations、状态矩阵、Gate 1 review 和 UI checklist。
- [x] 关闭 Q-001：公开 title/description 的来源。
- [x] 关闭 Q-002：已发布 Bot 修改后的生效语义。
- [x] 同步两项决定到 PRD、Spec、design、tasks 和原型。
- [x] 用户确认完整 Gate 1；记录原话、日期、来源，并冻结唯一 SHA-256 baseline。
- [x] 运行 `python3 scripts/quality/verify_change.py add-mobile-webrtc-demo-sharing` 并清除 Gate 1 阻塞。

## 1. Storage, Publication and Admin API

- [x] 实现 Bot 发布字段/版本、Bot+component+provider 凭据库与可回滚 SQLite migration，保持现有 Bot 行为。
- [x] 实现 `DemoLinkStore`：每 Bot 唯一、稳定 public_id、active 状态、事务与级联失效。
- [x] 实现发布前配置/凭证完整性验证和安全错误。
- [x] 实现受网站 Cookie 保护的 Share read/publish/enable/disable API。
- [x] 实现精确公开路由 allowlist，回归证明公开 link 不能访问任何管理 API。
- [x] 为 restart、delete、disable/enable、凭据轮换/清除/恢复、并发写入和失败回滚补充测试。

## 2. Session and Small WebRTC Transport

- [x] 按 D-009 锁定 Pipecat WebRTC extra、aiortc、Small WebRTC 前端包与 QR 包。
- [x] 以无付费调用测试确认 Pipecat 1.8.1 connection/request-handler/transport 签名。
- [ ] 验证并锁定 `client-js@1.13.0` 与 Small WebRTC transport 的 offer/PATCH/data-message 兼容组合。
- [x] 扩展 `mobile_web_call` Session/Lease/history 类型并保持旧类型兼容。
- [x] 实现零配置 public session admission、override 拒绝、rate limit 和共享 3 路容量门禁。
- [x] 将 Pipeline runner 改为注入 BaseTransport；保留现有 WebSocket wrapper。
- [x] 实现 session-bound Small WebRTC offer/PATCH 适配层、single-use claim、lifespan 和 connection registry；不直接暴露上游 handler。
- [x] 防止 callback 启动失败后仍返回可用 answer，并覆盖 Pipeline 登记失败、lease 释放与 connection 关闭测试。
- [x] 过滤 Pipecat SDP/signaling/candidate DEBUG 日志，增加日志不包含 SDP、IP 与 candidate 的回归测试。
- [x] 验证 PATCH 同时需要有效 session capability 与匹配的 `pc_id`，覆盖跨会话冒用。
- [x] 复用 AudioRecorder/CallCapture；验证 PCM16 16 kHz 输入和 24 kHz 输出契约。
- [x] 覆盖 token 重用、offer timeout、ICE/media failure、disconnect、shutdown 和资源释放。（真实公网 ICE 仍属于部署验证）
- [x] 麦克风授权前不创建公开 Session；过期/放弃协商会终结 pending history、清理 event buffer 并释放凭据与容量。
- [x] 支持同 capability/pc_id 的 Pipecat renegotiation 与 ICE restart，不重复 claim 或启动第二条 Pipeline。

## 3. Production UI — Engineering Checkpoint A

- [x] 正式 Bot route 增加 Share tab，使用固定 fixture 对照冻结原型。
- [x] 正式 mobile route 使用同一生产组件加载 Ready/Connecting/Live/Reconnecting/Error/Ended fixtures。
- [x] 实现最近 4 句渐隐字幕、完整 Transcript 抽屉及 36px+入口；不得带入原型示例数据。
- [x] 选择并确认 QR 生产依赖，完成真实 URL 编码、可解码性和 PNG 下载 fixture 验证。（真机相机扫码留待 Checkpoint B）
- [x] 完成固定桌面及 320/375/390/430px 结构、视觉、键盘与无横向溢出检查。
- [x] 保存 Checkpoint A actual/diff 证据，不更新冻结 baseline。

## 4. Real Integration — Engineering Checkpoint B

- [x] Share 页面接入真实 publication/link API，验证重启持久化、启停与删除失效。
- [x] Mobile 页面接入真实 public metadata/session API 和 Small WebRTC transport。
- [x] 接入真实 transport/Pipeline 状态、字幕、静音、字幕开关、挂断和 Call again。
- [x] Opening Message 与后续发声统一由 TTS text 进入字幕；短网恢复显示 Reconnecting，恢复后回 Listening，致命失败释放媒体。
- [x] Share 编辑即时显示 Unpublished changes；公开链接不存在、停用或凭据不可用统一使用冻结安全文案。
- [x] 验证 Opening Message、barge-in、动态语速、历史录音和逐轮指标未回归。（共享 Pipeline 与全量本地回归）
- [x] 验证公开/后台 auth 边界、CORS/Origin、缓存和安全错误。
- [x] 增加生产 host-network Compose 覆盖、STUN/host-network fail-closed 校验与无敏感信息部署预检；本地 bridge 保持不变。
- [x] 增加公开访问/开始/麦克风结果及 Session 连接/结束/安全失败分类埋点；只记录哈希 Demo 引用、枚举网络信息和耗时。
- [x] 按 D-012 轮换本地与 DigitalOcean Storage Key，保留数据并输出不含密钥的 Bot/Provider 重新录入清单。
- [x] 按 D-015 备份并确认现有 Evaluation 卷为生产数据，保留全部既有评测历史。
- [ ] 在当前 DigitalOcean 部署验证 UDP/ICE、Docker/host network 与防火墙；不伪造 TURN 覆盖。
- [ ] 在取得逐次授权后执行 iOS Safari/Android Chrome、Wi-Fi/移动网 external-real 短通话矩阵。
- [ ] 记录连接成功率、connect_ms、candidate 类型、失败分类和资源占用；不记录敏感内容。

## 5. Independent Verification — Engineering Checkpoint C

- [x] 运行后端 unit/integration、前端 build、Playwright desktop/mobile 与现有 WebSocket regression。
- [x] 验证 3 路并发、第四路 busy、超时和断开后的容量释放。
- [x] 完成可访问性、键盘、语义、焦点、触控热区和 `scrollWidth <= clientWidth` 检查。
- [x] 完成实际截图、visual diff、差异比例、known deviation 和环境记录。
- [x] 运行 `python3 scripts/quality/verify_change.py add-mobile-webrtc-demo-sharing`。
- [x] 委派独立 Agent 加载 `change-verifier`，结果写入 `verification/independent-review.md`。（PASS：可进入受控部署测试，非 Gate 2 最终验收）
- [ ] 独立结果必须为 PASS，且所有 Open 问题、known issues 和 unverified items 已解决、排除或经用户接受。

## 6. User Gate 2 and Archive

- [ ] 向用户提交最终产品验收：真实 Share 页面、手机 WebRTC 主链路与已披露限制。
- [ ] 用户明确接受后记录 User Gate 2 原话、日期与来源。
- [ ] 将 Delta Specs 合并到主规格。
- [ ] 归档 Change，并建议提炼可复用的多 Transport Pipeline 经验。
