# r89 来源覆盖修复独立复审（2026-10-26）

**当前修复：未发现新增确认缺陷；可关闭R88正常RTC来源范围缺口与R89 late-track实现缺陷。整体最终验收仍INSUFFICIENT EVIDENCE，不自签全Change PASS、Checkpoint C或User Gate 2。**

评审按change-verifier执行，未参与实现，未改生产代码/测试/status/tasks，未付费、部署、提交或推送；未重跑旧有限实验/浏览器。只独立复跑必要离线用例并核查已存严格RTC证据。

## 1. 已确认根因与修复安全性

原`observe_native_reader`在reader刚启动时一次包装`client._audio_input_track`。锁定SDK可能在其后才赋真实track，或运行中替换track；这两种情况下音频仍由SDK读取，但decoded证据旁路绕过早期wrapper。两个明确红灯均为实际PCM存在而`encoded_source_unavailable`，不能把这些旧失败当正常来源证明。

当前在**同一原生Resampler.resample入口**观察实际decoded AV帧，随后调用原始resampler、原样返回其frames。SDK读哪个track由它自己决定，不包装/固定/回写早期track；codec、采样率、声道、raw.pts和PCM不改。证明仍要求原server RTP payload hash/PTS、真实processed区间、连续覆盖、PCM hash一致及有效双端时钟；没有放宽SSRC、源epoch、时间缺口、过期或歧义条件。finally只恢复仍由本observer持有的resampler。

这修复的是**已复现的生命周期覆盖缺陷**；不表示任意重连/SSRC切换或硬件采集均获支持。

## 2. 独立验证与真实证据

独立命令：

```sh
.venv/bin/python -m pytest tests/test_td_rtp_input.py tests/test_rtp_capture_clock.py tests/test_td_rtp_integration.py tests/test_td_rtp_writer.py tests/test_td_webrtc_cancel.py -q
```

实际 **21 passed /1依赖警告/1.14s**，见`stage-review/r89-independent/source-reader-tests.txt`。包含晚赋track、替换track、原生Opus/PyAV/SDK PCM一致性、SSRC变化拒绝、缺包与来源冻结/时钟等。研发late-track-red.txt保留原两条明确红灯；原r88故障不被删改。研发完整回归为756 passed /5 warnings/40.55s，本评审未重复全量。

已存同正式入口的新源码严格`RTC_E2E=1`冷启动及同进程第二通warm，各为不同call ID、每通两个响应1:1/1:2。评审逐项重算源端frame包络、双端认证锚、同包hash与媒体样本偏移，全部一致：

| 通话 | call ID | 1:1 E2E范围约ms | 1:2 E2E范围约ms |
|---|---|---:|---:|
| 冷启动 | 229e84a0-9af1-43a3-a155-2c6778454f9b |590–1334|804–1845|
| 同进程第二通 |7fcf4340-689c-46e6-9212-40892d9b18d3|544–1277|1272–1815|

范围仍很宽，不证明精确低延迟、P95、增量性能或物理ADC/出声。这里是local-real RTC/HTTP/Worklet/历史，推理厂商替身，不是external-real。不是关闭E2E断言的限域播放检查，也不是拿一次诊断偶然绿替代原失败。

## 3. 无效诊断与历史归因边界

首次新fixture诊断向slots `CallCapture`追加不存在的属性，使observer抛异常并退出；`diagnostic-probe-error.txt`明确保留。该次计数0是**诊断探针错误**，不能作为“生产没有转发native帧”事实或生产根因。

改sidecar后有效诊断观察/接受101 native帧，候选源锚能够冻结；这是定位材料，不单独据此关闭R88红灯。真正关闭依据是两条独立生命周期红灯→代码修复→离线绿灯，以及新源码冷/暖严格正式RTC复验。

R88原失败当时没有server native覆盖快照，无法唯一回溯其全部原因。允许关闭当前修复/可用性缺口，应保留“历史当次全部根因未唯一确定”，不得写成已证明旧失败必然只有late-track一种原因。

