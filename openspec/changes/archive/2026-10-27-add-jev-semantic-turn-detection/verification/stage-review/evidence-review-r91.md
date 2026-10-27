# r91 新证据独立只读核查（2026-10-26）

**限定结论：现有Python3.11兼容与D-081单批ASR证据相符，未发现新增确认缺陷。全产品仍INSUFFICIENT EVIDENCE，不签完整Checkpoint C、全Change PASS或User Gate 2。**

本次按change-verifier只读核对记录、输入/请求hash、JUnit及原始安全事件；未修改实现/测试/基线，未调用API、厂商或重跑任何测试/浏览器。当前105个src/frontend生产文件与r89基包+r90增量源hash一致。

## Python3.11实际证据

- 隔离环境`/tmp/voiceagent-r91-py311/pyvenv.cfg`实际标明Python3.11.15、独立venv、无system-site-packages；原3.13环境未被作为3.11冒用。
- `voiceagent-r91-py311-junit.xml`独立解析得到**756个用例，全部无failure/error/skipped**；文本记录756 passed、9项依赖弃用警告、67.20秒。
- `voiceagent-r91-pip-check.txt`显示No broken requirements found；用户pip缓存权限警告只说明缓存禁用，没有被伪报安装失败。`voiceagent-r91-py311-mypy.txt`显示目标检查79源通过，已安装版本在freeze清单。
- 支持关闭旧R12/R79/R87的**目标3.11缺证据/依赖解析限制**：当前有真正目标解释器独立结果。旧3.13环境下默认3.11类型目标的失败记录仍保留，不把新环境成功说成旧失败从未发生。

这证明目标解释器软件兼容，不证明Linux1核1GB容量、手机/声学媒体或所有操作系统兼容。本评审仅核已有日志和环境配置，没有执行解释器/pytest/mypy。

## D-081授权、数据与实际结果

- D-081有可定位用户回复来源`call_2015902983f5481a881e2a20a25fe1d4`与明确原话“授权本批（上限US$0.02）”。范围限api.deepgram.com / flux-general-en，虚构否定续说音频5.8576875秒+3秒静音，最多1连接≤30秒，首错/范围缺口停止，无重试/其他厂商/TD/Jev/LLM/TTS。
- 独立重算冻结请求SHA-256与plan、delivery-status grant及实际jsonl claim一致：`ec8070080abcd19bf988b079055ce91c07c857c2e21b46d917baf3209a5836ac`。plan中的not_authorized是申请冻结快照，当前D-081/manifest为confirmed/completed，**不能重放**；未为改该字段而改变已授权hash。
- 输入实际hash匹配`f4dafd141773d42683c84fa7b938b68615e7f7493e9cad1da29d99c49f7de4b9`；16kHz/单声道/PCM16/93723帧（5.8576875秒）与冻结数据一致。段间12800样本=0.8秒。生成rate150与段界不是实测WPM或人工词边界真值。
- 安全原始jsonl包含一次claim、一次status=ok结果，**1连接、11737.98ms、26转写帧（25 Partial/1 Final）**。全部missing_reason为空且有归一化段；所有输出范围在实际音频+静音的8857.6875ms内。
- 实际第2→3帧Partial为“please do not test”→“please do not cancel my”，是可观察词汇修订；Final保留not及后续改时间句。另两次标点修订单列，没有混作实质意图变化。vendor-result-summary与原始事件相符。
- 实际费用未知；US$0.00385是按30秒包络的保守公开价估算，US$0.02是本批预算，不是已验证厂商账号硬扣费上限。未将估算当账单。

本批是**external-real ASR适配/SDK及生产归一化**，未经过TD提交/Final取消重答、Jev竞争、LLM工具或TTS播放。不能用它关闭这些整链、多语、真实重连或WPM效果项，也不能从一次英语样本推导识别质量通过。

## 先前失败与边界

空PCM在冻结前校验被阻止，重新获得本机语音服务权限生成有效输入后才冻结；已有probe在读取Key/建连前验证数据hash/格式/样本，实际本批claim与有效hash相符。不把本机say退出0当有效音频或真实厂商成功。

授权记录首次缺展示cost_ceiling被门禁拦住，补齐后才执行；没有扩大用户数据、次数、厂商或费用。执行器仅将冻结计划交现有守卫，并在授权检查后登记started_no_replay；当前completed不可复用。首次拦截记录/原失败保留，未声称所有准备步骤一次成功。

已存最终门禁0 errors/36 warnings为结构结果；本次不重复门禁或其他行为测试。仍未验证：Linux1核1GB、手机/Safari/VoiceOver、UDP弱网、物理AEC/双讲、跨连接可靠时钟、配对新增延迟，以及真实全模型多语/WPM/续说竞争/LLM工具/TTS取消。没有新增产品决定，本报告不授权任何下一批调用。
