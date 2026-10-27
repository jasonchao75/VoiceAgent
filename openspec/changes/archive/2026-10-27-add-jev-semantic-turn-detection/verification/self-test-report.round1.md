# 研发自测报告 — 增量记录，未达到完整交付

**状态：PARTIAL / NOT READY FOR INDEPENDENT REVIEW。M1—M5未完成，不申请独立审核，不填写独立PASS或User Gate 2。**

## 运行身份与范围

- 日期：2026-10-21（America/Los_Angeles）；执行者：本次开发Codex。
- 工作区基准HEAD：`2aff076d07599c5352b390edf83106d49e7bb2cb`；未提交的增量源码和测试见下表。用户原有下载脚本、数据集、其他Change和报告未覆盖。
- 环境：仓库`.venv` Python 3.13，锁定Pipecat 1.8.1 / Speechmatics Voice 0.2.8；没有新增依赖。
- Gate 1：D-048；v0.14 SHA-256再次校验为`657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4`，HTML未修改。D-049更新行为契约：Final替换已提交Partial不再判断改义。
- 证据等级：fixture/mock和本地回归；没有外部收费调用、没有客户数据外发，没有真实ASR/Jev/TTS效果证据。

## 已执行结果

| 测试范围 | 生产代码 / 测试 | 结果与边界 |
|---|---|---|
| ASR-01/03部分：范围替换、迟到Final、新尾部、重连代次、跨TD提交 | `src/asr/transcript.py` / `tests/test_td_transcript.py` | 6通过；缺少跨提交词时间明确缺失，不猜字符串；未接正式轮次控制器 |
| ASR-02部分：六模型事件归一化 | `src/asr/turn_events.py` / `tests/test_td_asr_events.py` | 7归一化fixture通过；模型共享协议，不证明实包或全部乱序覆盖 |
| ASR-02正式适配路径 | `src/asr/factory.py` / 同测试文件 | 2通过；真实注册工厂Flux Update产生Interim及原始result；Speechmatics保留metadata/fragments并启用include_results；ASRService提供归一化边界 |
| TIME-01/02/03部分及JEV-01 | `src/pipeline/turn_detection.py` / `tests/test_td_timing.py` | 12通过；纯时钟核心，未接Silero、实际音频/媒体健康状态、框架聚合器或调度 |
| JEV-02部分：HTTP错误、预算、响应验证 | `src/pipeline/jev.py` / `tests/test_td_jev.py` | 8通过；MockTransport、无网络，不证明真实连通、限流、延迟或语义效果；忙碌拒绝/超时取消路径仍需完整测试 |
| REV-01/02/03部分，按D-049 | `src/pipeline/response_revision.py` / `tests/test_td_response_revision.py` | 5通过；回答身份及一次重答、不重复操作的核心状态测试；未证明真实LLM/TTS/客户端缓冲取消和上下文替换 |
| NUM-01/03/04部分 | `src/pipeline/identifier.py` / `tests/test_td_identifier.py` | 16通过；纯编号格式、混合拒绝、来源/修订/代次、共享收集状态；未注册LLM工具，未接关键词、业务WPM、超时提醒及播放 |

新增56项测试均先观察缺失目标行为的红灯，再实现转绿。首次红灯输出在[本轮证据目录](development-20261021/)。后续修复了来源修订校验、Final窗口不重启、Soniox稳定token与新尾部共存，以及格式/类型检查问题。

## 实际命令

- `.venv/bin/python -m pytest -q`：**430 passed，3项依赖弃用警告，30.47秒**；[完整输出](development-20261021/pytest.txt)。
- `.venv/bin/python -m pytest tests/test_td_*.py tests/test_asr_factory.py -q`：**70 passed，2项依赖弃用警告，1.95秒**；[定向输出](development-20261021/targeted.txt)。此命令在最终类型修正后执行。
- `.venv/bin/ruff check`：本轮7份生产源码及6份测试文件检查通过；[输出](development-20261021/ruff.txt)。
- `.venv/bin/mypy`：本轮7份生产源码通过；[输出](development-20261021/mypy.txt)。
- `git diff --check`：退出0；没有提交或推送。
- `python3 scripts/quality/verify_change.py add-jev-semantic-turn-detection`：初始0错误/14警告；本轮最终记录见[门禁输出](development-20261021/change-gate.txt)。结构门禁不证明功能实现。

## 未完成、问题和未验证

1. M1仍未完成：self_developed配置/Catalog/会话快照与正式UI尚未接入；缺可靠时间范围的文本保留、运行时重连/音频位置桥接及厂商跨TD提交仍须完善。范围归一化器目前只诊断缺失，不得启用后静默丢转写。
2. 核心状态模块尚未全部接到正式Pipeline；Silero、唯一提交聚合器、异步Jev与独立看门狗、实际Final替换/取消与上下文均未完成集成。
3. M3工具注册、完整编号生命周期、WPM和播放仲裁/实际开播回执未完成；当前局部测试不证明真实工具副作用和音频取消。
4. M4缓存、持久化、Publish校验、真实历史指标、正式页面Checkpoint A/B均未完成。未修改正式UI，没有制作另一个验收页面，没有覆盖冻结基线。
5. M5完整自测未执行。真实六模型/Jev/TTS、实机AEC、目标1核1GB负载、WebSocket/WebRTC全链路未验证；无外部调用授权。本轮不新增服务端AEC。
6. 原交接delivery-status中尚为Open的事项仍未据此关闭。

## 产物与回退边界

- 证据保存在`verification/development-20261021/`；临时红灯输出也仍在`/tmp/jev-*-red.txt`，没有客户数据、录音或数据库，也未加入Git暂存区。测试自己的临时数据库由pytest临时目录管理，本轮未生成业务持久化数据。
- 本轮唯一修改的既有生产文件是`src/asr/factory.py`；其余新增底座未切换现有轮次来源。厂商原生/off定向及全量回归通过，但真实会话未验证。
- 没有发布资源或数据库迁移，无进行中会话/已发布数据回滚操作；如需撤销，审核后只逆转本轮factory增量及新增模块，不能回滚用户原有文件或其他Change。

## 审核状态

**未申请独立审核。** 本文件仅记录真实研发增量；完整实现与M5自测包尚不存在。没有填写独立PASS、Checkpoint C、User Gate 2，也未合并主规格、归档、提交、推送或部署。
