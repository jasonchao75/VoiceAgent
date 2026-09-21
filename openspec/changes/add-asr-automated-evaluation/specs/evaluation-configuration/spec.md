# Delta: Evaluation Configuration

## Purpose

定义 ASR 自动化评测使用的版本化标签、上下文、Prompt、资源连接、模型和成本配置。

## ADDED Requirements

### Requirement: Global versioned scenario tags

系统 MUST 支持创建、编辑、删除、启用和停用全局场景标签，标签列表不得由前端硬编码。标签 MUST 包含中英文名称、声学或语义类型、自然语言定义、示例、状态和版本，并且不与某个质检上下文绑定。

#### Scenario: Edit a referenced tag

- **WHEN** 管理员编辑已被批次或 Benchmark 引用的标签
- **THEN** 系统创建新版本，历史快照继续引用旧版本且不得被覆盖

#### Scenario: Disable a tag

- **WHEN** 管理员停用标签
- **THEN** 新批次不再获得该标签，历史报告和 Benchmark 仍可读取原标签快照

#### Scenario: Delete an unreferenced tag

- **WHEN** 管理员确认删除未被批次、报告或 Benchmark 引用的标签
- **THEN** 系统从当前标签库和后续选择项中删除该标签，并记录操作审计

#### Scenario: Delete a referenced tag

- **WHEN** 管理员确认删除已被批次、报告或 Benchmark 引用的标签
- **THEN** 系统将其从当前标签库和后续选择项中移除，但 MUST 保留不可变版本、引用快照和审计记录，使历史报告与 Benchmark 继续显示原标签

#### Scenario: Create a tag from an evaluation report suggestion

- **WHEN** 有权限用户确认报告中结构完整的 AI 建议标签
- **THEN** 系统将 AI 输出的中英文名称、中英文描述和声学/语义类型共同写入新的全局标签版本，不得只保存名称；名称或描述缺失时必须阻止创建并提示补全

### Requirement: Versioned evaluation context

系统 MUST 按实际业务范围保存版本化质检上下文，包括业务背景、流程、产品词汇、实体、话术规则和已知 ASR 风险。前端 MUST 只展示“质检上下文”，不得额外引入项目实体。

上下文列表中的“新建上下文”和“编辑新版本” MUST 打开可编辑表单；页面不得展示不可点击的占位操作。保存已有上下文 MUST 生成新版本，不得覆盖当前或历史版本。

质检上下文 MUST 只保存通用业务描述及对参考词典的版本化引用，不得把 `branch_dictionary` 等某一客户或某一业务专属字段固化为系统字段。页面 MUST 说明两轮 LLM 运行时输入的来源：`conversation_history` 来自批次上传，`evaluation_context` 来自当前上下文版本，`reference_dictionaries` 来自上下文关联词典，`screening_strategy` 来自新建批次选择，`scenario_tags` 来自启用标签快照。

#### Scenario: Create a context revision

- **WHEN** 管理员修改已有质检上下文
- **THEN** 系统另存新版本并允许设为默认；已冻结批次继续使用旧版本

#### Scenario: Open a prepared RiyadBank context

- **WHEN** 管理员编辑上线初始化的“利雅得银行分行转接”上下文
- **THEN** 页面预填业务目标、标准流程、术语与实体、判断规则和已知 ASR 风险，并清楚说明将创建的下一版本

### Requirement: Versioned generic reference dictionaries

系统 MUST 支持创建、编辑和版本化通用参考词典。每个词典 MUST 包含稳定 `dictionary_key`、名称、用途说明、版本、通用 schema 和 entries；schema MUST 至少允许 `canonical_value`、`alias`、`code`、`locale` 和 `metadata`，但不得要求所有业务都填写全部字段。

质检上下文 MAY 关联零个或多个参考词典。批次开始时系统 MUST 冻结所有关联词典版本，并以统一的 `reference_dictionaries` 集合传给两轮 LLM；集合内每项自带 key、version、schema 和 entries，不再使用单独的 `branch_dictionary_version` 变量。

#### Scenario: Attach a business-specific dictionary without changing the platform schema

- **WHEN** 管理员把“利雅得银行分行实体词典”关联到“利雅得银行分行转接”上下文
- **THEN** 系统只保存通用词典版本引用；新批次把该词典作为 `reference_dictionaries` 的一个元素冻结并传入两轮 LLM，其他业务无需出现任何分行专属字段

#### Scenario: Update a referenced dictionary

- **WHEN** 管理员编辑已被历史批次使用的参考词典
- **THEN** 系统创建新版本，历史批次继续读取旧词典快照，新版本只供后续上下文版本或批次使用

