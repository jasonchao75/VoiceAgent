# r72：历史真实性缺陷修复与 D-072

证据等级：离线。red.txt 实际失败：旧 first_playback 将 TD playback_ms 填为0.0；green.txt 修复后历史23项通过，0.48秒。修复通过 td_commit_ms 隔离所有已提交TD轮，保留旧native行为，不引入跨钟估算。

D-072只批准手机布局B，不是完整UI或产品验收。真实指标、平台/厂商剩余范围仍以总报告为准。没有外部调用，无独立PASS或Gate2。
