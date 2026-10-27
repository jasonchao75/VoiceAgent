最新r85：[六模型真实基本范围与实现证据收敛](development-20261025-r85/README.md)。六单例均通过，8项实现任务按JUnit/源hash审计补勾；真实多场景/重连、RTC源端/采用及设备仍未闭合，非最终独立验收。下文为逐轮历史。

当前r84：D075/D076已完成，Deepgram三模型新数字素材实际范围事件18/18/7均通过；共3连接，原上限分别US$0.02，不复用。详情[实际结果](development-20261025-r84/README.md)。其余三厂商、重连/质量/全链取消未验证。下文历史状态按日期追溯。

# 当前授权与准备状态 r83（2026-10-25）

现有收费授权全部已消费，不重放。D-053两条Jev成功；D-062 Flux英文continuation来源范围通过、digits边界失败已离线修复；D-065单例one真实24kHz单声道PCM16成功。其余六模型/修订重连/完整TTS取消仍缺证据，不采用下文旧“全未测”或“等待授权”快照。

原三段/tmp素材已不存在，旧计划不可直接执行。新的离线合成digits-ready.wav已保存于test-results/td-vendor-inputs/20261024，5.1675秒、16kHz单声道PCM16，SHA-256 a93499196b16dd1e9307ba97bedd24d246dedf995755e05bc9f20e382139966e；**未授权发送**。下一批必须新冻结精确数据/模型/次数/费用/停止清单与脚本守卫，再单独申请。非空环境Key也不等于鉴权成功或费用授权。本轮无外部调用。

---

# R2真实厂商联调授权清单草案（2026-10-22）

> r47最新实际结果：新D-062授权执行2个Flux英文连接，continuation完整范围通过、digits第7事件0.1微秒窗口/词端点差失败即停，余7未执行；新D-063首条one失败即停，SDK尾空格与精确文本守卫冲突已离线复现/修复，真实未重测。新批次授权已消耗，下面r44“等待回复”已过时，仅留追溯。

> 当前执行状态（2026-10-23 r44）：D-053 Jev两请求已成功；D-055/057/059各执行Flux首连接后停止，D-058 TTS首条超时后停止。所有旧批次禁止重放；下方“未授权/未执行”是早期准备快照。r43已提出新的Deepgram ASR9连接≤US$0.10和TTS3请求≤US$0.10独立授权，尚无答复，不执行。实际结果见当前self-test-report及各安全日志。

状态：**PREPARING / NOT AUTHORIZED**。D-053仅两次Jev请求，已用完；D-054只授权本地RTC验证。以下金额是拟申请上限，尚未得到授权，也不代表未核验计费规则已能技术保证。费用/凭证/脚本守卫准备齐再提交精确批次问题，不能先调再补授权。

## 数据清单（已就绪）

本机离线Albert合成三段虚构英文语音，16kHz/PCM16/单声道，总18.405375秒；不含人声录音、客户资料或生产对话。逐字文本、路径、时长、SHA-256见[vendor-synthetic-data.json](vendor-synthetic-data.json)。只可读取*-ready.wav；初次沙箱生成的三个AIFF均0采样，不可发送。重新生成后hash变化必须重审批次。素材在/tmp/voiceagent-jev-r39-synthetic/保留，未提交。

## 分批范围与停止条件

| 批次 | 接收方/固定目标 | 数据/最多调用 | 拟上限 | 执行前仍缺 |
|---|---|---|---|---|
| ASR-A | Deepgram flux-general-en、flux-general-multi、nova-3；Speechmatics enhanced；Soniox stt-rt-v5；AssemblyAI universal-3-5-pro | 每模型三段各一次，最多18条流；按实时速度发送，三段×六模型实际语音≤110.433秒；每连接总墙钟≤30秒，无重试/重连 | 全批US$1.00，未授权 | 六模型当前费率/最小计费/会话与token计费核算、凭证可用性、全批硬预算守卫及实际抓包脱敏脚本 |
| ASR-B | 同上，仅兼容通过的模型 | 另列精确断开点/音频后半段及两次连接预算，不借ASR-A授权重连 | 未定，不执行 | 先取得A结果；不能提前扩大调用/数据 |
| TTS-A | 正式Deepgram Flux TTS，候选voice flux-alexis-en | 固定“one”、“two”、“Your number has been cleared.”，各一次，3次；仅合成，不自动ASR回听 | US$0.10，未授权 | 账号计费/语音可用性及带取消验证的精确脚本/连接总时长；不自动选另一个voice |
| TTS-B | 正式ElevenLabs | 同上三条文本，候选模型/voice须按正式Bot和可用权限定案；当前0次 | 未定，不执行 | 精确模型、voice、档位计费和权限，不以自动发现调用扩大范围 |
| JEV-B | TypeSafe Jev，实际版本必须留存 | 后续复用真实ASR结果必须先形成新文本白名单/hash/次数；当前0次 | 未定，不执行 | A输出白名单；不能借D-053重复调用或把所有ASR内容自动送Jev |

