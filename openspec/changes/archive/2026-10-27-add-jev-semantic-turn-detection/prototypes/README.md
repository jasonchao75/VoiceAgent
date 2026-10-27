# TD交互原型：v0.14已确认基线

[打开原型](index.html) · [本轮改动对照](../verification/prototype-v014/changes.md) · [当前需求](../design.md) · [研发清单](../tasks.md)

- 冻结版本：v0.14（D-047清理后）；确认日期：2026-10-21；状态：Confirmed（D-048）。
- 唯一冻结基线 SHA-256：`657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4`
- 已按D-026至D-048同步本轮涉及的设置、说明与固定示例；具体覆盖及未覆盖范围见改动对照，不将浏览器模拟示例冒充运行时功能。
- User Gate 1已确认。来源：当前Codex聊天，D-047清理后用户原话“行，这回差不多了。那么User Gate1是不是算完成了”；详见[决策D-048](../decisions/decision-log.md)。后续有意修改此基线须重新确认。
- 页面沿用既有布局、配色和组件；仅原型，无真实ASR/Jev/TTS、工具执行、后台持久化、发布或付费请求。测试时不输入真实密钥。

## 区域与行为映射

| 区域 | Delta要求 | 本轮状态 |
|---|---|---|
| 关键词与纯编号规则 | Assistant keyword rule condition; Strict local identifier routing | 去掉独立关键词开关，必需门槛与整段生成上下文说明；不在设置中加入分流示例控件 |
| 工具与更正 | Controlled identifier tools for mixed input | 正常混合输入提交工具、更正清空工具、成功后确认、失败不伪报；仅固定示例 |
| 收集与播放 | New collection after success; Confirmed playback arbitration | 同轮保留、新采集清空；P03=B、清空停止旧跟读、未播修订合并等已确认规则说明 |
| 语义TD与Final修订 | Controlled response restart after material final revision | 配置页不呈现后端修订说明；行为契约见Delta，诊断示例仅在Sessions |
| ASR来源 | Self-developed TD source for every catalog ASR model | AssemblyAI ID修为universal-3-5-pro；六模型self_developed入口检查 |
| 缓存与AEC边界 | Runtime echo cache recovery; 本轮自测范围 | 固定发布音色/语速补合成留痕；浏览器AEC优先、服务端不新增、实机效果待验证 |
| 中英与Sessions | TD prototype language switching; Per-turn TD history evidence | 新文案中英切换，新增工具/重答4轮会话；原3会话保留 |

浏览器检查：1440×1000、1024×1000及390×844定向检查；390px抽屉358/358、弹窗356/356，稳定文档宽度390/390；无页面JS错误、无外部请求。截图与可复现检查见[证据](../verification/prototype-v014/browser-check.json)。这不代表真实厂商、物理AEC、完整可访问性或多浏览器验收。

[原型历史](history.md)保留；原型不是Checkpoint A，正式研发必须复用正式路由/组件加载fixture再接真实API。

## D-056明确批准的UI差异（2026-10-23）

Jev连接页保留显式保存Key复选框；不勾选不保存新Key。仅此控件允许偏离冻结v0.14，冻结文件及SHA不变，其他配置/布局仍按基线验证。Q-044关闭，不代表Checkpoint A/B或整包已完成。

## D-072：已确认手机布局差异

用户选择 Q-047=B：窄屏保留现有正式全局顺序，当前页面内容在前、Bot 列表在后；桌面及 TD/Share 内容规则不变。此为明确批准的单处视觉差异，不更新冻结 v0.14 文件或校验值。对比入口为 prototypes/shell-comparison/index.html，实际正式页证据见 verification/development-20261025-r71/ui/。批准差异不等于整页或 Checkpoint A/B 已通过。

## D-073：播放指标范围

批准仅为真实播放/E2E显示有证据的范围与误差/来源，证据不足仍缺失；补认证时钟关联与持久化，不改音频传输或冻结HTML/SHA，不默认采用候选播放器，不授权费用。r78播放范围及r81 WS源端E2E已有本地实现/自测；RTC源端与厂商/设备范围仍缺，原型文件不改。
