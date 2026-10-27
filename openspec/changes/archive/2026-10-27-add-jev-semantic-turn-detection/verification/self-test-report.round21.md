# 研发自测报告 — 第二十一轮正式历史语言增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 原音轨RTC及NLTK资源前轮证据见[self-test-report.round20.md](self-test-report.round20.md)。

- 逐轮TD历史接入现有语言组件，独立唯一控件ID；界面标签与事件字段名翻译，原始对话p、事件值dd显式标记literal并排除翻译，原对象和历史字段不改。测试以实际对话“Advanced settings”、转写“Priority rules”验证与界面词典同名时仍原样保留。
- 先验证历史入口缺失失败，再实现；实际配置/历史/本地WS回归14通过（1项重启协调跳过，独立重启此前通过）；最终历史两个项目包含1440/390固定视口8 passed / 5.1秒。前端Node4通过，构建/diff检查通过。正式中英文历史截图及红绿日志在[本轮证据](development-20261022-r21/)。
- 目视检查390px截图：原对话保留，语言入口与字段翻译显示；部分动态组合标签和历史元信息仍英文，旧会话缺语言入口，完整视觉/可访问性未完成，不标UI A/B通过。冻结原型SHA保持657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4。

未闭环：RTC逐任务精确回执/编号与缓存串行组合、精确渲染时钟指标；未知ASR范围/重连及真实六模型；完整UI语言/状态/视觉/可访问性；真实厂商、弱网/手机/耳机扬声器AEC。无真实Key使用/付费推理，无独立PASS/Gate2/提交/推送/部署/主规格合并/归档。服务8765/5174与/tmp/voiceagent-td-r15隔离数据保留；.venv/nltk_data资源被忽略。
