# Vendor Evaluation Artifacts Specification

## Purpose

定义 ASR 厂商测试脚本、日志和 Benchmark 结果的统一存放及计算约束。

## Requirements

### Requirement: Vendor script directory boundary

`scripts/vendor/<vendor>/` 只能保存单条测试脚本、批量测试脚本和 `logs/`；结果表格与独立评测算法不得放入该目录。

#### Scenario: Batch evaluation finishes

- **WHEN** 厂商批量测试产生逐条结果和汇总指标
- **THEN** 结果写入对应 `benchmarks/<library>/test-results/<vendor>/`，日志写入厂商 `logs/`

### Requirement: Daily result merge

每个 vendor、library 和自然日必须只维护一组 XLSX、明细 CSV 与汇总 CSV；同日重复运行按 `benchmark_id` 增量合并，重复 ID 使用最新结果覆盖。

#### Scenario: Repeat a benchmark on the same day

- **WHEN** 当日结果中已经存在相同 `benchmark_id`
- **THEN** 系统用最新结果原子覆盖该记录，不创建另一组结果文件

### Requirement: Library-owned accuracy rules

字准率计算必须使用目标 library 自己的脚本和口径。目标 library 缺少计算规则时，必须先取得用户确认，不得静默复用其他语料库算法。

#### Scenario: Evaluate library_ar

- **WHEN** 计算 `library_ar` 的 ASR 字准率
- **THEN** 直接使用 `benchmarks/library_ar/asr_char_accuracy.py` 及同目录说明