## 4. 关闭判断与剩余

- **R89 late-track实现缺陷：可Resolved**，两个明确故障场景由当前观察入口覆盖且原音频不改。
- **R88-NORMAL-RTC-SOURCE-BOUNDS：可Resolved（当前候选严格来源范围复验）**，原红灯及不能唯一历史归因边界保留。
- **R89无效诊断：作为探针错误纠正并保留**，不把无效0当prod事实。
- 原r88六项返修结论不变，本次未发现新代码缺陷。当前实现与自测包可交继续完整独立审核，不因未有最终PASS先要求研发再造任务。

尚未验证：手机/Safari/弱网、跨连接可靠时钟、硬件AEC/耳机外放双讲、目标1核1GB/Python3.11、真实厂商多场景/完整取消、精确新增延迟及RTC正式采用。均不能由本次冷暖两通变为PASS。没有新产品决定或收费授权，本次不建议重复已通过同例。

最终输入包待研发冻结；后续仅逐hash核对，不复用r88包hash代表新r89源码。

## 门禁时点

本次独立结构门禁当时因R89-DIAGNOSTIC-STYLE（临时fixture诊断两行超过100字符，Open且尚未标披露）返回1 error/40 warnings；日志保留。这是研发质量记录收口项，不当作已通过，也不是新的来源映射缺陷。已通知研发，不并发代改；最终封包以其修复/披露后的新门禁及冻结hash为准。

## 研发交付记录收口复核

研发已将canonical self-test-report简明指向r89、旧原文完整保留；当前tasks按核心实现、设备/真实效果未验证、独立/用户职责分类，剩余7未勾并非7个新增核心缺陷。评审只读核对68个场景身份与Delta行号/标题完全一致，63个后端选择器AST存在且在当前756 JUnit中实际执行通过、4个UI文件存在、1个仅冻结原型场景明确标static；不是宣称此次完成全部68场景的最终语义独立验收。当前22ID、completion-audit及冷暖历史重启/实际Sessions1440/390日志相符。

R89-DIAGNOSTIC-STYLE已修复并披露，研发最终门禁0 errors/39 warnings。原独立门禁时点错误日志保留，不再作为当前阻塞。两历史重启逐值相同，正式Sessions两视口2通过2.1秒来自研发实际证据，评审未重复执行浏览器。

**当前研发实现与自测包可交完整独立审查；整体最终验收仍INSUFFICIENT EVIDENCE。** 当前来源缺口支持关闭，未再发现确认代码缺陷。完整独立C/用户Gate2/默认采用及设备/真实完整效果不由本次收口自签。最终包尚待冻结，后续仅hash核对。

## 最终r89冻结包只读核验（2026-10-26）

评审独立核验1176个包内文件逐项hash、13项关键当前生产/测试与前端demo.html/login.html入口一致；package-reproduction-check所列238项实测运行/测试输入hash均与最终归档清单相符。archive SHA-256：`b15cf0ac6b6bd7a5faca0e575447b8d9a88615a5577c2d282375e4e854f33e8a`。当前独立报告、68Scenario、22ID及历史任务原文存在，清单无.env/数据库/录音/trace/node_modules。

研发新目录复现126核心后端、25客户端及完整前端构建通过，不冒称包内重跑完整756；初次遗漏两个Vite HTML入口导致构建失败和依赖/缓存前置失败均保留，最终包补齐两入口且238输入一致。评审此次只读核验，不新增测试、不改包、不重打归档；本补记仅在外层报告。

**研发实现与自测交付包可交完整独立审核；全产品仍INSUFFICIENT EVIDENCE，非PASS/Checkpoint C/User Gate2。** 当前来源缺口及原六项返修支持关闭，原失败与历史非唯一归因边界保留。设备/真实完整效果/目标环境/精确性能及默认RTC采用仍如当前自测范围披露。
