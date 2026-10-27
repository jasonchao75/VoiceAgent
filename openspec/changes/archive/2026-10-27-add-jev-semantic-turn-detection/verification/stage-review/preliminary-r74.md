# r74 阶段技术审查（非最终独立验收）

日期：2026-10-25。评审为本轮未参与实现的独立子 Agent。按 change-verifier 的只读追踪、证据分级原则审查；用户限定这是阶段提前审查，因此不写 independent-review.md、不授予独立 PASS / Checkpoint C / User Gate 2。

## 结论

**r74 快照尚不自包含，有一个 P1 工程封装缺陷需要修复。** 指标修复的定向离线检查通过；受控正式 RTC 入口有可核对的本机真实链路证据，但默认入口没有采用候选链路，不能扩大为正式全范围完成。未发现需要重新询问已确认产品规则的新冲突。

## P1：审核包遗漏自动化回归的实际输入

ID：R74-REVIEW-MISSING-ASR-FIXTURE（delivery-status 已登记）。r74 312 个文件各自 hash 正确并不证明依赖闭包完整。

独立将 `development-20261025-r74/review-inputs.tar.gz` 解包至全新临时目录，在该目录用现有锁定环境运行：

```sh
/Volumes/work/OpenCode/VoiceAgent/.venv/bin/pytest tests/test_td_asr_events.py::test_saved_flux_digits_boundary_uses_only_its_known_pcm_sample_extent -q
```

实际 `1 failed in 0.06s`：缺少 `openspec/changes/add-jev-semantic-turn-detection/verification/development-20261023-r47/deepgram-td-asr-synthetic-v1-D-062.jsonl`。该测试直接读取真实已留存失败事件，不能靠工作区存在文件支持包内复现。

这是一个“审核输入依赖闭包”问题，其他静态依赖遗漏应合并修复，避免每个漏文件独立登记。完成条件：新包保留旧包不覆盖，补已脱敏必要输入或等价固定 fixture；从全新解包目录实际执行离线回归，禁止读开发工作区兜底，保留退出码及输入校验。无需任何付费调用。

复现日志：`r74-review-evidence/missing-fixture.txt`。临时解包目录为 `/var/folders/fd/4jrj88t51tdcpn9l_qmdm_lw0000gn/T/voiceagent-r74-independent-3vebozp0`，仅非敏感副本，不含新录音/数据库/凭证。

## 已核查的历史指标边界

静态追踪 `src/history/capture.py`：`browser_event(first_playback)` 在 `td_commit_ms` 非空时不再写入 `browser_playback_ms`。`playback_receipt` 要求预备任务身份；有渲染坐标时检查时钟/采样率/非负因果坐标，按原任务 turn_id 标记已观察，迟到回执不写当前新轮。

离线执行 `tests/test_td_history.py tests/test_capture.py`：**23 passed / 0.67s**。覆盖旧事件不制造 TD 延迟、旧任务回执关联原轮及持久化；证据 `r74-review-evidence/history-targeted.txt`。

当前 TD 的 playback_ms / turn_to_playback_ms 仍无跨钟校准路径，真实回执只保留坐标；有渲染事实则 `render_clock_uncorrelated`，无回执则 `client_playback_unconfirmed`。这是已经披露的未完成指标能力，不是本轮新增 bug，也不能把 null 当指标验收完成。旧 native 路径仍使用服务器收件时刻；不可把该值当跨钟实际渲染延迟。

## Final / 编号与正式入口

核对 Delta 的 `Controlled response restart on final after partial submission`、`Confirmed playback arbitration`、D-068、D-072，及 `response_revision.py`、`serial_output.py`、`identifier_output.py`、`rtp_output.py`、`td-rtc-entry.js`：响应包含 turn/source/epoch/语音代次屏障，Final 仅替换当前 Partial 一次；任务 EOS 不伪报渲染结束，清空与输出身份沿共享仲裁器传递。

`create_app(development_rtp_candidate=False)` 默认关闭候选；公开 session 只有显式开发 opt-in 且自建 TD 才返回 `rtp_candidate`，同条件安装 `candidate_playback` / `webrtc_candidate`。因此 r68/r69 证据是**正式页面/接口的受控开发模式**，并非默认线上模式已采用。

检查 r68/r69 测试与记录：真实 loopback RTP、Worklet、鉴权回执、SQLite；ASR/LLM/TTS 为替身。r68 同时钟旧答停播后 Final 开始、持久重答一次；r69 续说跟读不停、提问排队、清空旧跟读/旧待播及历史。原始失败和 fixture 修复均保留。未重新执行任何已消费有限 RTC 实验。

这些证据支持已列本地组合，不支持真实厂商取消/弱网/设备兼容，更不支持最终采用。r70 n=1 两路径观测含未校准原链捕获成本，不能证明新链更快或准确的新增端到端延迟；既有报告已作此限制，无需再包装为新问题。

## 未审查与剩余关闭方式

- 未运行外部 API、生产服务、硬件麦克风/扬声器、手机/Safari/Firefox、弱网、并发/长通话，也未重复 699 项全量。真实厂商缺口需新的精确数据/次数/费用/停止条件授权；旧授权不可重放。
- 精确历史指标仍需工程实现跨钟关联及误差边界；本阶段不替产品定义新的计算口径，不用收件时间补数字。
- 候选默认采用仍需用户根据可用的延迟/兼容证据决定；已批准开发接入不等于批准正式替换。
- 包依赖闭包与陈旧顶部状态属于自主工程/文档修复；不需要用户决定。主自测报告头部仍称 r71、M2/M3 表仍有“完整 RTC 任务未接”旧文字，应统一当前摘要，保留逐轮历史即可。
- 完整 UI A/B、Spec 全场景、缓存故障与真实来源/重连矩阵未在本次独立重复，不能据本报告关掉对应未完成任务。

门禁实跑：`PASS: 0 errors, 45 warning(s)`，59 tasks unchecked。这里只证明结构门禁通过，不能替代行为或最终独立验收。

## r75 修复后最小复核

随后独立审查 `development-20261025-r75/closure/review-inputs.tar.gz`，SHA-256 为 `ef7243425f0894fc3e4aa190f7ab436f850c8286d5152c24af6196c488c9c7f2`。新目录解包包含缺失的 ASR JSONL，内容 SHA `d28ed84a232a74a588274807633eacc9d025f178f7b1e990368ebcd4e9af5b2f` 与原证据一致；从解包目录执行同一失败单例，**1 passed / 0.03s**。

因此，原发现的具体缺失 fixture 已独立复核修复。审核输入依赖闭包是否整体关闭，仍取决于主任务的新目录完整离线回归；本次没有重复该全量，也没有授予包整体/功能/最终独立 PASS。r74 原失败结论保留。复核命令输出及新临时目录见 `r74-review-evidence/r75-asr-fixture-recheck.txt`、`r75-recheck.json`。
