# 研发交包要求逐项核对（r89，2026-10-26）

核对对象是用户明确要求的“可供独立审核的实现与自测包”，不把开发交包定义成产品最终验收。用户同时要求列剩余问题/未验证范围；D045允许当前无麦克风时物理部分待验证，真实新批次需逐次授权，D068保留开发候选/默认采用决定。因此这些边界以明确未验证交审核，而不伪造通过或无限等待最终PASS再交包。

| 原始要求/不变量 | 当前权威证据/结果 |
|---|---|
| 项目AGENTS、change-delivery-guard、主规格/Delta/design/tasks/handoff/附录/自测/decisions先读 | 项目导航/现行D048—080及canonical skill已执行；关键行为/例外在Spec与决策，不借历史建议替用户确认。open-questions当前0，不重复问已确认规则 |
| 冻结v0.14及工作区保护 | frozen-baseline-check.json匹配唯一D048 SHA；source-delta-from-r88.json仅5个预期reader/测试/fixture差异，其余共享src/frontend/tests未改；最终包snapshot定义未提交版本，不冒称所有上下文归本Change |
| 开工/里程碑/交前Change门禁 | gate-before/最终gate-final实际退出结果；只结构通过，不代替行为、独立C或Gate2 |
| M1范围/版本/唯一提交/未知与重连边界 | 68个精确Delta场景→存在且JUnit执行的选择器（delta-scenario-map）；22ID矩阵明确fixture/local/external等级。缺来源D061有界失败不猜，不承诺未实测真实重连 |
| M2等待/Jev异常/续说竞争/唯一提交 | 当前756含独立Tmax、慢/错误Jev、并发修订、D080新target不被旧窗绕过；每通严格RTC仅一个td_commit；D049有效Final一律重答，无实质改义判断 |
| M3严格编号/受控工具/幂等/播放仲裁 | 当前756含纯本地、混合整体LLM工具、中英业务WPM、代次/成功/提醒/旧修订；r88实际回执响应丢失+遥测挂起有界关闭、不伪造stop/新答开播；r69/r83编号实际串行证据复用，不改默认传输 |
| M4缓存/发布/故障/历史真实 | r83公开入口缓存修复成功/失败继续及发布配置固定；756相关缓存/SDK停止保护；当前r89源→渲染证据、两响应、重启原样、正式Sessions 1440/390实际API范围展示/故障恢复/无溢出 |
| 正式页面冻结原型/A/B，禁另造验收页/配置后端演示 | r82 A及r84 B矩阵为同正式路由/组件DOM；r88完整性字段真实页面1440/390修复；本轮无配置新控件/新规则演示/冻结HTML改动，r89只reader观察与对应测试/fixture |
| SDD＋TDD，失败先复现 | 原r87新增3后端/RTC挂起/字段红灯保留；r88 6返修及独立Resolved；本轮late-track-red两实际SDK红灯→resampler原入口修复→19研发/21独立及严格冷暖实证。无效诊断及Ruff首失败也保留，不伪造根因 |
| Final不丢否定、不重放工具、不串轮 | test_td_review_regressions/test_td_runtime/test_td_tool_scope及实际严格Final两响应；跨范围词覆盖不足返回未知，原Final不按缺词表损坏重建 |
| 真实厂商授权与费用边界 | delivery-status.external_calls、D053/D065/D075—079及r85六模型基本矩阵。已消费只记实际结果/估算，不冒充实际账单；本轮0新费用/0客户数据，不复用旧授权 |
| 完整当前软件回归/运行版本 | backend-junit 756零失败/错误/跳过，client25，Ruff、实际3.13 mypy79及Vite通过；runtime-versions精确Python/Node/依赖/HEAD，.githooks已配置；3.11未验证保留 |
| 交付报告/场景映射/实际命令/事件/证据/剩余与回退 | canonical self-test-report、22ID matrix、68Scenario map、r89 README/JSON/日志/截图/版本/临时数据与默认开关回退，交包归档按SHA可复现；独立r88/r89报告非开发自评 |
| 剩余失败与真实性 | 原r88红灯不删；历史当次缺native快照不能唯一归因；探针slots错误0不当prod事实；故障遥测未送达时history可能completed/未知stop，不声称确定失败原因。当前确认实现缺陷均有独立关闭依据，剩余范围明确列未验证 |
| 不新增服务端AEC、不自行换架构/默认采用/提交推送部署/合主规格归档 | RTP/原音轨保持；默认candidate=False；当前仅未提交工作区自测包，product_acceptance仍pending，独立全Change PASS/C/Gate2未填 |
| 交回独立Codex | repair-review-r88/r89已由未参与实现者复核，最后包逐hash核对；这交付开发实现/自测输入，完整产品审核仍可要求补证，开发不代签接受 |

机器存在性/实际JUnit/事件核对见completion-audit.json。UI/厂商/硬件证据等级及未验证不会因本表改写为通过。最终包与外层后补hash报告冻结点明确，不能把文档补记当新源码重测。

独立目录包闭包补充：初始归档漏两个Vite入口的失败已发现并修复，非工作区源码缺失；独立目录126核心后端/25客户端/完整构建实际通过，package-reproduction-check.json逐输入SHA与最终归档清单再核。前置安装失败/缓存权限边界保留，未改锁文件或原缓存权限。
