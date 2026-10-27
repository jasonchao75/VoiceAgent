# 研发自测报告 — 第二十八轮正式页面键盘与可访问状态

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 本轮仅改正式配置组件及回归，不新增页面/控件或修改冻结原型。

- 正式TD/Jev子页按钮原仅CSS标记选中，屏幕阅读器无状态。缺行为浏览器两项目先红；修复为aria-pressed，Advanced层级增加aria-current，保留原CSS高亮规则。验证空格切VAD、回车返回Semantic、当前子页状态及可见内容对应。
- 正式配置/历史/实际AudioWorklet **12 passed / 11.1秒**为修复前基础回归；修复后同12项通过，最终保持原CSS规则后另行重跑配置两项目 **2 passed / 3.8秒**，见[navigation-final.txt](development-20261022-r28/navigation-final.txt)。不是完整键盘/屏幕阅读器/可访问性通过。build通过。
- 证据见[本轮目录](development-20261022-r28/)。既有截图输出到r9/r21页面证据目录；冻结prototypes未改。新增本机Vite进程使用5175（5174原有进程仍占用），验证后已停止新增5175进程；API全部测试拦截，未调用厂商。

仍未完成：未知来源/非法范围/跨连接恢复、RTC编号缓存串行组合/精确回执、精确指标、完整UI状态与视觉/可访问性、真实六模型/厂商/弱网/手机/实机AEC。最近全后端r25为591项，r26/r27后端增量未全量重跑。本轮不宣称M1—M5完整或提交独立审核，无Gate 2/提交推送部署合并归档。原隔离/tmp数据与忽略的NLTK资源保持原状。
