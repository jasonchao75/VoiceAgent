# Independent Change Review

## Verdict

**INSUFFICIENT EVIDENCE — 当前不可提交 User Gate 2。**

当前提交 `43ee1d03bb1a636c38000d2b774b99ab594aafd5` 的代码、local-real 回归、CI、生产部署、host-network/STUN/UFW 预检和线上不可用状态均通过；未发现新的本地产品代码阻塞。但首版核心验收路径——真实 Published Bot 在生产 route 完成浏览器 offer/PATCH/data-message、双向音频、Provider Pipeline、历史保存及公网 ICE——尚未执行。两个生产 Bot 还需要用户重新录入轮换后失效的 Provider API Key，Cloud Firewall 控制面也未确认。

因此，本结论不是实现失败，也不是 Gate 2 PASS：当前可以继续生产实测准备，但必须补齐真实通话证据后重新独立验收，才能向用户提交最终产品验收。

Review date: 2026-09-30
Reviewer role: independent Change verifier
Scope: `add-mobile-webrtc-demo-sharing`

## Evidence reviewed

### Static and fixture — PASS

- PRD V0.1.3、Delta Specs、D-001～D-015、tasks、delivery status、production deployment record 与 UI checklist 已复核；开放产品问题为 0。
- 两个冻结原型 SHA-256 仍为 `4dfa2c9d...f0c4de` 与 `cf15954f...fcc01040`，Gate 1 baseline 未变化。
- Checkpoint A/B/C 继续复用正式 routes/components/DOM；没有独立静态业务壳。
- 4 组数值视觉证据尺寸、changed-pixel ratio 与 mean-absolute delta 已在前轮独立重算通过。
- `43ee1d0` 将所有非活动 screen 同步为 `aria-hidden=true` 与 `inert=true`，并为 Live call title 提供语义 `h1`；对应回归覆盖 unavailable 状态与活动 Live 状态。

### Local-real — PASS

- 本轮独立复跑 full pytest：`374 passed`，仅 3 个依赖 deprecation warnings。
- Frontend production build：PASS。
- 定向 Ruff：PASS；定向 mypy（API/auth/WebRTC/publication 与相关测试）：PASS。
- Change guard：`PASS: 0 errors, 6 warnings`；warnings 均为已披露的非本地实现完成项。
- 已有本地真实 aiortc 证据覆盖首次 offer/PATCH、ICE restart、`pc_id` 轮换、单 Pipeline、资源清理；浏览器 fixture/loopback 证据覆盖锁定前端包的 offer/PATCH/data-channel 基础兼容。

### External-real deployment/runtime — PASS within stated boundary

- GitHub CI run `36705082129`：`success`，head SHA 为 `43ee1d0`；安全检查、OpenSpec guard、backend checks、frontend build 与 production image build 全部成功。CI 日志记录 Python 3.11 环境 `282 passed, 92 skipped`。
- GitHub CD run `36705391988`：`success`，head SHA 为 `43ee1d0`；deploy 与 public health verification 均成功。
- CD 日志确认容器 WebRTC preflight：`host_network=true`、`stun_server_count=1`、UDP ephemeral range `32768–60999`。
- 独立只读公网复查：`https://platform.voiceagentdemo.org/health` 返回 `status=ok` 且 pending/active sessions 均为 0；产品根路径 303 到登录页；公开 Demo HTML route 返回 200；缺失 public metadata 返回 404。
- `production-deployment.md` 记录的 390×844 生产浏览器检查证明 unavailable 页面无横向溢出，AX tree 仅暴露安全错误状态；本轮 Computer Use 浏览器 surface 不可用，未重复生成第二份浏览器 AX/screenshot 证据。
- 以上证明部署、HTTPS、静态页面、服务健康和主机侧 WebRTC 前置条件；不证明公网 WebRTC 媒体成功。

## Missing Gate 2 evidence

### E-001 — Provider credentials not restored

- D-012 已完成 Storage Key 轮换，两个 Bot 与业务数据保留；旧加密 Provider Key 按预期无法再解密。
- 用户必须在线上后台为目标 Bot 重新录入 ASR/TTS/LLM Key。完成前公开 Demo 只能保持 safe unavailable，无法验证真实 Pipeline。

