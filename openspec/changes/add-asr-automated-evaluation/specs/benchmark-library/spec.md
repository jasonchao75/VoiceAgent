# Delta: Benchmark Library

## Purpose

定义 ASR 自动化评测产生的正式 Benchmark 样本、追溯、下载、留存和审计规则。

## ADDED Requirements

### Requirement: Evidence-gated idempotent ingestion

第二轮明确 Good/Bad 且满足自动准入规则的 Case MUST 以 `AI 标注`进入正式 Benchmark；人工提交 Good/Bad 的 Case MUST 以 `人工标注`进入。正式 Library 的唯一约束 MUST 以 conversation ID 和 event ID 为业务键且跨批次生效；batch ID 只作为证据来源，不得参与判断样本是否重复。重试、重复 webhook、恢复运行、人工复核和后续批次再次命中同一事件时都不得产生第二条样本。

#### Scenario: Automatically ingest a clear case

- **WHEN** 第二轮输出满足准入规则的 Good 或 Bad
- **THEN** 系统创建或返回同一 Benchmark 样本，保存 AI 标注来源及批次证据快照

#### Scenario: Reuse the same event across batches

- **GIVEN** Library 已存在某 conversation ID + event ID 的正式样本
- **WHEN** 后续批次再次准入同一事件且结果与当前样本一致
- **THEN** 系统返回原 Benchmark ID、追加可追溯的批次证据且不得增加 Library 样本数

#### Scenario: Block a conflicting duplicate

- **GIVEN** Library 已存在某 conversation ID + event ID 的正式样本
- **WHEN** 后续批次产生不同 Good/Bad、标注文本或音频证据
- **THEN** 系统直接丢弃新 Benchmark 候选，不得创建第二条样本、覆盖当前值、追加修订或创建人工冲突复核任务
- **AND** 原样本的当前值、修订历史和导出内容保持不变，新批次的 Benchmark 新增数不得包含该候选

#### Scenario: Ingest a reviewed case

- **WHEN** 人工复核明确提交 Good 或带非空正确文本的 Bad
- **THEN** 系统创建或更新该 Case 对应样本，标注来源为人工标注，并保留原 AI 建议而不覆盖证据历史

#### Scenario: Exclude an unclear case

- **WHEN** 人工将 Case 提交为听不清
- **THEN** 系统不创建 Benchmark 样本；若此前仅有待定候选则将其排除，保留已复核和排除原因审计记录

### Requirement: Benchmark sample content

每个正式样本 MUST 包含 Benchmark ID、Good/Bad、语种、场景标签、纯用户 WAV 片段、历史转写、最终标注文本、标注来源、统一时间范围、定位精度和追溯信息。不得使用完整通话 MP3 代替用户 Benchmark 音频。

### Requirement: Delete one Benchmark sample

Benchmark Library MUST 在列表和样本详情提供单条删除入口。用户二次确认后，系统 MUST 原子删除该 Benchmark 当前记录与修订，并删除其位于托管 Benchmark 目录内的派生 WAV；不得提供批量删除或恢复入口。源对话、源批次、报告、人工复核与其他 Benchmark MUST 保留，系统 MUST 写入不含客户文本或音频路径的删除审计墓碑。

#### Scenario: Confirm deletion from the list or detail

- **WHEN** 用户从列表或详情对一个 Benchmark 样本确认删除
- **THEN** 该样本立即从列表、筛选、汇总和后续导出中消失，其详情、修订和音频不可再访问；源对话、批次、报告和人工复核保持可访问

#### Scenario: Cancel Benchmark deletion

- **WHEN** 用户打开删除确认后取消
- **THEN** 系统不得删除数据库记录、修订或派生 WAV，也不得写入删除审计

#### Scenario: Create a clipped sample

- **WHEN** Case 具有可靠统一时间范围且两类录音时间轴已校验
- **THEN** 系统从 `user_record/{conversation_id}.wav` 截取该范围，保留原始音频属性和片段校验信息

#### Scenario: Use a degraded full recording

- **WHEN** Case 只能可靠定位到完整纯用户录音
- **THEN** 系统可保存完整用户 WAV，但必须把定位精度标记为 full recording，页面不得显示伪造的句子级时间

### Requirement: Immutable trace and editable classification history