### Requirement: Fully visible and validated prompts

两轮完整 System Prompt MUST 对管理员全文可见，但默认 MUST 为只读状态。页面 MUST 提供明确的“编辑固定模板”入口；进入编辑状态后才允许修改、恢复完整默认模板并另存新版本。Prompt 原文 MUST NOT 随界面语言切换自动翻译，应用代码 MUST NOT 隐藏另一段会改变业务判断的 Prompt 规则。

质检上下文 MUST 提供两轮成品 Prompt 预览。预览 MUST 同时显示保留 `{{variable}}` 插槽的 Prompt 模板，以及使用当前上下文字段和代表性 Session 数据完成替换后的成品 Prompt；`evaluation_context` MUST 使用当前表单值，`reference_dictionaries` MUST 展开所有关联词典的完整 entries。第一轮模板 MUST 包含 `{{conversation_history}}`、`{{evaluation_context}}`、`{{reference_dictionaries}}`、`{{screening_strategy}}` 和 `{{scenario_tags}}`；第二轮还 MUST 包含 `{{request_group_id}}`、`{{candidate_case}}`、`{{production_transcript}}` 和 `{{asr_results}}`，并公开 `results[]` 与 `positioning_quality` 输出契约。

预览 MUST 提供“表单字段 → 模板变量 → 成品 Prompt 字段”的对应关系。管理员点击任一对应项时，页面 MUST 同时标记模板中的变量插槽和成品 Prompt 中已替换的字段或内容位置。

#### Scenario: Preview assembled requests from a context

- **WHEN** 管理员从上下文列表或上下文编辑表单点击预览
- **THEN** 页面可切换查看第一轮和第二轮，并分别展示含变量插槽的模板、完成全部变量替换的成品 Prompt，以及可定位两侧位置的字段对应关系

#### Scenario: Protect fixed prompts from accidental edits

- **WHEN** 管理员打开两轮 Prompt 配置
- **THEN** 两轮完整模板默认只读，只有点击编辑入口后编辑、恢复和保存操作才可用

保存时系统 MUST 校验必需输入变量、决定枚举和程序读取的返回字段；缺失时 MUST 指明缺少内容并禁止保存。本期 Prompt MUST NOT 输出 confidence，系统 MUST NOT 用 confidence 阈值决定自动入库或人工路由。

#### Scenario: Save a valid prompt version

- **WHEN** 编辑后的完整 Prompt 保留所有必需输入与结构化输出契约
- **THEN** 系统保存不可变新版本，只影响后续新批次

#### Scenario: Remove a required output field

- **WHEN** 管理员删除第二轮 decision、reference text、evidence location 或其他程序必需字段
- **THEN** 页面定位并说明缺失字段，保存操作失败且当前生效版本不变

#### Scenario: Preview a dynamically packed second-pass request

- **WHEN** 管理员预览第二轮 Prompt
- **THEN** 页面展示请求组 ID、组内候选数组、按 conversation ID 分组的历史对话/历史转写/评测 ASR，以及外层 `results[]` 和逐 Case `positioning_quality` 契约，不得仍展示单 Case 顶层输出

### Requirement: Idempotent prepared evaluation defaults

系统 MUST 在上线初始化时提供一份基于既有 RiyadBank 离线两轮流程整理的中文质检上下文、通用参考词典实例、第一轮完整 System Prompt 和第二轮完整 System Prompt。初始化 MUST 幂等：同一稳定 seed key 已存在时不得重复创建版本或覆盖管理员后续修改。

第一轮默认 Prompt MUST 包含通用 `reference_dictionaries`、P1/P2/P3 筛查档位、每个有效用户事件的 candidate/pass/data_issue 结果和事件级回听问题。第二轮默认 Prompt MUST 同样接收 `reference_dictionaries` 与 `screening_strategy`，并包含 event/segment 证据定位、Good Case/Bad Case/Needs manual audio review、双语建议标签完整字段、至少一家评测 ASR 成功的准入规则，以及禁止 confidence 阈值和简单多数票的规则。

#### Scenario: Initialize a fresh evaluation environment

- **WHEN** 新环境首次执行评测配置初始化
- **THEN** 系统创建可用的 RiyadBank 上下文与两轮 Prompt 默认版本，新建批次无需从空白配置开始

#### Scenario: Re-run initialization

- **WHEN** 部署、迁移或应用重启再次执行相同 seed
- **THEN** 系统识别稳定 seed key，既不重复创建，也不覆盖现有版本

### Requirement: Separated encrypted resource connections

