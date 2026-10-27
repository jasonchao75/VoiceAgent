# 研发自测报告 — 永久缓存与发布增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** M1—M5仍未全部闭环；不申请独立审核、Checkpoint C或User Gate 2。此前编号、工具、时序与范围证据见[self-test-report.round5.md](self-test-report.round5.md)。

## 本轮实现与实际结果

| 场景 | 结果和证据级别 |
|---|---|
| 持久资源/重启 | SQLite元数据、校验和、永久版本PCM；相同有效配置复用，旧配置资源保留。local-real文件/数据库，mock合成 |
| 配置指纹 | 包含有效语音设置与音频格式，排除普通动态语速控制及文本聚合；首次await前深拷贝，避免可变配置漂移 |
| 单项失败/重试 | 独立失败状态、成功不重合成、损坏不可发布；磁盘替换失败记录失败。mock故障 |
| 正式API/试听 | 正式受保护路由返回逐项状态、生成缺失项、校验真实PCM后包装WAV；不下发密钥/内部路径。local-real ASGI/SQLite，mock外部合成 |
| 发布绑定 | 缺失阻止、不合成；绑定固定资源版本；异步校验期间Bot变化则拒绝发布。local-real API/数据库并发测试 |
| 单元合成器 | 使用既有TTS注册表和Pipecat Worker；固定会话语速、sentence聚合、格式检查、显式超时。local-real SDK，mock TTS Processor |
| 运行时准备 | 发布版本/固定会话配置读取或修复，20ms PCM块、仅相邻间隔、重复单元保留；清空后迟到资源不回插。fixture/mock，不证明已接正式输出 |
| Bot来源 | 正式Bot/发布入口将身份绑定Lease；inline配置无此字段。local-real SessionStore/ASGI |

- 全量 **534 passed，3项依赖弃用警告，31.45秒**：[pytest.txt](development-20261021-r6/pytest.txt)。
- ruff src/tests通过；mypy相关50源文件通过；git diff --check通过。证据见[r6](development-20261021-r6/)。
- 缺失模块、API、词表单元边界及配置漂移/写失败的先失败证据已保留。适配器测试夹具最初误用begin_collection和revision=0，修正为有效clear操作后通过；夹具失败不作为功能TDD证据。
- v0.14 SHA-256仍为657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4。

## 未完成与未验证

1. **跟读尚未接正式串行输出。** custom_td仍记录identifier_echo_not_dispatched；预备PCM不等于发送/实际播放。普通与跟读仲裁、实际客户端任务开播/停止、真实取消仍未闭环。
2. 旧编号范围跨新输入/提醒的修订与补读尚未闭环；未知范围与跨连接时间对齐仍未证明。
3. 正式配置/Jev/词表缓存UI与完整历史UI、Checkpoint A/B仍未实现。API测试不替代页面验收。
4. 真实六模型、Jev/TTS效果、读法/连续听感、真实延迟与费用、物理双讲/AEC、目标资源环境未测。没有真实或付费外部请求，不使用Gate1作为费用授权。
5. 全量通过仅证明当前自动化范围；不代表M1—M5完成。未填独立审核PASS、未提交推送部署、未合并主规格或归档。

## 产物

r6证据目录保留日志；临时/tmp/jev-r6-*.txt为红灯追溯副本，未暂存提交。测试PCM/SQLite位于pytest临时目录；没有真实用户录音或厂商合成资源。未启动服务进程。
