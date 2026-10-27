# 研发自测报告 — 第二轮增量，整体仍未完成

**状态：IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** M1-4已完成，其余里程碑仍有未完成项；没有独立审核PASS、User Gate 2或完整M5自测通过声明。上一轮详情保留于[self-test-report.round1.md](self-test-report.round1.md)。

## 工作区和授权

- 日期：2026-10-21，America/Los_Angeles；基准HEAD仍为`2aff076d07599c5352b390edf83106d49e7bb2cb`，没有提交/推送/部署。
- D-048冻结原型未修改；D-049有效：同范围当前Partial提交后首个Final直接替换，不判断语义。
- 没有真实ASR/Jev/TTS收费调用，也没有外发客户数据。HTTP测试用MockTransport；真实Silero测试仅使用本地生成的100ms静音。
- 用户原有下载脚本、语料、其他Change和报告保留。没有修改真实.env、业务数据库或部署配置；新增SQLite结构仅在测试临时目录验证。

## 这次实际接通的路径

显式配置和Jev凭证→正式Session快照→音频前置Silero→厂商ASR→原始事件/连接代次/范围缓存→异步Jev及独立音频时钟→现有用户聚合器专用子类→现有LLM/TTS。后台连接代次、厂商端点隔离、Jev失败及TD事件已接入；不代表真实厂商和完整编号路径验证通过。

## Spec→测试结果

| ID | 实际测试 | 证据等级和结果 |
|---|---|---|
| PRODUCT-01部分/M1-1 | tests/test_td_config.py、test_td_credentials.py、test_config.py、test_bots.py | fixture/local-real：六模型来源、原生/off限制、显式参数、不可变快照、后台草稿重启、独立加密和地址绑定通过；UI未完成 |
| ASR-01/02/03部分 | tests/test_td_asr_events.py、test_td_transcript.py、test_asr_factory.py | fixture：Flux Update真实工厂路径、Speechmatics metadata/fragments（含null词详情）、范围替换、token稳定/尾部及跨提交通过；未知范围和真实重连未闭环 |
| M1-4/TIME-01/02 | tests/test_td_authority.py、test_td_runtime.py | local-real Pipecat：实际Worker/聚合器、厂商metadata/EOT不能提交、最长截止只有一次context；修复SystemFrame抢先竞态 |
| JEV-01/02、TIME-03部分 | tests/test_td_jev.py、test_td_timing.py、test_td_runtime.py | mock/fixture：完整概率、无效分布、HTTP失败、预算、慢请求、异常安全兜底通过；真实延迟/语义效果未测 |
| REV-01/02部分 | tests/test_td_response_revision.py、test_td_runtime.py | fixture/local-real Pipecat：同轮Final取消/上下文替换及第二次请求、重复不再请求、总用户提交1通过；真实LLM/TTS残留与工具副作用未通过完整验证 |
| AUDIO-01部分/M2-1 | test_bundled_silero_real_silence_and_pcm_validation | local-real：实际ONNX加载、静音时间推进、8k输入拒绝通过；未测真实说话/噪声/双讲 |
| HISTORY-01部分 | tests/test_td_history.py、test_capture.py、test_history.py | local-real：TD事件随实际历史事务落SQLite且重启读取；Partial提交不伪造Final/时延0，LLM首token仍采集 |
| Pipeline普通模式回归 | tests/test_pipeline.py | fixture：正式编排确实前置VAD、后置唯一TD、用专用聚合器，关闭HTTP资源，保留开场；native/chat原顺序回归通过 |

新增配置/凭证/运行时/历史缺失行为的红灯输出及后续结果在[本轮证据](development-20261021-r2/)。真实Worker测试先发现提交丢失（Timeout），修复后转绿；该失败已作为工程缺陷登记并关闭。另补了候选/提交历史轮次ID一致性红绿回归，修复后来源修订也逐条留痕。

## 实际检查

- `.venv/bin/python -m pytest -q`：**454 passed，3项依赖弃用警告，31.00秒**，见[pytest.txt](development-20261021-r2/pytest.txt)。包含最终chat凭证兼容及候选/提交历史轮次一致性回归。
- `.venv/bin/ruff check src tests`：通过；`.venv/bin/mypy src/asr src/pipeline src/session.py src/bots src/history src/api.py src/publication.py`：相关32个源文件通过。最终修订后复查见证据目录。
- `npm --prefix frontend run build`：通过；只验证来源文案调整可构建，不代表UI Checkpoint A/B完成。
- `git diff --check`：通过；Change最终门禁结果见[change-gate.txt](development-20261021-r2/change-gate.txt)。结构PASS不代表功能完整。

## 剩余问题和未验证

1. **已知工具隔离缺陷**：现有set_speech_speed尚未绑定原回答和输入身份，Final重答可能重复执行成功操作。需与编号工具一起实现响应作用域、成功操作幂等和旧代次拒绝；M2-5未完成。
2. 编号LLM工具注册、关键词/WPM/提醒、串行播放/回执、音频缓存/发布绑定尚未完成。当前编号状态单测不能替代这些正式链路。
3. 正式配置UI、Jev页、音频试听、历史TD展示及Checkpoint A/B尚未完成。后端已支持设置，页面当前只有来源选项和说明，不能据此声明可用配置入口。
4. 未知音频范围转写保留在诊断证据中，但可靠切分/消费仍未闭环。新连接frame与fixture不证明真实SDK重连顺序、无遗漏或所有语言兼容。
5. 真实LLM/TTS取消和客户端残留音频尚未验证；实际上下文重答通过不等于用户端音频已停止。
6. Jev/TTS/六模型真实探针、耳机/扬声器双讲AEC、目标1核1GB负载及WebSocket/WebRTC完整链路均未测；不新增服务端AEC。数值默认/调度阈值仍待校准和确认。

## 文件和回退

- 本轮证据目录：`verification/development-20261021-r2/`；临时输出仍在`/tmp/jev-*.txt`，保留以便追溯，未暂存提交。
- `frontend/dist/`是本地构建产物，已确认Git忽略。没有生成客户录音、业务测试数据库或外部合成音频。测试SQLite位于pytest临时目录。
- 代码未部署。对已有数据库仅设计了可重复执行的加列/建表；未在用户真实库运行，也没有破坏性数据迁移。整体功能完成前不运行真实库验证。
- 如撤销，应只逆转本轮代码增量；新增字段/事件表保持兼容，不删除数据、不逆转用户下载脚本或其他Change。进行中会话/已发布资源的完整回退测试仍属于M5。

## 审核状态

**未申请独立审核。** 继续M1剩余范围/设置UI及M2/M3响应与工具隔离，再推进播放、缓存和正式UI A/B；完整自测包就绪后才交评审Codex。
