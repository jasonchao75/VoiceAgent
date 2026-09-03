# Tasks: Add Call History and Metrics

## 1. Persistence

- [x] 1.1 定义 call、turn、metric、recording 模型和异步 SQLite schema
- [x] 1.2 实现 HistoryStore CRUD、分页和幂等初始化
- [x] 1.3 实现保留期、有效录音配额和最低剩余空间配置校验
- [x] 1.4 实现可重复执行的过期/超额清理服务

## 2. Pipeline Capture

- [x] 2.1 捕获最终 ASR 和完整 LLM 回复并按 turn 持久化
- [x] 2.2 实现用户上行音频有界队列与后台 FLAC writer
- [x] 2.3 录音失败时安全降级并记录不可用原因
- [x] 2.4 捕获 LLM、TTS、浏览器播放时间点并计算定义明确的指标
- [x] 2.5 接入 LLM diagnostic category 与 `diagnostic_id`
- [x] 2.6 按轮保存 reasoning token 数量、关闭策略和验证状态，不保存思考正文

## 3. API and Frontend

- [x] 3.1 实现历史列表、详情、录音流式读取和删除 API
- [x] 3.2 API 沿用 Basic Auth，隐藏文件路径、token、Key 和敏感内部字段
- [x] 3.3 新增 History 列表与通话详情页面
- [x] 3.4 展示逐轮文本、错误、指标定义、缺失状态和录音播放器
- [x] 3.5 开始通话前展示录音与文本保留提示，删除操作二次确认

## 4. Retention and Benchmark Metadata

- [x] 4.1 默认文本/指标保留 30 天、录音保留 7 天
- [x] 4.2 默认录音上限为 5GB 与数据卷容量 20% 的较小值，并保留 1GB 空间
- [x] 4.3 保存未来 ASR Benchmark 筛选所需的音频与模型元数据
- [ ] 4.4 更新 `.env.example`、compose、运行手册和容量估算说明

## 5. Automated Verification

- [ ] 5.1 测试历史 CRUD、分页、级联删除和应用重启持久化
- [ ] 5.2 测试录音格式、音频关联、队列溢出和磁盘失败降级
- [ ] 5.3 测试保留期、容量淘汰顺序、最低空间和清理幂等性
- [ ] 5.4 测试逐轮文本聚合与四类延迟口径
- [ ] 5.5 扫描 API、日志、SQLite、文件名和前端存储，确认无 Key/token 泄漏
- [x] 5.6 运行 format、lint、typecheck、后端测试和前端 build
- [x] 5.7 修复 Flux ASR final 口径、跨轮残留 frame 污染和缺失原因展示

## 6. Acceptance and Joint Deployment

- [ ] 6.1 本地完成多轮通话、历史回看、播放、删除和重启验收
- [ ] 6.2 验证磁盘不足不影响实时通话，并清理所有临时录音/数据库
- [ ] 6.3 部署前只读确认服务器磁盘总量、剩余空间和 `/data` 用量
- [ ] 6.4 与 LLM diagnostics Change 合并后执行一次统一部署
- [ ] 6.5 公网完成真实通话、错误诊断、历史记录、录音和指标验收
- [ ] 6.6 运行远端健康检查，确认 CI/CD 全绿并记录剩余风险
- [ ] 6.7 合并 Delta Specs 到主规格并归档 Change
