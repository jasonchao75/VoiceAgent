AI初稿，尚未完成.暂不可用

---
name: pipecat-integration
description: 提供基于 Pipecat 框架构建 Voice Agent 核心流水线（Pipeline）的标准作业程序（SOP）、并发原则、帧（Frame）处理规范及最小可用脚手架。当开发、重构音频流处理、对接 FreeSWITCH、实现“提前思考 (Thinking Ahead)”或“打断 (Barge-in)”机制时使用此技能。
---

# Pipecat Integration 开发规范与 SOP

## 核心定位

Pipecat 是将所有 Voice Agent 组件（ASR, LLM, TTS, VAD）串联为数据管道（Pipeline）的异步调度中心。万物皆帧（Frame），组件皆处理器（FrameProcessor）。

## 核心开发原则

1. **绝对禁止同步阻塞**：
   - 所有的 `process_frame` 方法必须是 `async` 并在 `asyncio` 事件循环中非阻塞执行。网络请求必须带 `timeout` 并使用 `aiohttp` 或异步 SDK。
2. **正确流转与放行 Frame**：
   - 如果你的处理器不需要修改该帧，**必须**显式调用 `await self.push_frame(frame)` 传给下一个处理器，否则管道会在此断流卡死。
3. **优雅处理控制帧 (Control Frames)**：
   - 监听打断信号，例如 `UserStartedSpeakingFrame`，必须支持内部状态（如积压文本、LLM 上下文）的迅速清理（Flush）。

## 关键工作流 (Workflows)

### 1. 编写自定义适配器 / 中间件
- **场景**: 对接新厂商或添加业务逻辑。
- **SOP**:
  1. 继承 `pipecat.processors.frame_processor.FrameProcessor`。
  2. 重写 `async def process_frame(self, frame: Frame, direction: FrameDirection)`。
  3. 通过 `isinstance(frame, TargetFrameClass)` 判断帧类型。
  4. 对关心的数据做异步处理。
  5. 必须 `await self.push_frame(frame)` 放行或替换为新的 Frame。

### 2. 实现“提前思考 (Thinking Ahead)”
- **场景**: 在 ASR 仅输出 `[Partial]` 时提前请求 LLM。
- **SOP**:
  1. 创建一个拦截器，监听 `TranscriptionFrame`。
  2. 提取并判断其 `.text` 及 `.is_final` 属性。
  3. 遇到非 Final 的长句子或停顿点，立刻发送异步请求给 LLM。
  4. 缓存生成的上下文，等待 Final 确认后再放行或直接输出 TTS。

### 3. 实现“打断 (Barge-in / Flush)”
- **场景**: 用户说话时中断 TTS。
- **SOP**:
  1. 确保 VAD 在管道最前端。
  2. VAD 触发 `UserStartedSpeakingFrame` 时，管道底层的 task group 会自动向所有下游下发 `CancelFrame`。
  3. **你的责任**：在自定义的处理器中，捕获 `CancelFrame`，停止任何进行中的耗时任务，重置内部聚合状态（如清空未发送的 ASR 文本）。

## 最小验证与交付标准

- **必须提供脚手架**：任何新增的 Pipeline 模块，必须附带一个不依赖 FreeSWITCH 的本地验证脚本（例如使用本地 `.wav` 喂入管道，或通过 WebSocket 模拟发送流）。
- **示例模板**: 参考 `tests/pipeline/pipecat_minimal_test.py` 结构，确保单模块可以拉起并在终端看到 Frame 流转日志。

> 注: 涉及具体 API 的参考，请查阅 Pipecat 官方文档或本地引用的 vendor reference。