通用停止：鉴权/权限、限流、模型不可用、TLS/超时、响应无可验证身份/格式、计费不明或预计达上限立即停止全批；无自动重试/切模型/换厂商。连接超时5秒、单连接总30秒、完成后立即关闭；任何失败后的重跑单独授权。只记录允许的转写/时间/事件和实际usage，禁止凭证/原始鉴权头入日志。英语合成数据仅验证兼容和时间字段，不能证明阿语/真人语速/噪声准确率。

## 只读官方价格核验及未决工程核算

- [Deepgram](https://deepgram.com/pricing)：Flux英文$0.0065/min，多语$0.0078/min；Nova-3单语$0.0048/min、多语$0.0058/min；Flux TTS $0.045/1k字符。执行时选定语言与附加项，核验账号/最低计费，不默认所有价格都适用。
- [Soniox](https://soniox.com/pricing)：实际按token；实时音频输入$2/M、文本输入/输出$4/M，约$0.12/hr只作估算，不把小时估算当硬费用上限。
- [Speechmatics计算页](https://www.speechmatics.com/pricing/calculator)：页面并列批处理/实时选项，静态抓取Enhanced $0.75/hr不唯一证明本批实时档位；不得套价，需核实。不能主动开启训练折扣/日志。
- [AssemblyAI](https://www.assemblyai.com/pricing)：当前实时价格页显示3.6 Pro $0.45/hr，不能套到本Change锁定3.5 Pro；目标3.5的可用性与计费需核实，不自动升级模型。

没有执行上述任何厂商调用。若某项无法取得明确上限/权限，保持该批阻塞，继续离线R3，不猜测价格或请求成功。

## r40执行准备更新

三份数据/hash未变。Deepgram ASR已拆为可单独执行的固定9连接批次，精确计划见deepgram-asr-batch-plan.json，脚本scripts/evaluation/probe_td_compatibility.py；每例连接/握手有界、SDK自动重连提前拒绝，整个批次首次失败即停，独占日志防重放。该批US$0.10授权问题已发出，未收到回复，不执行。

Deepgram TTS精确计划见deepgram-tts-batch-plan.json，3条35字符、固定Alexis、24kHz单声道PCM16，单独的连接和Speak文本次数守卫；估算US$0.001575，拟上限US$0.10，尚未申请/取得该批授权。独立运行发现并修复TTS导入循环，不能只靠完整pytest导入缓存证明可用。

公开价格进一步核验见development-20261022-r40/vendor-pricing-verification.md：Speechmatics实时无演示折扣Enhanced为$0.80/hr，AssemblyAI固定3.5实时基础价$0.45/hr已有官方Changelog依据；其余脚本/批次/权限和Soniox token预算仍需完成，不据此称六模型兼容通过。

## r41实际结果（2026-10-23）

D-055已授权原Deepgram ASR批次。实际只执行1条Flux英文/continuation连接，转写到达但所有事件报告invalid_source_audio_evidence、无有效范围，约12.02秒后按首例失败停止；未执行其余8条、未重试。公开单价30秒预算上界US$0.00325，非实际账单，厂商usage未给出。初版探针未在首个坏事件立即停输入且缺白名单原始时间，已离线修复；无法从该日志唯一定位实际拒绝原因。原授权已消耗，不借余下次数诊断。

新单连接诊断计划deepgram-asr-range-diagnostic-plan.json仅同一continuation文件/Flux英文，最多1连接30秒、上限US$0.02，首个范围缺口即时停并仅留安全时间字段；尚未授权/执行。独立TTS固定批次仍未授权。
