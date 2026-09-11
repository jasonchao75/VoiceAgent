# Gate 2 实现偏差复盘

## 结论

本轮主要问题不是原型不清楚，而是实现和自检没有把已确认原型当成逐区域、逐状态的强约束。首轮验收过度依赖静态字符串检查，缺少真实数据、完整交互生命周期、第三方 SDK 行为和布局溢出的浏览器验证，导致多个明显偏差由用户先发现。

## 用户发现的问题与根因

| 区域 | 发现的问题 | 根因 |
|---|---|---|
| ASR | EOT threshold 控件形态错误；开关样式不一致；缺 Audio input；API Key 被保存开关阻塞且跨组件串值 | 只核对字段是否存在，没有逐项核对控件形态、顺序和组件级状态隔离 |
| LLM | Advanced 层级不一致；缺 Max tokens / Request timeout；测试被原生确认框阻塞 | 原型区域未形成实现检查表；用浏览器原生交互代替产品内状态反馈 |
| TTS | Provider 切换未联动；Deepgram 错带 Custom Voice ID；Key 依赖规则混淆；Voice Library 过滤和层级偏差 | 未覆盖 provider × credential × voice source 状态矩阵 |
| Sessions / Advanced | Sessions 曾用卡片而非列表；抽屉不能收起；缺录音；日期本地化成中文；Advanced 丢失机器人列表且作用域不清 | 只验证单页静态结果，没有验证导航、抽屉开关、数据态和 locale |
| Chat / Web call | Chat 错误请求麦克风、长时间 Connecting、Start 看似无响应、重启不清历史、实时延迟拆分不完整 | 对媒体 SDK 行为做了未经验证的假设；未覆盖 Start → Send → End → Restart 生命周期 |
| 浮层 | ElevenLabs Voice Picker 出现横向滚动条 | 固定列宽、sticky footer 负边距和滚动容器组合未做 `scrollWidth` 检查 |

## 防复发机制

1. 已确认原型必须拆成“区域 × 状态 × 控件形态 × 顺序”的实现清单；每项同时映射规格、原型和验证证据。
2. Gate 2 自检先使用固定的有数据 fixture，覆盖空态、长文本、异常态、Provider 切换、Key 有无、桌面和窄屏；用户不承担首轮找错。
3. 交互测试必须覆盖完整生命周期和跨页面状态：打开/关闭抽屉、Start/Send/End/Restart、Chat 无麦克风、WebSocket ready、Sessions 录音与逐 Turn 指标。
4. 第三方 SDK 和浏览器原生控件不得靠推测验收；需真实浏览器 smoke test。要求固定英文日期时不用依赖系统 locale 的原生日期展示，常规流程不用阻塞式 `window.confirm`。
5. 所有浮层增加布局不变量：固定桌面与窄屏下 `scrollWidth <= clientWidth`，长名称可收缩/换行，只允许纵向滚动。
6. 每一个用户发现的缺陷，在修复完成前必须转成自动化断言或 `ui-checklist.md` 回归项，并在当前 Change 保存证据。

## 本次新增回归项

- Voice Picker、Session drawer、组件 drawer 禁止横向滚动。
- Voice Picker sticky footer 不再使用会扩大滚动宽度的横向负边距。
- 长 Voice 名称、语言和描述允许收缩或换行。
- 静态契约测试锁定浮层横向溢出规则；浏览器验收继续覆盖桌面与窄屏实际 `scrollWidth`。

## 验证结果（2026-09-10）

- Chrome 固定桌面视口、ElevenLabs 真实 30 条音色：Voice Picker `clientWidth = 743px`、`scrollWidth = 743px`、`overflow-x = hidden`，无横向滚动条；纵向滚动保留。
- 前端契约测试：15 passed。
- Vite 生产构建：通过；保留现有单包体积大于 500 kB 的非阻塞警告。
- 本地 Docker 页面已重建并启动；窄屏和其他浮层的真实浏览器尺寸检查仍属于 Gate 3 全量视觉回归范围。
