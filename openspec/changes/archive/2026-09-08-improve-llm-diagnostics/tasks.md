# Tasks: Improve LLM Diagnostics

## 1. Models and Service

- [x] 1.1 定义诊断请求、成功响应和安全错误响应模型
- [x] 1.2 实现异步最小流式 LLM 探测服务并显式设置超时
- [x] 1.3 实现统一异常分类与脱敏逻辑
- [x] 1.4 为每次探测和运行时故障生成 `diagnostic_id`
- [x] 1.5 定义 `reasoning_mode=lowest_latency`、provider/model 能力映射和验证状态模型
- [x] 1.6 采集流式 usage 中的 reasoning tokens，并只检测、不保存 reasoning 内容字段
- [x] 1.7 扩展固定资源方 Catalog：最低 reasoning 档、参数映射、证据能力和验证日期
- [x] 1.8 把 Google Gemini 加入固定 Provider Catalog，并加入首批稳定 Flash/Flash-Lite 模型档案
- [x] 1.9 新增 Pipecat `google` extra 生产依赖并验证锁定依赖

## 2. API and Runtime

- [x] 2.1 实现 saved-key Bot、BYOK Bot 和 Quick start 的诊断入口
- [x] 2.2 复用现有 Catalog、Origin、Key 解密和占位符校验
- [x] 2.3 将正式会话 LLM 异常接入同一分类器
- [x] 2.4 提供会话结束后短时可读取的安全诊断摘要并自动过期
- [x] 2.5 Bot、Quick start 和正式会话默认解析并应用最低思考档
- [x] 2.6 对无法关闭或检测到思考的模型告警；对无法验证的 Custom endpoint 实现用户确认后继续规则
- [x] 2.7 为现有 Bot 幂等增加 `reasoning_mode` 字段并默认回填 `lowest_latency`
- [x] 2.8 实现原生 Gemini adapter factory，与 OpenAI-compatible 路径共享统一 LLM 接口
- [x] 2.9 分别映射 Gemini 2.5 `thinking_budget=0` 与 3.x 最低 `thinking_level`

## 3. Frontend

- [x] 3.1 在 Bot 编辑器和 Quick start 增加 LLM 连通性测试按钮
- [x] 3.2 测试前提示会产生一次极小的真实厂商请求
- [x] 3.3 展示类别、配置摘要、耗时、建议动作和 `diagnostic_id`
- [x] 3.4 正式会话失败后自动展示安全诊断结果
- [x] 3.5 展示最低延迟请求、实际档位、reasoning token 数量和五态验证结论
- [ ] 3.6 正式会话检测到 reasoning tokens 时按轮显示延迟风险告警
- [x] 3.7 Gemini 使用固定模型下拉框并隐藏可编辑 Base URL
- [x] 3.7 为 `unverified` Custom endpoint 增加明确的风险确认交互

## 4. Automated Verification

- [ ] 4.1 覆盖成功、鉴权、模型、限流、超时、连接和未知错误分类
- [ ] 4.2 验证 saved-key 与 BYOK Key 生命周期及响应/日志无泄漏
- [x] 4.3 验证普通会话、Bot CRUD、Basic Auth 和会话 token 不回归
- [x] 4.4 运行 format、lint、typecheck、后端测试和前端 build
- [ ] 4.5 覆盖非推理、支持 none、无法关闭、检测到思考和证据缺失场景
- [ ] 4.6 验证 reasoning 内容正文不进入响应、日志、SQLite 或浏览器存储
- [ ] 4.7 覆盖 Gemini 2.5/3.x 参数映射、原生流式响应、usage 和依赖缺失错误

## 5. Acceptance and Delivery

- [ ] 5.1 本地使用 mock 完成所有诊断路径验收
- [ ] 5.2 用户确认后使用真实 LLM Key 执行最小连通性验证
- [ ] 5.3 使用用户 Gemini Key 验证固定模型可用性、最低思考档与首 Token 延迟
- [ ] 5.4 与 call history Change 合并后执行一次统一公网部署
- [ ] 5.5 公网验证页面诊断、真实会话错误展示和日志脱敏
- [ ] 5.6 合并 Delta Specs 到主规格并归档 Change
