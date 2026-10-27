# 后端独立代码审查（2026-10-26）

范围：当前 r87 工作区的 ASR 来源账本、Final 修订、编号共享状态与工具、TD 时间核心。只读实现，没有真实厂商调用或生产代码修复。以下为离线实际调用生产类的复现，不代表外部厂商实测。总体建议 **BLOCKED**，先修复来源文本问题；时间项需同步消除规格/测试冲突。

## B1 / P1：多个英文来源与词级切片丢失单词边界

- 位置：`src/asr/transcript.py:217,227,272,283`，以及 `src/pipeline/custom_td.py:325` 的同类直接拼接。
- `SourceNormalizer` 对 Nova 保留厂商 `transcript`，词字段来自不带分隔符的 `word`；`TranscriptLedger` 却用空串拼接独立来源及切片后的词。
- 实际离线输入：Nova `start=0,duration=1,is_final=true,transcript=one,words=[one(0,1)]`，再输入 `start=1,duration=1,is_final=true,transcript=two,words=[two(1,2)]`。
- 实际结果：`ledger.view().text == 'onetwo'`；配置词表 `one→1,two→2` 时 `IdentifierVocabulary.normalize(...) is None`。应该仍保留两个英文单词，而现在纯数字口述会被改成混合输入，错走普通 LLM；普通英文的 LLM/Jev 输入也被拼坏。
- 回归要求：同一 TD 包含多个 Nova/Speechmatics 来源、累计厂商 turn 跨提交后保留多个英文词、中文及数字连续输入、Soniox 自带前导空格四类。修复不能对所有 token 简单加空格破坏现有数字/CJK/token 拼接。

## B2 / P1：跨范围 Final 可用不完整词证据生成错误重答文本

- 位置：`src/asr/transcript.py:256-272`；实际消费点 `src/pipeline/custom_td.py:419-449`。
- `view()` 已调用 `words_cover_text` 拒绝不完整词覆盖；`resolve_snapshot()` 没有同样的检查，只要求存在至少一个范围内词。因此可以返回 `final=True,missing_reason=None` 的不完整文本。
- 离线复现：先消费来源 x、0–1000ms、Partial `I agree`；再更新 x、0–2000ms、Final `I do not agree now`，但词时间只有 `I(0,100),agree(400,900),now(1100,1500)`。实际 `resolve_snapshot(original)` 返回 `Iagree`、Final=true。否定被静默丢失，协调器随后会用此结果触发 D-049 重答。来源归一化会过滤缺 start/end 的词，所以这不是不可达的对象构造约束。
- 应保持无法证明该范围的状态，不得用部分词覆盖冒充完整 Final。验证应包括缺词、缺否定词时间、词穿过边界、完整覆盖及同范围无需切片的正常 Final。不要用猜时间或字符串后缀补证据。
- 已追加适配器入口证明：测试直接将Nova形态payload交给生产 `SourceNormalizer`，`do/not`词缺start/end，归一化实际返回一个segment且`missing_reason=None`，剩余词为`I/agree/now`；随后账本错误仍复现。属于本地故障注入证明的容错漏洞，不声称真实厂商曾发送此缺字段组合，也未发送任何外部请求。

## B3 / P1：Final 等待窗口会绕过更新后的语义目标

- 位置：`src/pipeline/turn_detection.py:163-166,203-211`；协调器 `custom_td.py:265-271` 只是调用该状态机，没有补偿。
- 实际复现：`WaitPolicy(600,2500,200,.5,.8)`；静音从0开始，Partial `done` 的语义目标600；poll(600)启动Final等待。随后Partial改成 `actually I also want`，新版本语义目标2000；poll(800)仍返回该新文本的提交，reason=`final_wait_expired`。
- 原因：文本更新清空 `_target_ms`，但 `_final_deadline` 仍存在；`poll()` 只在 deadline 不存在时检查语义目标，连已返回的新2000ms目标也被忽略。
- Delta voice-pipeline `Transcript revision`（23–25行）要求旧判断不得直接提交新文字；现有 `test_final_deadline_does_not_restart_for_latest_partial` 反而锁定了当前行为。另一方面同文件45–47行要求Final窗口到期用最新Partial，存在需要研发整理的口径冲突，不应把现有测试通过当作无问题。
- 建议保持原Final等待预算和2500ms最长上限，但重新满足当前版本有效语义目标；新判断缺失时只能等最长兜底，不能只因旧Final窗口到期提前交新文本。此方式不必无限重启Final等待。若产品本意确实是窗口开始后任何修订都立即沿用旧许可，必须明确解决上述Spec冲突，不能静默更改。

## 独立回归

执行：`.venv/bin/python -m pytest -q tests/test_td_transcript.py tests/test_td_timing.py tests/test_td_identifier.py tests/test_td_identifier_tools.py tests/test_td_tool_scope.py tests/test_td_response_revision.py`

结果：**65 passed / 1 existing dependency deprecation warning / 1.04s**。这些既有用例未捕获 B1/B2；B3 存在锁定旧行为的测试。当前Python3.13；没有验证Python3.11、真实ASR/LLM、物理设备或生产部署。根评审统一登记delivery-status，避免并发覆盖。

永久复现证据：同目录 `backend_repros_20261026.py`，运行 `.venv/bin/python -m pytest -q openspec/changes/add-jev-semantic-turn-detection/verification/stage-review/backend_repros_20261026.py`。当前实际 **3 failed / 1 warning / 0.78s**，分别对应 B1/B2/B3；断言表达应有契约，不修改生产实现。B3须结合上文规格冲突一起解读。该文件是审查证据，未加入默认tests目录。

## 本轮产品确认补记
用户已于2026-10-26选择“按新 Jev 判断继续等，但不超过最长静音上限（推荐）”，记入D-080。上文B3的规格优先级已明确，应按新目标修复，不再作为待用户决定项。
