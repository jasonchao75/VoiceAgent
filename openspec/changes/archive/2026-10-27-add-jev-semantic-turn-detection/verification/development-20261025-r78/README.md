# r78 D-073 播放范围实际集成与自测

## 实现范围

- RenderClockSampler经同一认证会话请求nonce，实际Worklet process回报frame；不等音频、不更换RTP、不传数据通道音频。WS TaskMediaManager与开发RTC候选均接入；旧默认RTC不变。
- 帧严格处于同一时钟两个锚之间时才形成服务端因果区间；不插值、不取RTT/2。回报收件时刻只作为区间的上界证据，不充当实际开播单值。
- 范围通过playback/response/turn不可变身份保留到原回复；锚迟到不挂到当前新轮。首普通回复范围进入TurnMetric.timing_ranges，逐回复范围及完整两锚在TD事件中保留。
- origin明确是server_audio_task_prepared，即该音频任务在服务端就绪到客户端Worklet渲染，不冒充硬件声学出声、旧标量同口径或完整用户感知延迟。原playback_ms/E2E标量不回填，不取区间中点。缺人声结束时钟的E2E保留source_end_clock_unavailable，**E2E源端关联尚未实现**。
- 新SQLite nullable JSON列timing_ranges保存范围，旧NULL读为空。正式Sessions原回复旁显示范围、来源/测量不确定性，数值向外舍入，语言切换不改值，390px抽屉无横溢。实时与历史共享格式器明示范围起点及响应。
- 空闲锚只占有界内存；实际任务派生范围时才持久化它使用的两锚，不让定时采样填满对话证据上限。

## 实际结果（范围不可拼接为一次全端全绿）

| 检查 | 结果 | 证据 |
|---|---|---|
| 当前完整后端 | 706 passed，5依赖警告，38.99秒 | backend-full.txt |
| 本轮相关后端 | 38 passed，2依赖警告，2.03秒 | backend-targeted.txt |
| 客户端纯组件 | 9 passed | client-final.txt |
| 正式历史1440/390中英 | 2 passed，1.6秒 | ui-range-green.txt、ui/截图 |
| 独立浏览器原生组件 | 1 passed，505ms；实际挑战/ack两请求 | native-globals-green.txt |
| 正式开发RTC | 1 passed，7.4秒；原映射/实际播放/Final停止/鉴权回执/持久范围 | rtc-clock-fixed.txt、rtc-fixed/ |
| 正式WS | 1 passed，6.7秒；原上行/Final取消/实际回执/范围/持久历史 | ws-clock.txt、ws/ws-timing-history.json |
| 实际应用进程重启 | RTC、WS的metrics与range事件通过真实HTTP原样读回 | api-process-restart.json |
| 独立阶段审查 | 因果数学未发现新缺陷；P2展示起点遗漏已按红绿证据复核关闭 | stage-review/preliminary-d073.md |
| 生产前端构建、Ruff | 通过 | build-final.txt、ruff.txt |

当前实际RTC两个回复范围（按正式UI向外舍入）：1:1为0–33.0ms；1:2为19.0–68.8ms。它们是本机替身任务的因果包围，不是厂商延迟/P95/手机性能。离线核对每个目标frame严格位于所存前后锚之间，见rtc-range-proof-audit.json。

## 失败和修复

- worklet-red：实际量子没有clock_sample；实现后通过。range-red：capture缺ack_render_clock；storage-red：范围重启丢失KeyError；idle-volume-red：空闲锚污染证据。修复后相关38项通过。
- ui-range-red：原回复范围卡片缺失，实际0而预期1；修复后双视口通过。
- rtc-clock首次失败停在新增指标查询：测试用了公开响应中不存在的session_token，实际GET401；播放/取消之前断言已过，未出现任务映射失败。客户端原生global函数用作类成员丢失Window调用接收者也令clock没有请求。默认fetch/setTimeout/clearTimeout改为globalThis包装后，组件与正式RTC通过。
- native-fetch相关初次分界有页面导航干扰，受控红灯仍没有请求，最终统一修原生函数绑定后通过。不能据此宣称单独证明fetch是唯一根因；所有失败保留。
- 独立评审P2指出实时指标卡漏origin。origin-red精确缺起点；共享格式修复后1 passed/871ms，独立只读复核关闭。
- 一次npm构建误在仓库根执行，package.json不存在，未实际构建；随后在frontend正确目录通过。该失误不是产品构建红灯。

## 安全与未验证

实际ASR/LLM/Jev/TTS全是loopback应用离线替身，使用合成声和浏览器假麦克风，未调用付费厂商。新时钟接口绑定live lease，不接受未知/篡改nonce；已完成采样重放不刷新时刻。采样周期500ms、任务启动额外有界采样、2秒过期/8 pending/32锚/64待派生任务是可回退资源策略，不是产品精度或性能SLA。

/tmp/voiceagent-r78-rtc-clock保留本轮测试DB、加密本地惰性Key及假麦克风录音；原始服务器/Vite日志在/tmp/voiceagent-r78-*.log，可能含临时能力URL，均不提交或打包。test-results/playwright的失败截图/trace同样保留为忽略产物，不直接并入审核包。本轮8793/5178服务已停止；未停其他任务或用户原型8794。

**尚缺：** 用户原始停声到渲染的E2E源时钟关联、真实厂商及取消兼容、硬件出声/手机/Safari/弱网/AEC/目标容量、默认RTC采用和完整UI/最终独立审核。不是完整交付/独立PASS/Checkpoint C/Gate2；旧审核包只代表旧源码。

## 最后类型检查结论

mypy-full.txt首次暴露本Change编码器first_packet_pts继承属性的类型缺失；补int|None声明（不改编解码逻辑）后mypy-clean.txt实际无增量Python3.13全src76文件通过。后端706项结果早于该纯注解；注解后RTP8项通过/1.17秒，不重复706项。旧47项错误/比较文件保留，不继续当作当前状态。默认部署Python3.11环境未在本轮运行，不据3.13结果声称3.11通过。

## 当前阶段审核输入

review-package/review-inputs.tar.gz包含405文件，逐文件hash核验。第一次解包46项相关后端通过后发现frontend/tests/unit漏打包；补完整目录后另解包客户端9项通过，两个版本后端输入hash相同。原失败和输入副本保留，不以封装遗漏当产品单测失败。源快照状态冻结在验证前，最新结论以外层报告/机器状态为准；最终全范围包尚待E2E源端及厂商/平台等任务关闭。
