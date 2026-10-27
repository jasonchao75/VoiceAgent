# r51：正式Sessions异常可见与重试恢复

W3必要UI缺口，未收费、不重启RTC调查、不跑最终全量回归。正式路由/组件接拦截fixture API；没有另造验收页。保留冻结原型，新增仅故障alert，正常布局不变。

根因：loadHistory失败向全局error-banner写入，但Sessions隐藏conversation-panel，提示不可见。现历史区域拥有本地role=alert，成功读取后清除；失败保留旧行，成功空列表移除旧行。未改API/存储/产品规则。

TDD：initial-incomplete-assertion.txt的2通过仅断言内容，没有验证可见性，明确无效修复证据。red.txt补可见断言后1440/390px两例失败。green.txt修复后2通过/1.4秒。node --check frontend/src/main.js通过；截图history-failed/recovered-{1440,390}.png。人工查看390失败态，alert位于列表上方，未藏在其他面板。所有API由测试拦截，无真实Key或外部请求。

复现（frontend目录）：VOICE_AGENT_UI_URL=http://127.0.0.1:5177 VOICE_AGENT_TD_UI_EVIDENCE=../test-results/td-history-recovery npx playwright test tests/ui/td-history-recovery.spec.js --project desktop-chromium。需本地Vite；本轮尝试启动遇5177已占用即退出，复用现有服务，未杀进程。普通sandbox内curl不可达不等于服务停止，实际浏览器运行成功。test-results/playwright保留失败trace/截图且被忽略，不提交。

当前源码2文件增量相对封存阶段输入见delta-from-stage.patch及source-fingerprints.json；原tar未覆盖。未证明真实API异常、完整UI A/B、RTC、厂商修复或手机。无新增产品问题，Q-046及后续费用独立授权仍待决定。
