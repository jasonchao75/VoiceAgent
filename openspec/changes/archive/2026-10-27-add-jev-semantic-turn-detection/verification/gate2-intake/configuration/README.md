# G2-01 配置页独立复验 — 2026-10-26

结论：本轮定向配置检查通过，用户已确认页面布局和操作符合预期（D-087）；不代表整个 Checkpoint C 或 User Gate2 通过。未发现新增确认缺陷，未修改生产实现。

## 环境与证据边界
- 当前正式前端重新执行 npm run build 成功，使用正式路由、组件及真实本地 API/SQLite。
- tests.ui.td_local_app 仅监听 127.0.0.1:18997，使用 /tmp/voiceagent-gate2-config-20261026；阻断非回环连接，语音厂商为替身。本轮未合成音频、未开始通话、外部调用 0。
- 六个定向 Playwright 用例：6 passed / 3.9s。覆盖保存过程中继续编辑、失败保留草稿并重试、切换机器人后的迟到错误隔离、390px 可操作性与无横向溢出、中英文切换不修改用户配置、默认中文。
- 失败状态由测试拦截故意注入；成功重试、读取与保存经真实本地 API，不将故障注入误称真实服务故障。
- 人工浏览器复验：关闭收集后相关字段禁用，恢复开关后值保留；将最短静音从600改650并保存；刷新后再次停止自己启动的服务进程，以同一数据目录重启，正式页面仍为650、收集开关开启、显示已保存。
- 截图：after-restart.png（用户验收页面）；formal-rules-390.png（窄屏）。自动化临时报告在 test-results/playwright-report；测试数据库和临时密钥保留于上述 /tmp 目录供当前验收，不提交。

## 复现命令
```sh
VOICE_AGENT_UI_URL=http://127.0.0.1:18997 VOICE_AGENT_TD_LOCAL_RUNTIME=1 VOICE_AGENT_TD_UI_EVIDENCE=../openspec/changes/add-jev-semantic-turn-detection/verification/gate2-intake/configuration npx playwright test tests/ui/td-runtime.spec.js --project=desktop-chromium --retries=0 --grep 'failed TD save|deleting a vocabulary|late save failure|390px|formal language|defaults to Chinese'
```

## 未验证与下一步
本次未重测缓存合成/发布、完整配置矩阵、真实 Jev/LLM 工具效果、手机/弱网/声学 AEC/完整真实链路。既有开放项继续有效，不视为风险接受或范围排除。用户先看配置页入口和三个配置标签的操作是否符合预期；之后继续编号行为、修订和历史联合验收。

## 用户分项确认
2026-10-26，用户原话：“符合预期”。仅确认本配置页分项；下一步G2-02编号行为。整体Gate2仍未通过。
