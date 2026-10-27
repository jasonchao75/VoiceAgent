# G2-02 编号流程独立复验（2026-10-26）

结论：本轮限定本地检查通过，未发现新增确认实现缺陷。未修改生产代码。用户未进行本项最终确认，整体 Gate2 保持未通过。

## 分层结果
| 范围 | 输入与结果 | 证据层 |
|---|---|---|
| 累计 | 目标6位，123→12345→123456，不重不漏 | 生产 normalizer/coordinator/collection；虚拟音频时间 |
| 未满位 | 最后人声6000ms，13999ms无提醒、14000ms一次；推进22000ms仍一次，保留12345 | 真实规则与TTSSpeakFrame事件；未播放真实TTS |
| 满位 | 提醒后续说6，123456；正常提交一次，无新增未满位提醒 | 生产协调器/提交状态；Jev无外部请求 |
| 超位 | 1234567完整保留；停顿349ms无提醒、350ms提醒一次；继续静音不重复；普通提交0次 | 生产协调器/输出事件 |
| 清空重收 | 清空成功后旧值为空，代次更新；再说89只保留89 | 生产清空工具状态及协调器 |
| 浏览器累计与停播 | 1→12；清空一次、值空；首个跟读实际渲染147072样本后stopped，第二个旧跟读没有started；清空后回答完成，回执均204 | 正式根路由/真实HTTP、WS、SQLite、AudioWorklet；ASR/LLM/TTS和麦克风输入为测试替身 |

## 执行与复现
- Python3.11：test_td_identifier、identifier_rules、identifier_inputs、identifier_tools、identifier_output、identifier_pipeline、td_runtime、td_playback、td_serial_output、echo_runtime，共117 passed，4项依赖警告，1.46s。
- 独立6位样例：在仓库根目录执行 `PYTHONPATH=. /tmp/voiceagent-r91-py311/bin/python openspec/changes/add-jev-semantic-turn-detection/verification/gate2-intake/identifier/six_digit_probe.py`；结果six-digit-results.json。该脚本使用生产处理器，替换输出传输并显式推进媒体时间，不声称经过浏览器播放。
- 正式浏览器：18998端口运行 `tests.ui.td_local_app --scenario identifier`，独立目录 `/tmp/voiceagent-gate2-identifier-20261026`，只允许回环网络；VOICE_AGENT_TD_LOCAL_RUNTIME=1、VOICE_AGENT_TD_LOCAL_SCENARIO=identifier，以 desktop-chromium 运行td-runtime.spec.js中 `formal WS identifier echo survives`：1 passed /10.2s。
- 浏览器留证：ws-identifier-combination.json，包含实际历史事件及播放回执。测试音频为本地合成固定PCM，不调用厂商。临时报告在test-results/playwright-report；临时数据库/缓存/密钥在上述/tmp目录，不提交。验证服务结束后停止；18997配置页服务不受影响。

## 限制与后续
满位、超位及未满位提醒尚未跑正式浏览器播放组合，真实TTS听感也未验证，已登记G2-02-REAL-REMINDER-PLAYBACK。真实ASR识别、真实LLM工具选择、手机弱网及声学AEC均不在本轮证据内。不得把事件生成等同用户已经听到提醒。外部调用0，新增费用0。用户验收待确认；完整C/Gate2不自动通过。
