# 研发自测报告 — 第十五轮正式页面增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** M1—M5及UI A/B尚未闭环。前轮记录见[self-test-report.round14.md](self-test-report.round14.md)。

- 修复顶部Publish未接已有发布处理、词表/选项结构变化未推进草稿代次，以及TD局部保存与正式Bot完整PUT契约不符导致422。保存先读取现存配置，保留其他设置与各组件凭证，不从表单覆盖无关草稿。
- 先失败后修复：两轮失败日志保留在[本轮证据](development-20261022-r15/)。最终浏览器 **4 passed / 10.2秒**：缺缓存阻止发布且不自动生成；显式生成后试听双单元时间间隔；保存刷新保留资源SHA版本；成功发布及Bot隔离；慢保存期间删除词表行保留未存状态，再次保存成功且保留ASR/TTS/LLM/Jev密钥标记和其他设置；原本地WS Final取消/实际渲染回执及配置fixture回归。前端构建通过。
- 真实本地UI/API/SQLite/SDK与浏览器音频执行；厂商推理全部替代，测试不使用真实Key，不证明真实厂商或物理听感。完整后端最近574项通过为r13历史结果，本轮未重跑后端全量。
- 用户已配置.env，只核查TYPESAFE_API_KEY唯一非空及Git忽略/未跟踪。未显示密钥、未发外部请求；正式Bot不自动读取它，Key有效性/额度尚未验证，真实测试仍需单批授权。

未闭环：WebRTC任务映射；精确时钟/真实指标；未知ASR范围与重连、真实六模型；完整UI A/B含中英/异常/重启/视觉/可访问性矩阵；外部厂商和实机/AEC。未填独立审核PASS或Gate2，未提交/推送/部署/合并主规格/归档。

隔离测试服务使用127.0.0.1:8765/5174；数据在/tmp/voiceagent-td-r15，仅合成文本、虚构测试凭证和音频，不提交。浏览器临时产物在test-results/playwright，构建产物frontend/dist，均忽略；证据日志留在本Change。本轮未覆盖其他任务已有改动。

追加验证：失败保存时草稿保持、API旧值不变，重试成功后Jev子页旧错误清除，1 passed（先红后绿）；隔离后端进程8888已明确退出，再启动新进程，正式API/页面验证同一Bot配置、四项凭证保存标记、两份缓存版本及WAV可读均保持，重启前后各1 passed。证据restart-before.txt、restart-after.txt、browser-recovery-red.txt及browser-recovery-green.txt。本项覆盖本地重启，不代表完整UI A/B已完成。

追加跨Bot隔离：旧Bot延迟503在切换后污染新Bot错误提示，已先红后绿修复；正式页面6 passed / 11.9秒（重启协调用例在普通套件按设计跳过，单独重启证据已保留）。证据late-failure-red.txt、late-failure-green-suite.txt；JS语法及git diff --check通过。
