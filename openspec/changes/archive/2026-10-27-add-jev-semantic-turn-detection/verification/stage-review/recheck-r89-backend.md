# r89 后端独立复核（2026-10-26）

**结论：原 B1、B2、B3 均支持关闭；本次定向审查未发现新增确认后端缺陷。** 此为后端修复及相关回归结论，不是整个 Change/Checkpoint C/User Gate2 的 PASS。遵循 change-verifier；未修改生产代码或现有测试，没有外部调用。

## 代码与契约核对

| 原问题 | 当前实现与结论 |
|---|---|
| B1 英文片段拼坏 | `src/asr/transcript.py:153–208` 的 `join_source_segments` 区分独立片段与 Soniox token，保留已有空白，数字与 CJK 不盲加空格；词时间切片使用全文覆盖后的原文位置。`custom_td.py:325` 的待处理混合范围也使用同一拼接。原 Nova one/two 适配器入口复现恢复为可识别的12，已关闭。 |
| B2 不完整词时间使否定丢失 | `src/asr/transcript.py:314` 跨范围解析先检可靠时间和 `words_cover_text`，再检查边界及原文切片；缺 do/not 时间返回 None，不生成错误 Final。完整同范围 Final 保留全文，不错误要求不必要的词切片；已关闭。 |
| B3 旧 Final 截止绕过新目标 | `src/pipeline/turn_detection.py:203–212` 在每次非最长兜底提交前检查当前目标，而非只在 Final 窗口开始前检查。旧窗口保留但不能提前授权新文字，新目标2000ms在800/1999ms均不提交；2000ms不重复增加Final等待，无新Jev结果到原2500ms才兜底。符合本轮已确认D-080；已关闭。 |

已读取本Change相关Delta、D-080确认及现有假设、r88修复报告，并检查归一化→ledger→普通/编号路由→Final重答调用点。没有依据已过期旧报告继续将已修复问题列为当前缺陷。

## 本次独立执行

1. 原审查复现 + 转写/计时/编号/工具/修订：

```sh
.venv/bin/python -m pytest -q openspec/changes/add-jev-semantic-turn-detection/verification/stage-review/backend_repros_20261026.py tests/test_td_transcript.py tests/test_td_timing.py tests/test_td_identifier.py tests/test_td_identifier_tools.py tests/test_td_tool_scope.py tests/test_td_response_revision.py
```

**77 passed，1条已安装SDK弃用警告，0.90秒。**

2. 新增正式回归 + SDK集成相关路径：

```sh
.venv/bin/python -m pytest -q tests/test_td_review_regressions.py tests/test_td_runtime.py tests/test_td_identifier_pipeline.py tests/test_td_asr_events.py
```

**107 passed，1条同类警告，2.07秒。** 两组测试文件互不重叠，但原3条审查复现与已晋升正式回归在行为上重合，不能把数量当独立场景覆盖。

3. `python3 scripts/quality/verify_change.py add-jev-semantic-turn-detection`：**0 errors /39 warnings，7任务未勾**；结构门禁不代表产品验收。

## 边界

以上为本地Python3.13、真实生产类及SDK/fixture测试；未测试真实厂商新增场景、实际重连、多语种效果、设备声学、手机/弱网、目标Python3.11/1核1GB。未执行UI/RTC分项或全Change独立C，因此不据本报告签用户Gate2。不新增产品问题；原已披露的未验证范围由主审汇总。