系统 MUST 集中维护 ASR 与 LLM 连接。ASR 连接卡片只维护 API Key，具体异步 Endpoint 属于异步 ASR 能力；LLM 连接 MAY 维护兼容网关 Base URL 和 API Key。

Azure GPT 与 OpenRouter MUST 作为独立 LLM 资源保存，不得覆盖或复用 OpenAI/GPT 的资源身份。Azure GPT MUST 解析并冻结资源主机、deployment 和 `api-version`，使用 Azure `api-key` 鉴权；OpenRouter MUST 使用固定官方 OpenAI-compatible Base URL 和 Bearer 鉴权。

Qwen 中国站 MUST 同时支持阿里云官方 OpenAI-compatible URL 与原生 DashScope `/api/v1` URL。系统 MUST 允许 `https://dashscope.aliyuncs.com/api/v1`、已确认的 `https://prem.dashscope.aliyuncs.com/api/v1` 以及 workspace 专属 Model Studio 域名，并按原生消息协议调用仅在该协议可用的 `qwen3.8-max`；不得把原生 URL 强制改写为 compatible-mode URL。

凭证 MUST 只允许写入或替换，不得回显明文；服务端 MUST 使用 Fernet 加密落 SQLite，主密钥只来自 `VOICE_AGENT_STORAGE_KEY`。API 响应、普通日志和验证错误 MUST NOT 包含明文凭证。

#### Scenario: Configure and test a connection

- **WHEN** 管理员提交新的 Key 或 LLM Base URL 并执行测试
- **THEN** 服务端使用未保存草稿验证鉴权、Endpoint、模型和输入能力，返回脱敏的成功或分类错误，并仅在确认后加密保存
- **AND** ASR 三家 MUST 可直接在资源连接页发起测试，并与对应异步能力卡片共享测试状态，不得要求用户跳转后才能测试
- **AND** LLM 测试 MUST 在当前连接卡片立即展示测试中、成功或分类失败；存在同厂商与同 Base URL 的已保存连接时复用加密 Key，否则明确提示填写 Key

#### Scenario: Read a saved connection

- **WHEN** 页面重新打开已配置连接
- **THEN** Key 输入保持空或只显示“已保存”掩码状态，不返回可恢复的密文或明文

#### Scenario: Keep Azure GPT and OpenRouter isolated

- **WHEN** 管理员分别保存 Azure GPT deployment 与 OpenRouter 连接
- **THEN** 两者拥有独立连接记录、验证状态和加密 Key；更新其中一个不得改变 OpenAI/GPT、另一个资源或其他 LLM 连接

#### Scenario: Validate an Azure deployment URL

- **WHEN** 管理员提交 Azure GPT 完整 chat completions URL
- **THEN** 系统只接受 HTTPS `*.openai.azure.com` 地址，并解析唯一 deployment 与 `api-version` 后执行最小真实诊断；缺失、重复或不受支持的路径参数必须在调用前明确拒绝

#### Scenario: Validate a native Qwen China endpoint

- **WHEN** 管理员为 Qwen 提交 `https://prem.dashscope.aliyuncs.com/api/v1` 并选择 `qwen3.8-max`
- **THEN** 系统 MUST 使用 Bearer Key 向原生 `multimodal-generation/generation` 路由发送消息格式诊断；成功后保存该原生 Base URL 和型号，并供两轮评测选择
- **AND** 非 HTTPS、非 DashScope/Model Studio 域名、携带凭证/端口/查询参数或不是 `/api/v1`、`/compatible-mode/v1` 的 URL MUST 在外部调用前拒绝

#### Scenario: Keep connections across deployment restarts

- **WHEN** 应用重启、容器重建或前端版本更新，但仍挂载原数据卷并使用同一 `VOICE_AGENT_STORAGE_KEY`
- **THEN** ASR 与 LLM 连接的脱敏配置、验证状态和加密 Key 均保持可用，用户无需重新填写
- **AND** 主密钥缺失或不匹配时系统必须明确报错，不得把连接静默显示为未配置

#### Scenario: Load and test an LLM model

- **WHEN** 管理员打开模型选择器并点击“实测模型”
- **THEN** 页面从服务端当前目录展示已登记供应商型号，兼容网关允许输入准确 Model ID，并通过现有 LLM 诊断能力发送一次明确提示可能计费的最小真实请求；结果展示脱敏诊断 ID 与首 Token 耗时，失败展示分类错误，且不得以本地型号匹配冒充真实验证
- **AND** 模型验证不得自动填写或改写价格字段，价格同步和人工确认仍是独立流程

#### Scenario: Reuse a saved Bot provider connection

