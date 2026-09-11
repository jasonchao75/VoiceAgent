# Gate 1 产品验收板

Status: **Approved on 2026-09-08.** 产品已确认可交互原型无问题。

本页是开发前的产品范围确认，不是最终 UI 验收。Delta Spec、状态矩阵及设计文档作为研发与测试追溯材料，不要求产品逐条阅读。

## 验收方式

1. 打开 `prototypes/index.html`，按下表依次进入五个区域。
2. 判断页面结构、字段、控件类型和主要交互是否符合预期。
3. 产品确认后，原型冻结为实现基线，不因实现偏差要求产品重复确认需求。
4. 实现偏差由 Gate 2 的原型/正式页面对比发现并修正；Gate 3 才是最终产品验收。

## 一页验收清单

| 区域 | 本次必须确认的内容 | 原型操作 | 产品结论 |
|---|---|---|---|
| ASR | 仅 Deepgram / Flux ASR；English/Automatic；Automatic language hints；只读 PCM 16 kHz；Advanced 展示 EOT threshold 拖拽条、EOT timeout、Keyterms、Profanity filter、Numerals、Redact；API Key 默认可填写，保存选项仅决定是否持久化 | 点击 ASR 卡片，切换 Language 并展开 Advanced | 已确认 |
| LLM | Provider/Base URL/自由输入 Model/Temperature；Advanced 含 Thinking、Max response tokens、Request timeout；独立且默认可填写的 API Key；Test connection 显示 TTFT | 点击 LLM 卡片并展开 Advanced | 已确认 |
| TTS | Initial speed 之前是基础项；之后统一归入 Advanced；Text aggregation 排第一；ElevenLabs 先填 Key 才选 Voice；Deepgram Voice 不依赖 Key 且无 Custom Voice ID；API Key 默认可填写 | 点击 TTS 卡片并切换两个 Provider | 已确认 |
| Tests | Chat 与 Web call 均有 Start/End；播放 opening message；每次 Agent 回答下方就近展示 Turn latency；Chat 支持发送文字打断；Web call 展示字幕 | 使用顶部 Test bot 分别进入两种测试 | 已确认 |
| Sessions | 主区保持逐行列表；View 打开可收起抽屉；对话不显示 Agent/Caller 标签；每个回答下方展示 Turn latency；Web call 提供历史录音 | 打开 Sessions 并点击一条 View | 已确认 |

## Gate 1 不要求产品逐项验收的内容

- loading、接口失败、空数据、长文本、字段校验和录音过期等覆盖完整性，由 `prototypes/ui-state-matrix.md` 追踪。
- 精确尺寸、颜色、间距、字体和响应式规则，由 `prototypes/ui-annotations.md` 追踪。
- 每条行为的 Given/When/Then 契约，由 Delta Specs 追踪。
- 上述内容在 Gate 2/3 通过截图 diff、功能测试和可访问性检查提供证据；发现产品决策问题时再单独提请确认。

## 已确认的规格基线

- Flux ASR Advanced 的正向字段清单已经写入 Delta Spec。
- 各组件 API Key 默认可填写；是否保存只控制加密持久化，不控制输入能力。
- 不支持项仍明确保持隐藏：Eager EOT、Nova endpointing、smart detection、noise suppression。
- 本次没有改变其他业务目标或参数规则。
