# 匿名扫码播放鉴权：独立专项审核

- 日期：2026-10-27；审核者：`public_auth_review`。
- 结论：**PASS，限 PUBLIC-PLAYBACK-AUTH 本地工程修复范围**。未参与实现，未修改需求，不代替用户验收或上线验证。
- 本报告补充既有 `independent-review.md`，不覆盖此前各专项结论。

## 需求与实现核对

已读取 proposal、README、Delta Spec、决策和既有审核记录。新增验收场景要求扫码者凭当前通话 Bearer 上报播放证据，无需后台 Cookie；管理端保护保持不变。本次没有页面或视觉结构修改，沿用正式 mobile-demo 页面，不需要另造原型。

`ProductAuthMiddleware._uses_call_bearer` 仅将明确的会话证据路径交给业务鉴权：playback-events、playback-clock（含单层 challenge ID）、rtp-input。路径段数量和空 session ID 均检查，任意子路径和管理接口不放行。放行网站 Cookie 不等于放行通话鉴权：三类端点仍通过 `store.get_active(session_id, token)`，验证该会话存在、未关闭及密钥恒时比较；随后继续执行任务归属、时钟 challenge 或服务器 RTP 来源验证。没有移除播放证明或改用数据通道传音频。

## 独立复验与证据

- 本审核者运行 `python3 scripts/quality/verify_change.py fix-identifier-cumulative-rtc`：PASS，0 errors / 4 warnings。当时 auth 缺陷及收尾任务尚未关闭；另两项为既存真实环境未测与旧会话原因不可追溯，均不能按本次修复冒认完成。
- 本审核者运行 `/tmp/voiceagent-r91-py311/bin/python -m pytest tests/test_auth.py tests/test_playback_receipts_api.py -q`：**12 passed**。开启网站鉴权后先创建会话，再清空 Cookie；管理 API 返回 401，有效通话播放回执成功；缺失凭证、错误任务、错误时钟和未建立的 RTP 来源均继续拒绝。
- 本审核者运行 `/tmp/voiceagent-r91-py311/bin/python -m pytest tests/test_session.py -q`：**7 passed**。另静态核查 `get_active` 的会话绑定及令牌比较。
- 浏览器测试由开发者执行，本审核者读取实际产物复核，未冒认独立重跑：Chrome 138 旧 RTP 接口 1 passed；Chromium 153 桌面及窄屏 2 passed。正式页面浏览器 Cookie 为空且 `/api/bots` 为 401，只有独立 API provisioning 客户端持后台 Cookie。验证使用正式 RTC/RTP/Opus/AudioWorklet，ASR/LLM/TTS 为离线替身。
- `/tmp/voiceagent-public-auth-chrome138/formal-identifier-receipts.json`：6 条播放回执全部 204，证据请求 20 条 201、26 条 204，无 401/403；engineVersion 为 138.0.7204.183。
- `/tmp/voiceagent-public-auth-current/`：桌面、窄屏诊断的 engineVersion 均为 153.0.8010.12；最后一轮共享回执文件含 6 条 204、证据请求仅 201/204。两个项目共享回执文件名，不能将该单文件声称为两套独立留存；两项通过结果由测试运行记录支持。

## 边界与发现

本次未发现阻塞修复交付的新增实现缺陷。既有测试关闭网站鉴权，导致生产扫码路径遗漏未被发现；新鉴权开启回归直接覆盖该缺口。

未验证真实安卓硬件、Safari、弱网、扬声器/AEC、付费厂商端到端以及本次生产部署；不把桌面窄屏当作手机实机。没有调用收费 API、发送真实客户音频或修改生产配置。临时证据均位于上述 `/tmp` 路径，不提交凭证、录音或测试数据库。
