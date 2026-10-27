# 研发自测报告 — 第二十二轮旧历史语言与任务证据审计

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** 前轮逐轮历史/RTC/完整自测历史见[self-test-report.round21.md](self-test-report.round21.md)。

- 旧会话复用原对话和指标渲染，补语言控件；对话literal保护，缺TD证据仍明确未采集，旧指标不重算。重复关闭/打开详情只有一个控件。逐轮历史动态候选状态和回复标签按UI片段翻译，来源ID保留。先红后绿，最终桌面/窄屏项目含1440/390固定视口8 passed / 7.9秒，Node4、构建和diff检查通过。[证据](development-20261022-r22/)。
- 对M2重新按任务语义审计，定向64 passed / 1.98秒、2依赖弃用警告；仅勾M2-2/3/5实现/离线子任务，详见[任务证据矩阵](task-evidence-matrix.md)。M2整体仍未完成，不把MockTransport/SDK证明当真实厂商或硬件事实。

未闭环：RTC精确任务回执和编号/缓存仲裁组合；精确渲染时钟指标；未知ASR范围/重连和真实六模型；完整UI状态/动态文案/视觉diff/可访问性；真实厂商、弱网和实机AEC。无新增产品决定，无真实Key使用/付费推理，无独立PASS/Gate2/提交/推送/部署/主规格合并/归档。隔离服务8765/5174、/tmp/voiceagent-td-r15测试数据与忽略的.venv/nltk_data资源保留。
