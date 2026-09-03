# Tasks

- [x] 用户确认保留 `.xlsx` 正式归档，并同步输出 VS Code 友好的 UTF-8 CSV
- [x] 用户确认历史日志全部保留
- [x] 用户确认删除旧辅助分析脚本
- [x] 用户确认 `library_ar/asr_char_accuracy.py` 逻辑保持不变并作为当前统一口径
- [x] 建立现有 vendor 文件迁移清单，标注目标路径和保留/清理原因
- [x] 统一各 vendor 入口名为 `test_single.py` 和 `test_batch.py`
- [x] 删除 vendor 目录中的旧辅助分析脚本
- [x] 让 vendor 批量入口调用目标 library 已有的字准率脚本
- [x] 后续 library 缺少字准率脚本时先询问用户，再在该 library 内补写
- [x] 合并 `logs_batch/` 到 `logs/`，处理重名且保留历史记录
- [x] 删除 `scripts/vendor/` 下的历史 CSV，不迁移旧结果
- [x] 实现按自然日增量合并并覆盖同一组 `.xlsx`、明细 CSV、汇总 CSV
- [x] 在 `.xlsx` 中写入 library 现有脚本计算出的逐条/整体指标
- [x] 验证 Benchmark ID 通过清单音频路径正确关联
- [x] 验证失败/跳过不中断批次，汇总口径正确
- [x] 清理 `__pycache__`、`.pyc` 和确认无用的中间产物
- [x] 运行语法检查、`--help` 和小样本/mock 批量测试
- [x] 更新相关工程文档并记录未迁移文件与剩余风险
