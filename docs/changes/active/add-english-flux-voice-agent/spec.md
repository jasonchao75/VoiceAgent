# Spec: English Flux Voice Agent MVP

## 1. Product Boundary（产品边界）

第一版是一个面向内部测试的英文浏览器 Voice Agent，而不是生产客服系统。
它必须优先证明实时 Pipeline、基础可配置性、打断体验和可部署性，不扩展到电话、复杂业务工具或多厂商同时接入。

## 2. Target Flow（目标流程）

```text
Browser microphone
  -> FastAPI WebSocket transport
  -> Pipecat pipeline
  -> Deepgram Flux STT
  -> LLM context aggregator
  -> OpenAI-compatible streaming LLM
  -> TTS provider factory
       -> Deepgram Flux TTS (implemented)
       -> ElevenLabs TTS (extension point only)
  -> Browser audio playback
```

用户开口事件同时触发 interruption 路径：停止浏览器本地播放、取消未完成的 LLM/TTS 输出，并开始处理新的用户轮次。

## 3. Runtime Configuration（运行配置）

### Requirement: Configuration separation

正式 Agent 配置必须放在 `configs/runtime/`，不得复用或覆盖现有 `configs/vendor/deepgram/config.json`。后者继续作为 Arabic Nova-3 ASR 厂商测试配置。

运行配置至少包含：

- Agent language（MVP 固定为 `en`）
- Flux ASR model 与允许的端点检测参数
- LLM provider、base URL、model 和显式 timeout（不包含 API Key）
- TTS provider（MVP 只允许 `deepgram_flux`）
- Flux voice、speed、expressivity 和输出采样率
- 默认 System Prompt 与 Opening Script
- 会话空闲超时和最大会话时长
- 可独立更新的 Flux Voice Catalog 与 LLM Provider Catalog；Catalog 只保存公开元数据和官方文档链接，不包含凭证

运行配置和服务器环境变量不得包含共享 Deepgram/LLM API Key。两类厂商 Key 必须由用户在每次创建会话时提供。

### Requirement: BYOK credential lifecycle

- Deepgram 和 LLM 全部强制 BYOK，不提供共享默认 Key 或服务器 fallback Key。
- 前端使用 password 类型遮罩输入框收集 Deepgram API Key 与 LLM API Key，不得写入 Local Storage、Session Storage、Cookie 或 URL。
- Key 只能通过初始 HTTPS `POST` 会话创建请求体提交给后端，不得放入 Query String、WebSocket URL 或后续音频/控制消息。本地验收允许浏览器安全上下文认可的 `localhost` / `127.0.0.1` loopback HTTP 例外；非 loopback 地址必须使用 HTTPS。
- 后端为成功创建的会话生成随机、不可预测、短时有效的 opaque session token；WebSocket 后续只使用该 token 建立会话。
- 后端只在当前进程内存中保存 Key，并将其绑定到单一会话；禁止写入数据库、缓存、文件、异常详情、监控标签或日志。
- 会话结束、创建失败、空闲超时、最大时长到期或异常关闭时，后端必须释放对应凭证引用并使 session token 失效。
- API 错误可以提示 Key 无效或权限不足，但不得回显 Key、Key 前后缀或上游完整鉴权请求。

### Scenario: Session overrides

WHEN 用户在未开始会话时填写两类 API Key，并通过引导控件修改 System Prompt、Opening Script、LLM model 或 Flux voice
THEN 前端在创建会话时提交这些非敏感配置
AND 前端只通过初始 HTTPS 请求体提交 API Key
AND 后端完成白名单校验并创建内存会话后清除前端表单中的 Key
AND 会话开始后锁定影响连接的配置
AND 修改后的配置只在下一次新会话生效

## 4. Pipeline（实时处理管道）

### Requirement: Asynchronous pipeline

核心 Pipeline 必须使用 Pipecat 和 asyncio，不得在音频、厂商网络请求或 Frame Processor 中使用同步阻塞 I/O。

### Scenario: Normal conversation turn

WHEN 用户说完一句英语
THEN Flux ASR 产生 transcript 与结束轮次信号
AND transcript 被加入 LLM 上下文
AND LLM 文本按流式增量进入 Flux TTS
AND Flux TTS 音频按到达顺序立即返回浏览器播放
AND 不等待完整 LLM 回复后才开始合成

### Requirement: Opening script

Opening Script 是 Agent 已说出的第一条 assistant message，而不是 System Prompt 的一部分。

### Scenario: Assistant speaks first

WHEN 会话建立且 Opening Script 非空
THEN 系统通过选定 TTS 播放 Opening Script
AND 将其以 assistant role 记录进同一会话上下文
AND Opening Script 播放期间允许用户打断

