# 研发自测报告 — 编号链路及成功换代增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 本次推进了第四、第五轮增量；整体M1—M5仍未完成。未申请独立审核/Checkpoint C/User Gate 2，未合并主规格、归档、提交、推送或部署。上一阶段详情见[self-test-report.round4.md](self-test-report.round4.md)。

## 实际实现与证据

| 场景 | 本次结果 | 证据等级/测试 |
|---|---|---|
| 优先规则配置 | 显式关键词、词表、WPM、独立停顿和完整性保护进Bot JSON/SQLite，隐藏草稿保留，Session深拷贝；无数值默认 | fixture/local-real SQLite：test_td_rule_settings.py、test_td_config.py；UI仍未实现 |
| 纯编号/混合分流 | 完整格式校验；纯编号本地收集，混合句整体Jev→原LLM工具。速度不影响收集；单单元/两位不新增门槛 | fixture：test_td_identifier_rules.py、test_td_runtime.py |
| 来源范围共享 | 相邻同源尾段不覆盖，重叠音频组替换，多来源可绑定；Final文字/元数据同时裁剪，跨词边界不猜 | fixture：test_td_identifier_inputs.py、test_td_transcript.py |
| 真实SDK工具纵向链路 | TD→现有聚合器→SDK自动注册/后台工具调度→结果回填→续生成；Final重答用户提交1次/工具副作用1次，纯编号工具0次 | local-real Pipecat，mock外部推理：test_td_identifier_pipeline.py；不证明真实厂商效果 |
| WPM | hello/你好/1234分别1/2/4单元；按完整词时间范围计算，不按token数或音频窗口算；缺证据明确无法计算 | fixture：test_td_identifier_rules.py |
| 未满保护 | 不请求Jev（注入调用计数为0），普通最长等待不绕过；到独立保护只提醒一次，保留编号；后续提问不重交旧数字 | fixture：test_td_runtime.py；实际跟读尚未发出 |
| 当前候选迟到修订 | 已本地处理的同一保护候选变混合句时撤销失效值并重交最新整句；修订到刚满时进入普通TD；用户提交只有1次 | fixture：test_td_runtime.py；已修正参数化用例确实使用不同输入，不把重复执行算分支覆盖 |
| 成功后新采集 | 最终来源证明＋已TD提交才确认纯编号成功；Partial达标/未提交不清空。真实新输入开始才换代，旧代次不能回写 | fixture：test_td_runtime.py |
| 混合新采集 | 旧值保留到受控提交验证成功，才清空换代并写新值；非法值不清空；重复及同输入Final不再次换代 | fixture：test_td_identifier_tools.py；正式Pipeline共用同一状态/入口 |
| 并发工具/结果真实性 | 校验前及投递前都检查；提交/清空或两个替换并发时，回调返回投递时当前编号/位数/代次，被替代结果明确superseded | fixture：test_td_identifier_tools.py；不伪造第二次操作应用 |
| 历史证据 | 操作结果与实际提供给SDK的结果分开记录；来源版本/范围、WPM阈值/缺失原因留痕；10000条上限后保留截断计数标记而非静默丢弃 | fixture/local-real：test_td_history.py及SDK纵向用例；完整历史UI仍未完成 |

## 检查结果

- 最终全量：**519 passed，3项依赖弃用警告，30.63秒**，见[pytest-final.txt](development-20261021-r5/pytest-final.txt)。上一检查点510项通过，原始证据仍在r4。
- ruff src/tests通过；mypy相关43源文件通过；git diff --check通过。见本目录对应日志。
- 真正缺失行为/缺陷先失败再实现的输出在[r4](development-20261021-r4/)和[r5](development-20261021-r5/)。r5的parallel-tools-intermediate是中间失败记录，不能当通过证据；最终以全量结果为准。
- 本次也修正测试夹具导入、可注入decide和参数化接线；夹具错误未当作功能红灯。参数化漏覆盖已登记、披露并修复后复跑。
- 冻结v0.14 SHA-256保持657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4。无前端页面改动；上一轮历史抽屉1440/390px证据在r3，不冒充完整UI A/B。

## 仍未完成 / 未验证

1. **跟读音频未发送。** 当前echo_eligible仅记录echo_not_dispatched。永久缓存、配置指纹、发布版本、故障补合成、串行输出和客户端任务开播/停止回执仍未接齐，不能声称听到或停止。
2. 跨新轮次/提醒的旧编号ASR自动修订及补读、完整清空停播仍未闭环。本轮只覆盖当前保护候选的已消费范围回流；成功换代基本路径不替代这些场景。
3. 固定提醒走现有TTSSpeak入口，但完整播放仲裁和逐轮历史展示仍未接齐。普通提醒的完整已知文本更新关键词上下文，不代表实际播放证明。
4. 正式配置页、Jev页、词表音频、历史详情及Checkpoint A/B未完成。编号后台可配置不等于正式页面可用。
5. 未知范围安全消费、真实六模型时间戳/重连、实际LLM/TTS残留取消、WebSocket/WebRTC完整链路、物理双讲AEC及1核1GB性能未验证；无服务端AEC新增。
6. 真实ASR/Jev/TTS没有本批授权，均未运行；语义效果、P95延迟、费用和上线参数校准未证明。

## 工作区、授权与交接

HEAD仍为2aff076d07599c5352b390edf83106d49e7bb2cb。D-048/049有效，开放产品问题0项。用户下载脚本、语料、其他Change和报告未覆盖；没有改真实业务库、读取/打印凭证、外发客户数据或收费调用。

证据目录development-20261021-r4/、r5/；临时/tmp/jev-r4-*.txt、/tmp/jev-r5-*.txt保留追溯，未暂存提交。测试库仅pytest临时目录；无新录音/合成音频/服务进程。完整实现与M5自测包未就绪，继续开发，不提交独立审核。
