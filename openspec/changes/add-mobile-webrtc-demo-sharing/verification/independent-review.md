# Independent Change Review

## Verdict

**BLOCKED — B-005/B-006/B-007 已关闭，但 Q-005 仍阻止 DigitalOcean 部署。**

本轮三项修复均通过增量独立复验，没有发现新的产品代码阻塞。当前自动门禁仅剩未关闭的 Storage Key 安全问题 Q-005；在用户确认 Key 的使用范围并完成轮换处置前，不可执行 DigitalOcean 部署。Q-005 关闭后，本 Change 可恢复为“可进入受控部署测试”，但仍不是 User Gate 2 最终验收。

Review date: 2026-09-30
Reviewer role: independent Change verifier
Scope: `add-mobile-webrtc-demo-sharing`

## Resolved findings

### B-005 — Telemetry 隐私与字段契约：PASS

- `ShortWindowRateLimiter` 不再保存完整 IP：key 由进程内随机 salt、scope、public ID 与 client 标识生成不可逆 bucket；原始 IP 不进入 bucket key 或日志。
- 每次访问会清理超过 60 秒的所有 bucket；独立时钟探针确认旧 bucket 被移除，active bucket 数保持有界。
- `BrowserEvent` 对 `mobile_*` 事件携带 `text` 明确返回校验错误；直接 Pydantic 探针与回归测试均通过。
- 正常移动 telemetry 只发送枚举 candidate/network/error 分类与耗时；未发现 Transcript、音频、Key、SDP、candidate 地址或完整 IP 的日志路径。

### B-006 — 麦克风拒绝顺序、分类与指导：PASS

- 页面仍先请求并释放 permission-only microphone stream，只有成功后才请求公开 Session。
- `NotAllowedError`、`SecurityError` 和 Pipecat permission wrapper 均分类为 `denied`；缺失设备分类为 `unavailable`。
- denied 页面显示浏览器设置与 Microphone 权限指导并保留 Retry，不再透传浏览器原始错误文案。
- desktop/narrow Chromium 的现有 30 项相关 Playwright 证据覆盖“0 次 Session 请求、一次 denied 埋点、指导文案可见”。本轮未更新冻结原型或 baseline。

### B-007 — 首次 WebRTC 部署回滚：PASS

- 目标 revision 在部署前强制要求 `compose.webrtc.yaml`，缺失时 fail closed。
- rollback checkout 到旧 revision 后，Compose helper 会按文件是否存在动态选择：旧 revision 没有 WebRTC override 时使用基础 `compose.yaml`，不会再因缺文件跳过恢复。
- 合并 Compose `config --quiet`、shell syntax 与回滚回归测试均通过。

### Checkpoint C 数值视觉证据：PASS

- 4 组 frozen-render baseline、同尺寸正式页面 actual 与 amplified diff 文件齐全且均可读取；对应尺寸分别为 Admin `1440×1000`、Mobile live/transcript `390×760`、Mobile reconnecting `390×844`。
- 独立重算 `changed pixel ratio / mean absolute delta` 与文档完全一致：Admin `9.09% / 5.01%`、Mobile live `6.54% / 2.39%`、Transcript `14.70% / 4.76%`、Reconnecting `10.58% / 3.05%`。
- `diff/README.md` 已明确阈值、归一化方法、4× contrast 与 known deviations；`ui-checklist.md` 的状态、尺寸和比例已同步。
- 两个冻结 HTML 的 SHA-256 仍为 `4dfa2c9d...f0c4de` 与 `cf15954f...fcc01040`，未更新 Gate 1 baseline。

## Remaining blocker

### Q-005 / KI-020 — 暴露的 Storage Key 尚未处置

- Q-005 的记录准确：需要用户确认已暴露的 `VOICE_AGENT_STORAGE_KEY` 是否也用于 DigitalOcean，才能确定本地/服务器轮换、凭据重新录入或数据重置范围。
- 自动门禁结果：`BLOCKED: 1 error(s), 7 warning(s)`；唯一 error 是 Q-005。
- 该问题不否定 B-005～B-007 的实现质量，但在安全处置完成前阻止部署。

## Evidence boundary

| Evidence level | Result | Boundary |
|---|---|---|
| `static` | PASS for B-005～B-007 | 字段校验、权限顺序、动态 Compose 与冻结 hash 可追溯 |
| `fixture` | PASS from current evidence | 30 项相关 desktop/narrow Chromium 与 4 组数值视觉差异证据通过；使用正式 route/components/DOM |
| `local-real` | PASS for B-005～B-007 | 16 项 Python 定向测试、Compose 合并与安全契约探针通过 |
| `external-real` | NOT RUN | DigitalOcean UDP/ICE、iOS Safari、Android Chrome、Wi-Fi/移动网与真实 Provider 仍待验证 |

## Independently reproduced checks

```text
.venv/bin/python -m pytest -q tests/test_webrtc_deploy.py tests/test_publication.py
# 16 passed

.venv/bin/ruff check src/api.py tests/test_publication.py tests/test_webrtc_deploy.py
# PASS

.venv/bin/mypy src/api.py tests/test_publication.py tests/test_webrtc_deploy.py
# PASS

env VOICE_AGENT_STORAGE_KEY=verification-placeholder-key \
  VOICE_AGENT_STUN_URLS=stun:stun.example:3478 \
  docker compose -f compose.yaml -f compose.webrtc.yaml config --quiet
# PASS

bash -n scripts/deploy/platform_voiceagent.sh
# PASS

python3 scripts/quality/verify_change.py add-mobile-webrtc-demo-sharing
# BLOCKED: Q-005; 1 error, 7 warnings
```

No paid Provider call, real customer data, production mutation, credential read, frozen baseline update, or product-code change was performed by this review.

## Remaining gates

1. 用户回答 Q-005，并按确认范围完成 Storage Key 轮换与必要的 Provider Key 恢复。
2. 自动门禁恢复 PASS 后，方可进入 DigitalOcean 受控部署测试。
3. 部署阶段完成 HTTPS、真实 STUN、Cloud Firewall/UFW、公网 UDP/ICE、production-route audio/data-message 与 iOS/Android 网络矩阵。
4. external-real 和用户明确验收完成前，不可 User Gate 2、合并主规格或归档 Change。
