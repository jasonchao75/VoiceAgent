# r50：复验最小范围、失败归因与授权拒绝

目的仅为阶段报告W2：原因收敛后不再用整批收费重跑碰运气，并防止旧已消费授权被复用。没有真实调用、没有读取真实Key、没有RTC调查/架构变化、没有完整业务回归。核心ASR修复是r49；本轮只改两个探针及其安全/协议回归。

## 必要修复

原公共verify_authorization只核confirmed/hash/次数，靠本地独占日志防重放；复制已消费记录但没有日志时会允许通过。consumed-grant-red.txt明确DID NOT RAISE。现要求execution_status=authorized_not_started，在读取Key前拒绝completed/stopped/running/缺状态；原独占日志保留，不能因余量未用完重试。该证明限于明确已消费的记录，不宣称跨所有主机的分布式扣费锁。

TTS新增固定白名单failure_stage：connection/request_guard/transport_send/provider_control_error/deadline/unit_pipeline_or_artifact；scope_rejection只取固定代码，拒绝文本不落结果。speak_attempts与completed_speak_sends区分“尝试”“send返回”，均不当作厂商收到或确定扣费；旧真实日志不追加这些字段来伪造根因。首个connection_failure保留，不被后续预算拒绝覆盖。

## 最小清单（未申请、未授权、未执行）

- ../deepgram-asr-digits-confirmation-plan.json：独立batch，仅固定digits WAV5.1675秒、3秒静音、Flux英文、最多1连接≤30秒，拟上限US$0.02，首范围/协议/鉴权/超时错误停，无重试/重连，无其他服务。数据hash沿原冻结值；不重跑已通过continuation。
- ../deepgram-tts-one-confirmation-plan.json：独立batch，仅one3字符、固定flux-alexis-en、24kHz单声道PCM16、最多1请求/15秒合成时限，拟上限US$0.02；首异常停，不换音色/重试，无其他服务。

两计划都只作准备，不是费用请求。公开费率仍标2026-10-22历史参考，申请前需核对，不能当当前实际账单。新增batch/hash/次数/上限不同，旧D-062/063等不能匹配，更因已消费而拒绝。已授权原9连接/3文本计划结构和hash完全未改（plan-check.json）。

## 实际离线验证

minimal-scope-guard-green.txt：22 passed，3依赖警告，5.80秒。覆盖本轮授权拒绝、最小scope互斥/不扩量及同实际SDK假socket：被改文本只记录安全请求守卫阶段，不发送该Speak；精确原文正常通过。没有为数量新增普通TD场景。初次ruff行长失败保留，ruff-final.txt通过；types.txt为实际Python3.13两脚本通过。最小CLI dry run只做计划/文件hash核验，不读Key/联网：

.venv/bin/python scripts/evaluation/probe_td_compatibility.py --repair-confirmation
.venv/bin/python scripts/evaluation/probe_td_tts.py --single-unit-confirmation

相关测试命令：.venv/bin/pytest tests/test_td_vendor_probe.py tests/test_td_tts_vendor_probe.py -q。没有使用--execute。gate-before.txt因新发现尚未标披露而非零，披露后gate-before-disclosed.txt恢复通过；不把初次失败改写为通过。

## 评审增量与下一步

r48阶段输入副本不覆盖；本轮4文件相对该副本的patch及SHA单列。评审本轮时同时使用r49增量，因为新ASR留证读取SourceSegment.sample_rate。只读审查和必要离线复现不授权费用；下一段需阶段意见、价格核对及独立最小授权后才执行。RTC Q-046仍Open，最终整体交付/独立PASS/C/Gate2仍未完成。
