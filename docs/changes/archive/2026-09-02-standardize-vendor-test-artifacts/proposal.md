# standardize-vendor-test-artifacts

## Why（为什么要做）

当前 `scripts/vendor/<vendor>/` 同时混放测试脚本、辅助脚本、CSV 结果、缓存和多套日志目录，批量测试结果也没有按 benchmark library 和运行批次统一归档，导致脚本职责、结果追溯和供应商横向对比不清晰。

## What（这次要做什么）

- 将每个供应商目录收敛为单条测试脚本、批量测试脚本和 `logs/`。
- 将数据处理、WER 计算等通用辅助脚本迁出供应商目录。
- 将批量测试结果统一输出为 Excel，并按 benchmark library、供应商和运行时间归档。
- 统一结果字段、时间戳、覆盖策略和失败记录规则。
- 删除 vendor 目录中的历史 CSV；历史日志完整保留并统一归位。

## Out of Scope（这次明确不做什么）

- 不修改厂商 ASR 参数、模型、鉴权或识别逻辑。
- 不重新运行历史音频。
- 不改 benchmark 标注文本和音频文件。
- 不引入新的生产依赖；如生成 `.xlsx` 缺少现成依赖，需另行确认。

## Pending Decisions（待确认）

- 供应商专用的数据清洗/分析脚本是否允许迁到 `scripts/evaluation/<vendor>/`。本 Change 暂按允许迁移设计。

## Confirmed Decisions（已确认）

- 批量测试结果必须生成真正的 `.xlsx` 作为正式归档，并同步生成 UTF-8 CSV 明细和汇总文件，方便在 VS Code 中直接查看与比较；CSV 不替代 `.xlsx`。
- 历史日志必须全部保留，并统一归入各 vendor 的 `logs/`。
- 当前所有阿拉伯语 ASR 字准率统一使用 `benchmarks/library_ar/asr_char_accuracy.py` 和同目录说明文档，不修改其计算逻辑。
- 后续每个 benchmark library 应在自身目录保存适用的字准率计算脚本；缺少时必须先询问用户，再补写实现。