样本 MUST 可追溯到源批次、完整 conversation/event ID、输入文件、上下文版本、Prompt 版本、模型、每家 ASR job/segments、第二轮决定、人工复核、标签版本、音频处理参数和入库时间。后续修改语种、标签或人工文本 MUST 形成审计版本，不得删除原值。

#### Scenario: Review sample provenance

- **WHEN** 用户打开 Benchmark 样本详情
- **THEN** 页面可查看纯用户音频、历史转写、最终标注、Good/Bad、来源和完整只读追溯，并可跳转到有权限的源批次与对话

#### Scenario: Read Arabic Benchmark text in Chinese mode

- **WHEN** 用户在中文模式打开 Benchmark Library 当前页或样本详情，且可见历史转写或标注文本包含阿语
- **THEN** 页面按来源批次合并请求其冻结的第一轮 LLM，为当前页最多 20 条可见阿语及详情阿语显示中文对照，同时保留原文；译文只在浏览器会话缓存，不修改、导出或搜索正式 Benchmark 数据

### Requirement: Search, filter and scoped download

Benchmark Library MUST 支持按完整 conversation ID、标注文本、语种、场景、Good/Bad 和 AI/人工来源筛选，并固定每页展示 20 条。用户 MUST 能跨页保留勾选，并可分别下载“已选样本”或“当前全部筛选结果”；“全部筛选结果” MUST 覆盖所有分页，而非仅当前页。

下载产物 MUST 为 ZIP：根目录包含 UTF-8 `benchmark.csv`，音频按 `wav/<language>/<primary-scenario-tag>/<benchmark-id>.wav` 两级分组。目录名 MUST 使用稳定、文件系统安全且不随界面语言变化的语种与标签标识；多标签样本使用其入库时冻结的主场景标签。`benchmark.csv` MUST 至少包含 `audio_path`、`benchmark_id`、`annotated_text`，其中 `audio_path` 与 ZIP 内 WAV 路径逐行一致。

#### Scenario: Download selected samples

- **WHEN** 用户勾选一个或多个可访问样本并发起下载
- **THEN** 系统异步生成只含所选样本的分组 ZIP，`benchmark.csv` 中每行与一个音频文件稳定对应，并记录下载审计

#### Scenario: Download every filtered sample

- **WHEN** 用户设置筛选条件并选择“下载全部筛选结果”
- **THEN** 系统冻结本次筛选快照，异步导出所有分页中的命中样本，并在界面显示导出总数

#### Scenario: Group audio by language and primary scenario tag

- **WHEN** 导出同时包含英语、阿拉伯语及多个场景标签的样本
- **THEN** WAV 文件位于对应的 `wav/<language>/<primary-scenario-tag>/` 目录，文件名为 Benchmark ID，根目录 `benchmark.csv` 给出路径、ID 和标注文本

#### Scenario: A selected audio file is unavailable

- **WHEN** 下载生成时个别样本音频损坏或失效
- **THEN** 系统不得静默遗漏，而是生成 manifest、标明失败样本并向用户展示部分失败

### Requirement: Long-term retention and controlled access

原始评测录音、历史对话和正式 Benchmark MUST 至少保留 10 年，10 年内不得被自动清理、普通历史保留策略或容量保护删除。超过 10 年后的继续保存、归档或删除 MUST 依据届时有效的合规策略并保留审批与操作审计。

#### Scenario: General recording cleanup runs

- **WHEN** VoiceAgent 普通通话历史执行 7 天录音或容量清理
- **THEN** 已导入评测批次和正式 Benchmark 管理的录音不受该清理任务影响

#### Scenario: Access sensitive benchmark data

- **WHEN** 用户查看、播放、下载或修改 Benchmark 或其源录音
- **THEN** 系统验证统一评测权限并记录操作者、时间、对象和动作；短期音频地址不得长期公开

### Requirement: Batch-to-library balance disclosure

Library 和批次报告 MUST 展示每批实际 Good、Bad、听不清排除和未复核数量，以及 Good:Bad 目标和实际比例。额外 Good 样本 MUST 可区分“疑点复判为 Good”和“同对话正常池抽样”。

#### Scenario: Inspect Good sample origin

- **WHEN** 用户查看一个 Good Benchmark 样本
- **THEN** 页面和导出数据明确其来源为疑点复判或额外 Good 抽样，并保留抽样规则版本