WHEN Opening Script 为空
THEN Agent 不主动说话并等待用户输入

### Requirement: Barge-in

WHEN Flux ASR 或前置 VAD 判断用户开始说话
THEN 浏览器立即停止当前本地播放
AND Pipeline 取消尚未完成的旧 LLM 输出
AND TTS 收到适用的 interruption 控制
AND 旧轮次残余音频不得重新播放
AND 新用户轮次能够继续完成

第一版必须记录打断发生时间与音频停止时间。Deepgram `playback_offset`、`text_spoken` 和 LLM 上下文精确对账如受 Pipecat 当前适配器限制，应在测试报告中明确说明，不得声称已经完整支持。

## 5. Provider Interfaces（厂商接口）

### Requirement: TTS provider extension point

Pipeline 不得在编排代码中直接写死 Deepgram 构造逻辑。必须通过小型 Provider Registry/Factory 根据配置创建 TTS service。

第一版 Registry 只注册 `deepgram_flux`。ElevenLabs 只定义未来适配所需的稳定接口边界，不添加不可运行的伪实现，不发起 ElevenLabs API 请求。

### Requirement: LLM integration

第一版使用一个 OpenAI-compatible Streaming 接口，以会话配置提供 `base_url`、`model`，以 BYOK 会话凭证提供 API Key，从而允许选择一家兼容厂商完成真实联调。

必须提供不调用付费 API 的 mock LLM 测试；真实 LLM 厂商与模型在连通性测试前由用户提供或确认。

## 6. Audio Contract（音频约束）

- 浏览器输入、Pipeline、Flux ASR 和 Flux TTS 的 encoding、sample rate、sample width 与 channels 必须显式声明和校验。
- 任何重采样必须发生在明确的边界，不能依赖厂商或浏览器隐式猜测。
- MVP 采用单声道 PCM；具体输入/输出采样率在实现前根据所锁定的 Pipecat 与 Deepgram 官方版本确定，并写入运行配置与测试断言。
- DigitalOcean 公网页面必须使用 HTTPS/WSS，否则浏览器麦克风能力不作为可用交付。

## 7. Frontend（前端页面）

页面参考 Vapi 的信息架构，采用简洁的单页测试台：

- 配置区：Deepgram API Key、LLM API Key、LLM provider/base URL/model、System Prompt、Opening Script、Flux voice。
- 会话区：用户/Agent transcript、当前发言方、错误提示。
- 控制区：Start Session、End Session、麦克风状态。
- 状态区：WebSocket、ASR、LLM、TTS 状态和基础延迟。

### Requirement: Guided Flux voice selection

