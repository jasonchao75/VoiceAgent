# r89 UI 独立复审（2026-10-26）

结论：原“完整性收集关闭仍可编辑”已修复；本次发现一项P2视觉基线偏差，尚不能签UI完整Checkpoint C。未修改生产代码、原型或用户Gate状态，没有外部调用。

## 原修复复验

`frontend/src/td-settings.js:91–96`已统一处理总规则与完整性开关；实际正式根路由Chromium 1440及390px均通过加载禁用、重新开启、保存16位配置、关闭保存null、刷新仍禁用。原问题可关闭，不能继续当未修复。

## 新确认P2：词表列标题丢失冻结样式

`frontend/src/td-settings.css:43`的`#vocabulary .vocab-head`只含grid-template-columns和gap，缺少冻结原型的display:grid、10px字号、muted颜色及14px上边距。正式页面三个标题在16px普通行内布局中挤成一串，没有对齐识别词/跟读内容/音频列。冻结原型相同DOM有独立三列对齐。

实际计算样式（同1440px视口）：

| 属性 | 正式 | 冻结 |
|---|---|---|
| display | block | grid |
| font-size | 16px | 10px |
| margin-top | 0px | 14px |
| color | rgb(237,242,239) | rgb(143,154,149) |

证据在[recheck-r89-ui-evidence](recheck-r89-ui-evidence/)：`formal-rules-1440-zh.png`、`baseline-rules-1440-zh.png`、`vocab-header-style.json`。这是人工图片比较后再用计算样式证实的偏差。当前`td-baseline.spec.js`只比较可见输入控件，未覆盖表头，所以自动基线检查全绿不能否定问题。

修复要求：恢复已冻结表头样式及响应式隐藏边界，增加表头布局/字号断言；无需改变产品设计或重新询问用户，禁止覆盖冻结图来通过。建议同时检查600–700px表头隐藏阈值，生产目前仅max600px，冻结为max700px（该区间未本轮浏览器复验，不作为第二个确认缺陷）。

## 本轮实际独立执行

启动仅本机Vite5191；正式`/`生产main.js/td-settings.js，所有API由既有fixture拦截，未另造验收页。

1. `td-settings.spec.js td-validation-states.spec.js td-baseline.spec.js td-history-baseline.spec.js --project=desktop-chromium`：**12 passed /16.6s**。覆盖保存、未保存编辑保留、键盘切换和aria状态、禁用、四错误态、中英1440/390、六配置子页冻结控件样式、Sessions结构。
2. `td-shell-baseline.spec.js td-history-recovery.spec.js td-asr-source-entry.spec.js --project=desktop-chromium`：**6 passed /8.6s**。Share卡片/禁用恢复/草稿，历史503→空态恢复，六ASR入口及来源切换，均含1440/390。
3. `td-settings.spec.js --grep 'number completeness' --project=narrow-chromium`：**1 passed /1.5s**。该用例明确390px，不是1024px替代。

共19个浏览器用例通过。手工查看本轮正式与冻结词表截图发现上述P2，原完整性修复截图亦检查。冻结源只读；D056/D072/D073允许差异不包含词表表头。

实际命令前缀：`VOICE_AGENT_UI_URL=http://127.0.0.1:5191 VOICE_AGENT_TD_UI_EVIDENCE=/tmp/voiceagent-r89-independent-ui node node_modules/@playwright/test/cli.js test`（frontend目录）；输出分别`/tmp/voiceagent-r89-independent-ui-results[-extra/-narrow]`。浏览器初次启动前本地监听受权限限制，工具批准后正常运行；不是产品失败。

## Gate2仍缺什么

本轮已增加独立C的页面功能、冻结视觉抽查和基本可访问性证据，不应仍简单写“C未开始”。但确认视觉偏差应先修复；完整键盘焦点路径/屏幕阅读器/跨浏览器并未实测，不能声称完整可访问性通过。真实API/storage B有r84及r89历史重启研发证据，本轮只读核对，不能把fixture保存当实际持久化。RTC、真实设备/AEC和厂商效果由其他分项评审覆盖或明确未验证，本UI报告不代签整Change/Gate2。

临时脚本`/tmp/voiceagent-r89-vocab-header.cjs`与测试图在/tmp保留诊断，关键安全截图/JSON已复制本报告证据目录。Vite本轮服务用完停止，不触碰其他服务。
