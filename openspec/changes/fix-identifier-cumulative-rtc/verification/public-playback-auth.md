# 匿名扫码播放鉴权修复（2026-10-27）

## 已确认生产原因（external-real，只读日志）

会话 `fabf7023-2f52-4b30-a411-6d632622fcd6` ICE 已连接；连接事件 elapsed=13048.5ms，失败事件 elapsed=14885.3ms，`playback_failure_reason=playback_receipt_unconfirmed`。nginx 显示 events=204，但 playback-events/playback-clock/rtp-input=401，且发生于清理前。

`ProductAuthMiddleware._uses_call_bearer` 只列 events/metrics，遗漏新增播放端点。匿名扫码用户的有效通话 Bearer 先被网站 Cookie 检查阻挡，无法确认播放，客户端按保护规则中断。这是本次会话的确定原因；不用于追认旧096cb487会话的未知首因。

## 修复边界

精确加入 playback-events、playback-clock、playback-clock/{sample_id}、rtp-input。只跳过网站登录 Cookie；端点自身的 active session Bearer、任务归属、时钟挑战和 RTP 来源校验全部保留。管理端及任意嵌套路径继续要求网站登录。无音频协议、数据库、凭证或业务配置变更。

## Red → Green

- 修改生产代码前，新增 website_auth=True 用例：有效通话 token 到达 receipt 路径时返回401而非预期409，复现生产故障；auth=False通过。
- 修复后 auth/receipt API：12 passed。覆盖匿名有效token、无token、异任务、原文拒绝、clock probe/ack、RTP来源与管理端保护。
- 本地真实浏览器，正式页面/真实 RTP/实际 AudioWorklet 回执、厂商 fixture：Chrome138 1 passed；当前 Chromium desktop+narrow 2 passed。后台API客户端单独登录，扫码页面cookies为空，/api/bots=401，播放clock=201、回执=204，无401/403。覆盖编号累计跟读、停止、清空、普通回答及退出。
- 之前浏览器fixture关闭网站认证，未覆盖生产登录配置，是此前验证遗漏；新增显式认证开启模式用于回归。
- 全后端测试：803 passed、9 skipped（既有跳过）；Ruff 与 mypy src 通过。

## 证据及范围

本地证据 `/tmp/voiceagent-public-auth-chrome138`、`/tmp/voiceagent-public-auth-current`；测试数据 `/tmp/voiceagent-auth-playback-20261027`，服务日志 `/tmp/voiceagent-auth-playback-server.log`。不提交临时数据库/日志。无收费厂商调用、无真实客户音频外发。

真实安卓硬件、Safari、扬声器/AEC及弱网仍未验证；桌面Chrome138不能等价为安卓真机验收。独立审核见 public-playback-auth-review.md。