- Flux Voice 主控件必须使用下拉选择，不要求用户手工输入 model ID。
- Voice Catalog 由后端运行配置提供并可独立更新；至少包含显示名、model ID、口音、性别、年龄、声音特征和推荐用途。
- 页面必须显示当前选中项的 model ID，并提供 Deepgram 官方 [Flux TTS Voices & Languages](https://developers.deepgram.com/docs/flux-tts/voices) 与官方试听入口。
- MVP 默认只允许 Catalog 中经过验证的英语 Flux voice。新增 voice 通过更新 Catalog 和验证后开放，不在普通界面提供无校验自由输入。

### Scenario: Select a Flux voice

WHEN 用户打开 Flux Voice 下拉框
THEN 用户能看到易懂的名称与关键声音特征
AND 选择后能看到实际 model ID
AND 用户可以打开官方 Voice Catalog 或试听页面进一步比较

### Requirement: Guided LLM configuration

- LLM Provider 使用预设下拉框，MVP 至少提供一个已完成连通性验证的 OpenAI-compatible Provider，以及 `Custom OpenAI-compatible` 高级选项。
- 每个 Provider 预设由后端 Catalog 提供：显示名、默认 base URL、推荐 model ID、获取 API Key 的官方链接、查看模型列表的官方链接。
- 选择预设时自动填充 base URL，并以可搜索下拉/组合框展示推荐 model；因为模型权限和 ID 变化频繁，必须保留手工输入自定义 model ID 的能力。
- 选择 `Custom OpenAI-compatible` 时，用户必须自行提供 HTTPS base URL 与 model ID；页面明确说明仅支持 OpenAI-compatible Streaming API。
- 所有帮助链接必须来自受控 Catalog、使用 HTTPS 并在新标签页打开，不得根据用户输入拼接可执行链接。
- API Key 字段旁必须显示简短 BYOK 说明：Key 从对应厂商控制台获取，仅用于当前会话，不会保存。

### Scenario: Configure an LLM without knowing model IDs

WHEN 用户选择一个 LLM Provider 预设
THEN 页面自动提供该 Provider 的 Key 获取入口、模型文档入口、默认 base URL 与推荐 model
AND 用户可以直接选择推荐 model
AND 用户仍可切换为高级自定义 model ID

### Scenario: Safe configuration

WHEN 用户输入并提交厂商 API Key
THEN Key 只存在于遮罩输入框和初始 HTTPS 会话创建请求体
AND 提交成功后前端清空 Key 输入值与相关 JavaScript 引用
AND 页面源码、URL、Local Storage、Session Storage、Cookie、接口响应和 WebSocket 消息中不得出现厂商 API Key

### Scenario: Recoverable error

WHEN 麦克风拒绝授权、WebSocket 断开或任一厂商返回错误
THEN 页面显示可理解的错误信息
AND 会话能够安全结束
AND 用户可以在问题解决后重新开始新会话

## 8. Observability and Evaluation（观测与评测）

每个会话使用非敏感 session ID 串联日志。第一版至少记录：

- WebSocket 连接建立时间
- 用户 turn start / turn end
- ASR final 到达时间
- LLM first token 时间
- TTS first audio 时间
- 浏览器 first playback 时间（由前端回传）
- interruption 与本地 audio stopped 时间
- 厂商错误类型和会话关闭原因

页面至少展示：用户结束说话到首个可听音频的端到端延迟，以及 LLM first token 到 TTS first audio 的延迟。日志不得输出密钥；完整 transcript 是否写入服务端日志默认关闭。

## 9. Local Delivery（本地交付）

- 提供 `.env.example`，只包含非厂商的运行参数与说明；不得要求配置共享 Deepgram/LLM API Key。
- 提供一条主启动命令，优先使用 Docker Compose，使用户无需手工创建 venv 或安装 Python 包。
- 提供 `/health`；健康检查不得调用付费厂商 API。
- 提供启动、停止、配置和常见问题说明。
- 本地自动化测试和浏览器核心路径通过后，才能进入公网部署。

## 10. DigitalOcean Demo（公网 Demo）

DigitalOcean 部署是本 Change 的第二交付阶段，不是开始编码的前置条件。

部署必须满足：

- 使用独立 demo 服务与非 root 运行身份。
- Nginx 反向代理静态页面、API 和 WebSocket。
- 域名或可受信任主机名启用 HTTPS/WSS。
- 不在服务器环境变量、部署 Secret 或配置文件中保存共享 Deepgram/LLM Key；厂商 Key 只使用会话级 BYOK 内存凭证。
- 公网入口增加最小访问保护（推荐 Nginx Basic Auth）、会话时长限制和并发限制，避免测试密钥被滥用。
- 部署前运行本地检查；部署后检查 `/health`、WebSocket 和浏览器麦克风路径。
- GitHub 对 push/PR 自动运行不调用付费厂商 API 的测试与生产镜像构建。
- 仅 `main` 分支 push 对应的 CI 全绿后，才可自动部署到 `platform.voiceagentdemo.org`；PR、fork 或失败的 CI 不得触发部署。
- 自动部署必须串行执行、固定 SSH 主机指纹、验证目标 commit 属于远端 `main`，并在容器启动或健康检查失败时保留或恢复上一健康镜像。
- 仓库变量 `PLATFORM_DEPLOY_ENABLED` 是部署总开关；首次初始化完成前及紧急维护时必须保持关闭。
- 自动部署只使用服务器运行参数与部署凭证；不得向 GitHub Secrets 或服务器写入共享 Deepgram/LLM Key。
- 资源创建、DNS 变更、服务器写入、真实 API 费用和部署动作必须由用户再次确认。

## 11. Acceptance Scenarios（验收场景）

1. **Assistant-first**：填写 Opening Script 后开始会话，Agent 先说话，随后完成至少三轮英语对话。
2. **User-first**：清空 Opening Script 后开始会话，Agent 等待用户先说话。
3. **Prompt behavior**：更换 System Prompt 并新建会话，回复风格发生符合预期的变化。
4. **Voice selection**：更换合法 Flux voice 并新建会话，配置实际生效。
5. **Configuration guidance**：用户可从 Voice/Model 推荐项完成配置，并能打开对应厂商的官方 Key 与模型文档。
6. **Barge-in**：在 Agent 播放长回复时开口，旧音频停止且新一轮继续。
7. **Failure recovery**：模拟 LLM/TTS 错误，页面可见、会话安全关闭、能够重新连接。
8. **BYOK lifecycle**：两类 Key 只能通过初始 HTTPS 请求体提交；会话结束后 token 失效，服务器日志、存储、响应和后续 WebSocket 消息中均无 Key。
9. **Public demo**：经用户批准部署后，通过 HTTPS 页面完成上述核心路径。