### E-002 — Production WebRTC/media path not exercised

仍缺少同一次真实生产 Session 的可追溯证据：

1. Published Bot metadata 与 Session admission 成功；
2. browser package 对生产 endpoint 完成 offer、非空 candidate PATCH 与 data-message；
3. ICE connected，记录 candidate type、connect time 与安全失败分类；
4. 麦克风上行进入 ASR，Opening Message/后续 TTS 下行可听且字幕一致；
5. barge-in、mute、captions、短断网恢复、hangup/Call again 成立；
6. `mobile_web_call` 历史、用户录音、Transcript、逐轮指标和资源释放准确。

### E-003 — Network/browser support target unproven

- DigitalOcean Cloud Firewall 控制面规则无法从 VM 验证；需要控制台确认，或由一次真实 ICE 成功间接证明当前路径可达。
- iOS Safari、Android Chrome、Wi-Fi 与移动网矩阵均未执行；无 TURN 决策下的 ≥95% 建议连接成功率尚无样本。
- 当前 390×844 线上证据来自 unavailable 状态，不等同于真实手机浏览器的 Ready → Live → Ended 通话。

### E-004 — Delivery record closure

- `delivery-status.json` 仍有 KI-022 与 UV-002/003/007/008 为 Open；其中 KI-022 属于 Change 外的历史 Playwright 环境/预期漂移，应在 Gate 2 前明确解决、排除出本 Change 或取得用户接受，不能保持未归类的 Open 状态。
- tasks 中生产 UDP/ICE、真机网络矩阵、连接指标、独立 PASS 与 Gate 2/归档项仍未完成。

## Evidence boundary

| Level | Result | Proven | Not proven |
|---|---|---|---|
| `static` | PASS | PRD/spec/decision traceability、auth/telemetry/deploy contracts、frozen baseline | — |
| `fixture/mock` | PASS | UI 状态矩阵、响应式/无障碍、failure/recovery、offer/PATCH guards | 真实公网媒体 |
| `local-real` | PASS | SQLite/API、aiortc、browser loopback、build/test/type/lint | DigitalOcean ICE 与付费 Providers |
| `external-real deployment` | PASS | CI/CD、production image、host network、STUN/UFW preflight、HTTPS health、unavailable UI | Cloud Firewall、真实 Session/audio/history |
| `external-real product` | NOT RUN | — | 核心移动通话与浏览器/网络支持目标 |

## Reproducible checks

```text
git rev-parse HEAD
# 43ee1d03bb1a636c38000d2b774b99ab594aafd5

python3 scripts/quality/verify_change.py add-mobile-webrtc-demo-sharing
# PASS: 0 errors, 6 warnings

.venv/bin/python -m pytest -q
# 374 passed

npm run build  # from frontend/
# PASS

.venv/bin/ruff check src frontend tests scripts/deploy
# PASS

.venv/bin/mypy src/api.py src/auth.py src/webrtc.py src/publication.py \
  tests/test_publication.py tests/test_webrtc.py tests/test_webrtc_deploy.py
# PASS

gh run view 36705082129 --json status,conclusion,headSha,jobs
gh run view 36705391988 --json status,conclusion,headSha,jobs
# both completed/success at 43ee1d0
```

No paid Provider call, real customer data, credential value read, production mutation, frozen baseline update, or product-code change was performed by this review.

## Required next actions

1. **User action:** 在生产后台重新录入目标 Bot 的 ASR/TTS/LLM API Key，并确认 Demo 状态恢复 available；密钥不要发送到聊天或日志。
2. **User authorization:** 在发起任何可能计费的真实 Provider 短通话前，按本次测试明确授权数据范围、厂商、次数/时长、费用上限与停止条件。
3. **Deployment check:** 在 DigitalOcean 控制台确认 Cloud Firewall UDP `32768–60999`；若未启用 Cloud Firewall，记录该事实即可。
4. **External-real test:** 至少完成一个 production-route 端到端短通话闭环，再执行 iOS Safari/Android Chrome × Wi-Fi/移动网矩阵并记录安全指标。
5. **Re-review:** 关闭或明确排除所有 Open records，独立验收结果更新为 PASS 后，才可提交 User Gate 2。用户明确接受后才能合并主规格与归档 Change。
