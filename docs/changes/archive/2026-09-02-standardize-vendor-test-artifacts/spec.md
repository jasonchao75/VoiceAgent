# Spec: Vendor Test Scripts and Benchmark Results Layout

## 1. 目标目录结构

每个供应商目录必须收敛为：

```text
scripts/vendor/<vendor>/
├── test_single.py
├── test_batch.py
└── logs/
```

每个 benchmark library 的批量结果必须归档为：

```text
benchmarks/<library>/
├── ...原有音频与标注文件
├── <library 自有的字准率计算脚本与说明文档>
└── test-results/
    └── <vendor>/
        ├── <YYYYMMDD>.xlsx
        ├── <YYYYMMDD>.csv
        └── <YYYYMMDD>_summary.csv
```

例如：

```text
benchmarks/library_ar/test-results/speechmatics/20260824.xlsx
benchmarks/library_ar/test-results/speechmatics/20260824.csv
benchmarks/library_ar/test-results/speechmatics/20260824_summary.csv
```

结果日期使用执行机器的本地自然日，格式固定为 `YYYYMMDD`。同一 vendor 在同一天只保留一组结果文件；后续批次按 `benchmark_id` 合并，新 ID 追加，重复 ID 用最新结果覆盖，并重新计算当日汇总。文件写入必须采用临时文件替换，避免中断造成半写文件。日志仍使用 `YYYYMMDD_HHMMSS` 时间戳逐次保留。

## 2. Requirement: Vendor 目录只保留测试入口和日志

`scripts/vendor/<vendor>/` 中只能存在以下内容：

- `test_single.py`：单条音频测试入口。
- `test_batch.py`：读取 benchmark 清单并批量执行的入口。
- `logs/`：单条和批量运行日志。

不得保留 CSV、Excel、`__pycache__`、独立 WER 工具、音频转换工具、数据清洗脚本、分析脚本或第二套日志目录。厂商配置继续放在 `configs/vendor/<vendor>/`，不得迁入脚本目录。

### Scenario: 检查供应商目录

WHEN 检查任一 `scripts/vendor/<vendor>/` 目录  
THEN 顶层只能看到 `test_single.py`、`test_batch.py` 和 `logs/`  
AND `logs/` 中只能保存日志文件及为历史迁移所需的日志子目录  
AND 不得存在结果表格、缓存或 benchmark 数据副本

## 3. Requirement: 辅助逻辑归位

批量测试共享的 Excel 结果导出能力可以放入 `src/evaluation/`。文本归一化、WER/CER 和字准率必须使用目标 library 已有的计算脚本，不得在 vendor 目录保留另一套实现。

单条和批量测试入口可导入上述模块，但入口脚本必须可直接运行。迁移时优先复用现有逻辑，不改变识别参数和评分口径。

### Scenario: 迁移现有辅助脚本

WHEN 现有 vendor 目录包含 `upsample.py`、`wer_calculator.py` 或数据筛选/分析脚本  
THEN 不再需要的辅助脚本直接删除  
AND vendor 测试入口改为使用目标 library 已有的字准率脚本  
AND 对应测试入口的导入路径同步更新  
AND 迁移前后同一输入的核心处理结果一致

## 4. Requirement: 批量测试输入契约

`test_batch.py` 必须以 benchmark library 的清单文件为事实来源，并至少读取：

- Benchmark ID。
- 音频相对路径。
- 人工标注文本。
- 语言或方言字段（如清单提供）。

音频与 Benchmark ID 的关联必须以清单中的音频路径列为准，不得假设音频文件名等于 Benchmark ID。输入路径不存在、标注为空或单条请求失败时，批次不得整体中断，必须在结果中记录失败状态与原因。

### Scenario: 运行 `library_ar`

WHEN 批量脚本读取 `arabic_asr_benchmark_sheet3.csv`  
THEN 使用 `wav` 列定位音频  
AND 使用 `Benchmark ID` 作为结果主键  
AND 不依赖 Saudi 音频文件名与 Benchmark ID 顺序一致  
AND 对没有 `wav` 的记录写入 skipped 状态，不调用供应商 API

## 5. Requirement: 每个 Library 自带字准率规范与实现

当前 `library_ar` 的唯一验收口径为以下两个现有文件：

- `benchmarks/library_ar/asr_char_accuracy.py`
- `benchmarks/library_ar/阿拉伯语ASR字准率计算说明.md`

所有供应商对 `library_ar` 的结果必须统一使用该脚本计算，禁止复制、改写或在 vendor 目录维护另一套归一化与准确率逻辑。脚本已有的 CER、字准率、字符替换/删除/插入、WER、词准确率和负值处理均保持不变。

批量测试结果仍必须保存为 `.xlsx`，并同步保存 UTF-8 编码的明细 CSV 与汇总 CSV。CSV 只是便于 VS Code 查看和版本比较的镜像，不得改变计算口径。明细 CSV 固定且仅包含 `benchmark_id`、`audio_path`、`annotated_text`、`transcript`、`normalized_annotated_text`、`normalized_transcript`、`wer` 七列。如果需要把现有脚本的计算结果写入最终结果，只允许增加调用和文件写入适配层，不得修改 `asr_char_accuracy.py` 内部算法。

