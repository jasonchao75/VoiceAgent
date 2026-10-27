# 研发自测报告 — D-050闭环与音频任务身份增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** Q-041已关闭、Change门禁恢复PASS（0 errors，20 warnings），但M1—M5仍未完成，不申请独立审核/Checkpoint C/User Gate 2。上一轮正式UI初步证据见[self-test-report.round9.md](self-test-report.round9.md)。

## 实际实现与证据

- 用户选择A已记录D-050：正式Jev每会话统一100次，不新增控件。模型缺省即100，旧正数草稿/请求预算规范为100。新Bot不再要求隐藏工程字段；其余TD参数仍须显式填写。
- MockTransport实际记录100次失败后，第101次返回budget_exhausted且HTTP计数仍100；将耗尽客户端接TD，3499ms不提交、3500ms正常最长等待提交。没有外部连接、没有付费调用。
- 正式Advanced fixture省略max_calls仍保存为100、无新增控件，并复跑配置/预览/选项/保存竞争/桌面窄屏检查，**1 passed，2.0秒**：[ui.txt](development-20261021-r10/ui.txt)。
- 音频任务帧类型以不可变类绑定身份，借原有protobuf name传递；实际SDK sender重分块与短尾补齐后，两任务身份仍分别对应原样本，无旧音频误标新任务。native wire兼容性fixture通过，不代表已接客户端。
- 渲染线程worklet已开发、尚未挂正式输出。Node vm fixture的2项quantum测试验证：收包无开播事件、写样本才有任务事件、结束去重、targeted clear只报告128个已渲染样本并移除余下72个、迟到旧包被拒。**这是fixture，不是实际AudioWorklet或硬件播放证据。**
- 全量Python **548 passed，3项依赖弃用警告，32.53秒**：[pytest.txt](development-20261021-r10/pytest.txt)；ruff src/tests通过，mypy相关53源文件通过，JS语法和git diff --check通过。
- 红灯证据保留：缺失统一预算、音频身份模块和worklet。原生输出测试初次未调用实际transport-ready钩子导致目标未注册，修正fixture生命周期后通过，不作为产品红灯。

## 未完成与未验证

1. 音频身份/渲染器仍欠正式tagger、协议解析、任务结束/停止回执和服务端仲裁接入；不能声称真实开播/停止或已进客户端的旧音频被撤回。WS/WebRTC均需完成。
2. 缓存跟读与串行播放、更正补读、旧纯编号改混合句的完整推理、未知范围/重连音频时钟尚未闭环。
3. 正式UI完整状态/缓存交互/真实API持久化刷新重启/中英/视觉diff尚欠，Checkpoint A/B未通过；R9的草稿与缓存交互问题保持Open。
4. 真实六模型、Jev/TTS效果/费用/语言/延迟、物理双讲/AEC、目标资源环境未测。没有真实/收费外部调用，D-050也不是测试费用授权。

原型v0.14字节未改；不填写独立PASS或Gate2，不合并主规格/归档/提交/推送/部署。本机Vite已停止。测试PCM/SQLite仅pytest临时目录；r10日志、Node fixture结果保留，/tmp/jev-r10-*.txt为追溯副本。r10正式页面复测刷新r9同名截图，非修改冻结baseline。无真实录音/厂商合成资源。
