# r45：缓存恢复与正式历史闭环

范围为CACHE-02/HISTORY-01的一条正式WS纵向场景，不替代RTC发布入口。应用tests/ui/td_local_app.py scenario=identifier_cache_repair，离线ASR/LLM/TTS替身；外部网络连接被拒。实际资源缓存/发布API/SDK流水线/浏览器Worklet/历史SQLite正常使用。旧版本读故障仅由fixture抛ValueError注入，不删除文件。

## 结果

- cache-history-red.txt：补合成/实际清空组合已过，正式历史缺Runtime audio recovery；目标行为红灯。
- cache-history-final.txt：1 passed 10.2秒。一次实际SDK补合成、46.34ms本地资源耗时，Worklet实际开播与清空停止；中英恢复标记/耗时/指纹保存，原始值不翻译。ws-identifier-combination.json为脱敏实际事件和回执。
- history-labels-red.txt：中文标题原始英文回落，明确断言失败；修复后history-review-final.txt：1440/390各352字段原值保持、回落标题0、浮层无横溢。history-review.mjs可只读重跑（依赖本机5177现有fixture历史，不启动会话）。中英截图已保存并人工检查。
- frontend-build-final.txt PASS；frontend-unit.txt 5 passed；ruff.txt PASS。

## 失败准备记录与范围

cache-runtime-network.txt初次422为新测试漏Publish请求体；cache-runtime-red.txt未合成是瞬时故障重读已恢复，不是假报补合成。cache-history-green.txt曾因父级嵌套记录locator计数3而失败，限定实际事件后通过。history-screenshots.txt/history-labels-final.txt是只读脚本异步加载/语言切换后旧locator超时，保留而不宣称成功。最终只读结果以history-review-final.txt为准。

该Bot已先发布，但正式Web测试会话读取草稿，resource_version=null，UI如实显示Not available。仅证明草稿WS恢复；固定发布快照SDK测试不可拼接为公开RTC端到端证据。R1仍阻塞，不批准或替换正式播放器。没有付费调用，所有旧授权不重放。

## 命令

后端：PYTHONPATH=. .venv/bin/python tests/ui/td_local_app.py --data-dir /tmp/voiceagent-td-r45-cache-repair --port 8769 --ui-origin http://127.0.0.1:5177 --scenario identifier_cache_repair。

前端：VOICE_AGENT_UI_URL=http://127.0.0.1:5177 VOICE_AGENT_TD_LOCAL_RUNTIME=1 VOICE_AGENT_TD_LOCAL_SCENARIO=identifier_cache_repair VOICE_AGENT_TD_UI_EVIDENCE=../openspec/changes/add-jev-semantic-turn-detection/verification/development-20261023-r45 npx playwright test tests/ui/td-runtime.spec.js --project=desktop-chromium --grep 'formal WS identifier echo'。

只读审阅：node openspec/changes/add-jev-semantic-turn-detection/verification/development-20261023-r45/history-review.mjs。临时数据/tmp/voiceagent-td-r45-cache-repair保留作证，不提交；前端编译和测试缓存仍忽略。
