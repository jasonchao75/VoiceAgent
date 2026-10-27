# 部署记录（2026-10-27）

- 用户授权：D-001，先自测/独立审核通过后上线。
- 发布提交：393b060bfa7ad1734065e78c5e9031732d29a752。
- [CI 40487240625](https://github.com/jasonchao75/VoiceAgent/actions/runs/40487240625)：success。
- [自动部署 40487567424](https://github.com/jasonchao75/VoiceAgent/actions/runs/40487567424)：success。
- SSH只读复核：部署checkout HEAD与上述SHA相同；容器running healthy。
- 公开HTTPS /health：status ok，pending_sessions=0，active_sessions=0。
- 未修改数据库或机器人配置，未发起收费调用。本次健康检查不等于真实通话效果通过。
- 回退代码版本：c7d46ea060d43f639e2c03a3d4626b4983aace38，无本次数据库迁移。
- 用户下一步：刷新页面重新拨测，Partial数字满足配置条件即本地跟读；异常按新session ID核查。
- 本地测试服务18871/18872已停止；证据与隔离库留在self-test.md列出的/tmp路径，不提交真实录音、密钥或测试数据库。部署后本记录及状态更新留在本地，避免文档提交再次触发生产构建。

## 后续兼容修复上线
- 失败连接释放补丁8112278：CI40490977670、CD40491387733成功。
- 新旧RTP接口兼容eada6b4e62dcfa80cf6e737cfb3e5c8b0b1cdee2：CI40492339475、CD40492716633成功。SSH确认生产HEAD完全一致，容器running healthy。
- 无数据库迁移、无机器人配置修改、无收费调用。回退代码为8112278；回退会失去旧接口兼容。
- 本轮18871/18872隔离服务已停止。Chrome138测试包和证据保留在browser-compatibility.md列出的/tmp路径，不提交。
- 安卓硬件、Safari、AEC及弱网仍未验；未将桌面138测试等同于手机体验通过。

## 连接启动修复上线
- 提交66b872b2c84779992a0f6bee22db6bcbab7e1703；CI40497716544、自动CD40498025696均success。
- SSH确认生产checkout HEAD一致，容器running healthy；公开/health status=ok、pending=0、active=0。
- 独立审核startup-rtc-review.md为PASS；详细复现/回归startup-repair.md。
- 无数据库迁移、无真实厂商测试、无机器人配置修改。代码回退点eada6b4（会恢复已发现的启动/清理缺陷）。
- 隔离服务18871/18872已关闭，测试证据/tmp/voiceagent-connect-*和被忽略test-results保留，不提交音频、数据库或日志。部署后证据更新留本地，避免仅文档再次触发部署。

## 匿名扫码播放鉴权修复上线
- 提交2f25841812212908a68da56e5bd4143de8086e5c；CI40503606417、自动CD40503983684均success。
- 公开health=ok，pending=0、active=0；无token的不存在会话clock请求返回Session authorization is invalid，证明已进入通话鉴权，未放开无凭证访问。
- 自测803 passed、9 skipped，匿名且启用网站认证的浏览器3组通过，独立审核public-playback-auth-review.md为PASS。
- 无数据库/机器人配置修改，无收费调用。回退点66b872b（会恢复匿名扫码鉴权缺陷）。
- 专用18871/18872服务已停止；证据与隔离库路径见public-playback-auth.md，保留不提交。部署后记录留本地，避免仅文档再次部署。
- SSH复核服务器HEAD与2f25841完整SHA一致，容器running healthy。
