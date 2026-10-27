# r93 严格新镜像／资源限定证据独立复核（2026-10-26）

**限定结论：当前Docker原生排除修复及严格新镜像的1CPU/1GiB离线资源证据相符，未发现新增确认缺陷。全产品仍INSUFFICIENT EVIDENCE，不签完整C、全Change PASS或User Gate2。**

按change-verifier执行，只核`development-20261026-r93/strict/`。根目录初版镜像实验为历史，不混入strict统计。评审未改实现/测试，不调用厂商，不重跑WS或756/25；仅运行获明确允许的9项scratch哨兵测试，并只读inspect本轮两个已停strict容器及strict镜像，未操作旧用户容器。

## 1. 原生Docker语义与修复

旧Gitwildmatch“原四输入缺失”归因已撤回，不能继续引用4红→4绿证明Docker事实。r93原生反例中四输入本来都包含，真正缺陷是父目录例外过宽，导致frontend/.env、node_modules及无关证据哨兵进入上下文。哨兵不是实际密钥；现有记录未发现真实frontend/.env或实际Key泄漏，镜像未推送。

当前`.dockerignore`移除广泛父目录例外，只保留具体文件或明确source/runtime/**路径，并在末尾排除任意层.env/.env.*、node_modules、__pycache__。tests/test_docker_context.py默认skip，须显式环境开关，使用**真实Docker FROM scratch/COPY及local导出**，只在临时目录写无害哨兵，不读取真实.env。

独立实际执行：

```sh
VOICE_AGENT_DOCKER_CONTEXT_TEST=1 /tmp/voiceagent-r91-py311/bin/python -m pytest -q tests/test_docker_context.py
```

**9 passed /1依赖警告/0.40s**。5个必需输入保留、4个私有/生成哨兵排除。研发修前3 failed/6 passed明确失败在frontend/.env、node_modules、无关证据排除，与旧根.env始终排除相符。支持关闭当前R93-DOCKERIGNORE-SEMANTICS；不是一切任意敏感文件绝不进入镜像的无限承诺。

## 2. 严格产物与内核约束

独立只读inspect记录于`stage-review/r93-independent/selected-docker-inspect.json`：

- strict镜像ID：`sha256:92223298f87b16a086451fd91f1fafed1472a8b3495abdc8268d46b36fd727b1`，Linux/arm64；两容器实际Image完全相同。
- `/voiceagent-td-r93-strict-resource`和`/voiceagent-td-r93-strict-silero`均exited、ExitCode0、OOMKilled=false。NanoCpus=1000000000、Memory=MemorySwap=1073741824、CpusetCpus=0。
- 保存的内核`cpu.max=100000 100000`、`memory.max=1073741824`与无swap余量一致；WS运行cgroup memory.peak=187940864字节（179.234375MiB），oom/oom_kill=0。
- WS容器仅127.0.0.1:18993映射，network=bridge，依靠显式应用出站拒绝，**不是内核无网**。Silero容器network=none，无端口。
- 只读mount是本轮本地测试脚本，无真实DB/凭证目录挂载；存储/tmp在tmpfs，不证明磁盘IO性能。D-083仅限定本机Docker/隔离准备，不是部署/推送/收费调用授权。

真实Silero日志显示Python3.11.17、捆绑ONNX模型加载成功，约51.0ms预热和7.85ms处理2秒静音，独立无网任务退出0。继承Web healthcheck的非Web任务Health字段不用于判其模型失败。此任务是批处理静音，不是语音/噪声准确率或和WS同条真实VAD链。

## 3. strict冷暖WS与资源统计

只读核查两个不同call历史：冷`4a142aa6-9855-439c-ab4f-41e18d8fe33f`、暖`0e30f02b-3380-4e52-939d-168539532a88`。每通均td_commit一次、response_restart一次，旧任务实际task_stopped且rendered_samples>0，Final新response1:2实际task_started，两个原响应的E2E范围存在。研发原正式用例各1通过6.5/6.4秒，未重跑。

这是local-real HTTP/WS/SQLite/浏览器Worklet，ASR/Jev/LLM/TTS/**VAD为替身**；配置provider标签不是本次真实厂商调用证明。真实Silero任务独立列示，不能拼成同通话完整真实Silero+供应商效果通过。

独立解析strict 1134条100ms样本，maxRSS=208.37109375MiB、观察窗loop_delay最大11.281792ms、pending/processing采样最大0与summary一致。5项输入hash与当前Dockerfile/.dockerignore/lock/fixture/原生测试相符。RSS与cgroup共享页计费口径不同，不相加；100ms采样0不证明瞬时队列无峰值，不能以窗口最大值或一次冷暖作为P95、并发容量、真实厂商负载或配对新增延迟SLO。

## 4. 准备失败与剩余边界

只读rootfs cp失败、internal网络端口不可达、未被显式lifespan调用的sampler及测试名称筛选未选中均有报告/原件，属于任务执行前置或探针问题；当前strict在完整采样/有效发布端口下复验，不把未执行算通过。Docker启动可能自动恢复旧用户服务是D-083已说明边界；本评审只接触两个记录ID的本轮容器，未对旧容器stop/restart/rm或读取其数据。

当前证据足以支持**严格新镜像在Linux arm64、1CPU/1GiB下运行所列离线资源场景**。仍缺真实厂商并发/完整VAD整链、瞬时队列精确峰值、RTC资源、手机/Safari/VoiceOver/UDP弱网/物理双讲AEC、原链配对增量延迟及x86_64等。没有新增产品决定，不把限定通过提升为全性能、默认RTC采用、完整C/PASS/Gate2。

独立9项及门禁日志在r93-independent；本次没有重打交付包，最终包hash未在本报告核验。