- **WHEN** 当前账号已有同厂商、同规范化 Base URL 且包含加密 Key 的 Bot 连接，并选择服务端目录内的另一个型号
- **THEN** “实测模型” MUST 通过 `bot_id` 复用该连接的加密 Key，并以 `llm_model` 临时覆盖为所选型号，不得修改原 Bot 配置或要求用户重复填写 Key；厂商或 Base URL 不匹配时不得复用
- **AND** 输入 `Gemini/gemini-3.8-flash` MUST 规范为 `gemini-3.8-flash`，服务端目录 MUST 包含该正式型号

### Requirement: Verified asynchronous ASR capabilities

系统 MUST 为 Soniox `stt-async-v5`、Speechmatics `melia-1` batch/multi 和 ElevenLabs `scribe_v2` webhook 分别维护 Endpoint、模型参数、输入约束、验证状态和最近验证时间。只有验证成功且未停用的能力可供新批次选择。

#### Scenario: Validate with real mixed-language audio

- **WHEN** 管理员验证 ElevenLabs 能力
- **THEN** 测试覆盖真实英阿混合录音的异步提交、自动/多语种识别、时间戳、说话人分段、轮询或 webhook 和重试

#### Scenario: Capability configuration changes

- **WHEN** Endpoint、Key 或模型参数变化
- **THEN** 能力状态变为待复验，在重新成功验证前不得作为可用资源加入新批次

### Requirement: Per-batch resource selection

新建批次 MUST 默认继承全局资源配置，并允许本批次选择一个或多个已验证异步 ASR、第一轮 LLM 和第二轮 LLM。批次开始后所选 provider/model/capability 版本 MUST 冻结。

系统 MUST 持久化维护评测 LLM 模型目录。管理员输入的自定义 Model ID 只能在一次显式、最小且成功的真实诊断请求后写入目录；仅输入、诊断失败或未知厂商 Endpoint MUST NOT 写入。目录不得保存 API Key，已验证型号 MUST 在后续新建批次的两轮 LLM 选择器中可用。

模型选择值 MUST 同时标识 provider 与 Model ID；Azure deployment、OpenRouter model slug 与其他资源出现同名 Model ID 时不得串用连接、价格或执行适配器。

#### Scenario: Select a single evaluation ASR

- **WHEN** 用户只选择一家已验证评测 ASR且两轮 LLM 均有效
- **THEN** 系统允许创建批次，但第二轮仍需满足证据准入规则，证据不足时进入人工复核

#### Scenario: Register a verified custom LLM model

- **WHEN** 管理员在成本配置输入自定义 Model ID 并主动点击真实测试，且厂商返回成功响应
- **THEN** 系统幂等写入厂商、Model ID、非敏感 Endpoint 主机、诊断 ID 和验证时间，并立即使其可供新批次选择

#### Scenario: Reject an unverified custom LLM model

- **WHEN** 自定义 Model ID 诊断失败、未执行诊断或无法归属到支持的评测厂商
- **THEN** 系统不写入模型目录，也不在新批次中展示该型号

### Requirement: Versioned prices and hard budget

系统 MUST 支持维护默认批次预算、每家异步 ASR 的计费单位与价格，以及两轮 LLM 的输入、缓存输入和输出 Token 价格。价格编辑 MUST 生成新版本且不得重算历史批次。

供新批次选择的 LLM 型号 MUST 在当前价格版本中具有同厂商、同 Model ID 的价格；仅验证连接或模型可用性不得绕过价格完整性校验。

预算 MUST 作为费用止损上限而非费用预测；新建批次页面 MUST NOT 展示不可靠的成本预估。单批次默认上限为 10 美元，用户设置不得在未额外授权时高于 10 美元。

人民币报价 MUST 保留人民币原始金额，并由价格版本冻结一条经管理员确认的人民币兑美元汇率。批次使用冻结汇率执行统一美元预算门禁，同时 MUST 展示原币金额、汇率版本与折算美元金额；后续汇率版本不得重算历史批次。

#### Scenario: Freeze a mixed-currency pricing version

- **WHEN** 管理员确认人民币兑美元汇率并保存新价格版本
- **THEN** 后续新批次冻结该版本，Qwen 人民币费用保留原值并按冻结汇率折算到美元预算，历史批次不变

#### Scenario: Synchronize a model price

- **WHEN** 管理员从官网目录同步或手填某具体 Model ID 的价格
- **THEN** 页面展示来源和更新时间并要求人工确认，保存后形成新价格版本

#### Scenario: View historical cost

- **WHEN** 用户查看历史批次
- **THEN** 页面使用其冻结价格版本展示核算费用，不因当前价格变化而改写历史金额