### Scenario: 默认读取 Library 评测规则

WHEN 对任一 library 计算 ASR 字准率  
THEN 必须先查找该 library 目录内已有的字准率计算脚本和说明  
AND `library_ar` 必须直接使用现有 `asr_char_accuracy.py`  
AND 不得直接沿用其他 library 或某个 vendor 私有的计算规则

### Scenario: Library 缺少评测规则

WHEN library 缺少字准率计算脚本或口径说明  
THEN 必须停止正式字准率计算并向用户确认指标口径  
AND 获得确认后在该 library 目录补写说明和可运行脚本  
AND 默认参考 `library_ar/asr_char_accuracy.py` 的能力与结构，但不得未经确认直接套用语言相关归一化规则  
AND 完成最小自测后才能生成正式字准率结果  
AND 不得静默猜测归一化、字符切分或异常样本处理规则

### Scenario: 规则说明与实现不一致

WHEN library 的说明文档与计算脚本行为不一致  
THEN 该批结果不得作为正式评测结果  
AND 必须先修正规则或实现并重新计算

## 6. Requirement: Excel 结果规范

每天生成一个 `.xlsx` 正式归档及两个同日期 CSV 镜像；同日后续批次更新这组文件。`.xlsx` 至少包含以下工作表：

- `details`：逐条识别和评分结果。
- `summary`：本批次整体及必要分组统计。
- `run_metadata`：供应商、模型、配置摘要、library、开始/结束时间和脚本版本信息。
- 隐藏状态工作表：保存增量合并所需的完整机器数据，不作为人工查看结果。

`details` 固定且仅包含以下 7 列，并与明细 CSV 完全一致：

- `benchmark_id`
- `audio_path`
- `annotated_text`
- `transcript`
- `normalized_annotated_text`
- `normalized_transcript`
- `wer`

`summary` 至少包含总数、成功数、失败数、跳过数、成功率、整体 WER/CER、整体字准率、平均延迟和 P95 延迟。整体 WER/CER/字准率必须按全语料累计编辑距离计算，不得直接对逐条百分比做算术平均。

### Scenario: 完成批量测试

WHEN 批次执行结束或发生可恢复的单条失败  
THEN 在 `benchmarks/<library>/test-results/<vendor>/` 生成或更新当日 `.xlsx`、明细 `.csv` 和 `_summary.csv`  
AND 结果包含成功、失败和跳过记录  
AND 不在 `scripts/vendor/<vendor>/` 生成 CSV 或 Excel  
AND 新 Benchmark ID 追加、重复 Benchmark ID 以本次结果覆盖  
AND 不创建同日第二组结果文件

## 7. Requirement: 日志规范

单条和批量测试日志统一写入 `scripts/vendor/<vendor>/logs/`。文件名必须包含测试类型和时间戳：

- `single_<YYYYMMDD_HHMMSS>.log`
- `batch_<library>_<YYYYMMDD_HHMMSS>.log`

日志可记录 Benchmark ID、阶段、耗时、状态和脱敏后的错误，但不得记录 API Key、Token 或其他凭证。日志不得作为最终指标来源；`.xlsx` 为正式归档，CSV 为同批次可读镜像。

## 8. Requirement: 历史文件处理

现有 `scripts/vendor/` 内的历史结果 CSV 不迁移，必须删除。该规则只适用于 vendor 脚本目录中的历史输出，不得删除 `benchmarks/<library>/` 下的 benchmark 原始清单。

现有 `logs_batch/` 日志必须全部合并进 `logs/`；文件同名时不得覆盖。`__pycache__` 和 `.pyc` 属于可再生缓存，应清理且保持 Git 忽略。

### Scenario: 清理历史 CSV

WHEN `scripts/vendor/<vendor>/` 中存在历史 CSV  
THEN 删除该 CSV  
AND 不迁移到 benchmark library  
AND 不得影响 benchmark 原始清单和历史日志

## 9. 验收标准

- 所有 vendor 目录满足第 1 节结构约束。
- 所有测试入口通过语法检查，且 `--help` 可正常执行。
- 使用小样本或 mock 完成一次批量测试，生成结构和字段合规的 `.xlsx`、明细 CSV 与汇总 CSV。
- 每个参与评测的 library 均有明确的字准率计算脚本和说明文档。
- `library_ar/asr_char_accuracy.py --self-test` 通过，且文件逻辑未被修改。
- 验证批量结果按 library 现有脚本生成逐条与整体准确率。
- 验证缺失音频、空路径和供应商调用失败不会中止整个批次。
- 验证同日结果按 Benchmark ID 正确追加/覆盖且不新增文件，日志不包含凭证。
- 汇报已删除的历史 CSV、保留的历史日志和测试产生的临时文件。

## 10. 已确认补充

- 不保留 vendor 目录中的旧辅助分析脚本。
- `library_ar` 的准确率算法、归一化、字段和负值处理全部以现有脚本为准，不另行设计。
