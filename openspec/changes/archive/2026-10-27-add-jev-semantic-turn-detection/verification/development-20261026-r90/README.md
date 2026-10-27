# r90 界面返修与阶段验收增量（2026-10-26）

已修复r89唯一新增词表表头缺陷；本地键盘验收发现并修复Jev切换、编辑行增删、Sessions与ASR组件抽屉焦点去向。无后端/媒体/协议/产品规则变更。原六项独立关闭保持，不重做；RTC候选默认关闭、RTP保留。完整Checkpoint C/User Gate2仍未通过。

## 实际验证（fixture，不冒充真实API/硬件）

| 检查 | 结果/证据 |
|---|---|
| 冻结基线CSS红绿 | 原样式6失败→6通过；中英1440/390、650隐藏及701显示断点，颜色/10px/14px/列坐标与冻结对比。header-red.txt、header-green.txt、header/*.json/png |
| 键盘红绿 | 原Jev/行新增/Session焦点6失败；原ASR抽屉2失败→10通过；keyboard-red.txt、component-red.txt、voiceagent-r90-keyboard-final.txt、keyboard/*.json/png |
| 当前Google Chrome | 14通过（上述6表头+8键盘）；voiceagent-r90-chrome.txt、chrome/*；最后Sessions身份修复后只复验受影响4条通过（voiceagent-r90-chrome-refresh.txt），不累加为18个不同场景。Chrome156.0.8078.47，与Chromium同引擎，不代表Safari |
| 构建 | Vite通过；voiceagent-r90-build.txt |
| 冻结SHA | v0.14仍为657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4；未改基线 |
| 原全量回归 | r89独立756后端/25客户端；本轮无后端/媒体改动，按用户要求不重复跑未受影响项 |

键盘路径覆盖Tab/ShiftTab/Enter/Space/Home/End/Escape、focus-visible、语义禁用跳过、可访问名称及重复ID、Jev页返回、词表/问题行增删、非模态抽屉打开/退出焦点。没有新增焦点陷阱或改成模态。DOM ARIA快照不等于VoiceOver/WCAG完整审核；见[设备计划](../device-performance-test-plan.md)。

测试修正完整披露：701px冻结自身表头中心在输入外约3px，首次额外中心断言过强；改为冻结相对列坐标，1440仍检查中心。Delete原泛button匹配Listen/Delete两元素，改.td-remove；Sessions常规路径等待列表响应只验证加载完成；独立随后证明刷新原DOM仍可造成隐藏焦点，已登记R90-SESSIONS-REFRESH-FOCUS并按callId恢复新行/可见Sessions入口。independent-refresh-red.json保留原独立真实失败；新增刷新回归最初整行多行文本匹配失败，改按稳定会话ID定位后通过，refresh-red.txt不独立充当产品红灯。保留header-first-oracle-failure.txt、keyboard-first-selector-failure.txt。另一次受限环境浏览器启动失败未执行用例，隔离本地浏览器获权限后运行；不把启动错误算产品失败或通过。

## 复现

从项目根：`cd frontend && npm ci`（已有依赖时无需安装），`npm run dev -- --host 127.0.0.1 --port 5192`。另终端在frontend运行：

```
VOICE_AGENT_UI_URL=http://127.0.0.1:5192 npx playwright test tests/ui/td-vocab-header.spec.js tests/ui/td-keyboard-accessibility.spec.js --project=desktop-chromium --workers=1
```

加`VOICE_AGENT_TD_UI_CHANNEL=chrome`使用已安装Google Chrome隔离临时配置。API在测试中全部拦截fixture，正式路由/组件/DOM照常加载；冻结HTML只读比较，不维护另一套验收页面。截图可指定`VOICE_AGENT_TD_UI_EVIDENCE=/tmp/td-r90-review`。不调用真实厂商、不请求麦克风。测试需要已安装Playwright Chromium；缺浏览器应先说明安装条件，不能把未执行当通过。

环境：macOS arm64、Node25.9.0、现有Python3.13.2；本机发现Python3.11.15但无pytest依赖，Safari26.6.2已安装未实测；Docker CLI存在但受限执行未连接daemon，不据此推导daemon不可用。

## 剩余工作与最小下一步

1. 本增量已独立复审：未发现剩余确认实现缺陷；报告位于stage-review/repair-review-r90.md。全Change仍INSUFFICIENT EVIDENCE，完整C/Gate2未通过。
2. [厂商计划](../vendor-specialist-test-plan.md)：先冻结一段含否定/停顿的虚构英文及真值/hash，核对单模型单连接预算，再单独请求本批授权。已有额度均已消费，本轮0外部调用。
3. [设备/性能计划](../device-performance-test-plan.md)：准备隔离3.11依赖环境、iPhone/Safari及麦克风、Linux1核1GB/UDP故障环境，再做配对链路延迟；缺设备/环境继续未验证。RTC默认采用仍是后续产品决定，本轮不需要重问已有规则。

回退：仅移除本轮CSS/焦点增量会恢复已确认缺陷；不应整文件回滚共享工作区。新增测试与fixture无生产依赖。临时证据/tmp/voiceagent-r90-*、忽略test-results/playwright*、frontend/dist；保留r90目录选定截图/白名单JSON/日志，未保存新录音、DB或真实Key。旧r89冻结包保持不变，本轮源码增量与证据另行封装，不冒称旧tar是新实现。
