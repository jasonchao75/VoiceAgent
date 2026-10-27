# r93 Linux资源限定实测与Docker原生语义纠正（2026-10-26）

D083明确允许启动本机Docker Desktop及隔离测试。已完成**严格新镜像的实际Linux arm64／Python3.11.17／1CPU／1GiB限定资源场景**；不代替全部容量、真实厂商、RTC、手机或声学验收。无新增付费调用、部署、原型/音频架构/默认RTC采用变更，完整C/Gate2仍未通过。

## 当前唯一最终产物与实际结果

最终镜像`voiceagent-td-resource-r93:strict`，实际digest `sha256:92223298f87b16a086451fd91f1fafed1472a8b3495abdc8268d46b36fd727b1`。本目录根部旧初版镜像结果仅历史，当前以**strict/**为准，不把前后不同产物结果混算。

| 限定场景 | 实际结果 | 边界 |
|---|---|---|
| 原生Docker排除规则 | 修前3失败/6通过；修后9通过；标准Dockerfile实际strict构建成功 | scratch构建只复制无害哨兵，不读取真实.env；不是Git规则模拟 |
| 真实本地Silero | 独立无网络容器，1CPU/1GiB，真实捆绑ONNX预热约51.0ms，2秒静音批处理约7.85ms，退出0/无OOM | 非实时匀速输入、非真人/噪声效果，和WS不是同一条推理流水线 |
| 正式WS冷态 | 现有td-runtime.spec.js首条正式路由测试1通过6.5秒 | 真HTTP/WS/存储/浏览器Worklet，ASR/Jev/LLM/TTS/VAD为已标注离线替身 |
| 同进程第二通暖态 | 相同既有测试1通过6.4秒 | 每通唯一提交1次、Final重答1次，旧任务实际停止/新任务实际渲染、来源范围与正式历史恢复检查通过 |
| 内核资源 | cpu.max=`100000 100000`、cpuset=`0`，memory.max=1073741824，无swap余量；memory.peak=187940864（约179.2MiB），oom/oom_kill=0 | SQLite/临时音频在tmpfs，不能代替目标磁盘I/O性能；宿主浏览器不在服务端cgroup；其他旧容器可能争用宿主CPU，不称独占物理机器 |
| 100ms采样 | 1134条，进程maxRSS约208.37MiB、观察窗最大loop延迟约11.28ms，pending/processing采样均0 | RSS与cgroup共享页计费口径不同，不相加；采样0不能证明瞬时队列无峰值；不是新增链路P95或A/B延迟 |

strict/resource-summary.json、strict/voiceagent-r93-strict-kernel.txt保存原始约束；strict/cold、strict/warm包含每通完整白名单历史与源包证据。strict中的镜像构建/脚本/版本/运行日志和内核值可复核。Linux容器为aarch64，不冒充x86_64。Silero批处理容器继承镜像Web healthcheck但不是Web服务，验收看退出0/真实模型结果，不把该非服务health字段当功能错误。

## 更正：r92 Docker“原四输入缺项”判断错误

当时以Gitwildmatch审计Docker父目录否定规则，错误推断demo/evaluation/login和webrtc脚本被排除。**该归因已撤回**，独立报告也保留错误原文并前置更正；不能以旧4红/4绿证明Docker行为。

r93用仅含哨兵的实际Docker scratch context导出证明：原规则与加四行规则输出相同，四输入本来就包含；真实缺陷是`!frontend/`等父目录例外过宽，会包含frontend/.env、node_modules及无关OpenSpec证据。根.env哨兵始终排除。项目frontend没有实际.env文件，未发现真实Key泄漏证据，镜像未推送。docker-ignore-counterexample.json留存两个原生反例，不保存真实.env内容。

修复移除广泛父目录例外，仅保留具体文件或明确/**路径，末尾明确排除任意层.env/.env.*、node_modules、__pycache__。原测试已替换为Docker原生显式开启测试：5个必需输入保留、4个私有/生成输入排除，3红6绿→9绿。全后端默认不会自动启动Docker；需`VOICE_AGENT_DOCKER_CONTEXT_TEST=1`。镜像初版与strict前后都保存，不把BuildKit的缓存增量传输7KB误称整个上下文大小，也不将两版观察窗差异称性能优化。

## 环境与准备失败的分流

- Docker启动按原配置自动恢复`voiceagent-platform-voice-agent-1`并健康；没有对旧容器执行stop/restart/rm或操作其数据。仅本轮新镜像/容器被创建、替换或停止。
- 只读rootfs拒绝docker cp，发生在资源任务启动前；改为仅只读挂载三个本地测试脚本，无真实DB/凭证挂载。原空容器按自建ID清理。
- Docker internal网络使实际发布端口为空，内部health健康但宿主拒绝连接，浏览器测试尚未开始；只替换自建容器为普通bridge，明确仅127.0.0.1:18993发布，现有fixture启动自检证明非回环socket连接在发出前拒绝。此处是应用出站保护，不谎称内核无网；Silero独立任务仍network=none。
- 临时100ms sampler起初用on_event未被既有显式lifespan执行；检查无样本后包裹原lifespan，确认采样文件存在才执行首通。另一次带^的名称筛选未选中测试，保留selection-error记录，没有把未执行算通过。
- strict改变了构建上下文，因新产物/启动风险才定向复验同一冷暖及Silero，没有为增加数量扩展同类场景；旧756后端/25客户端无变化不重复跑。

## 复现与清理边界

1. 在独立环境按当前Dockerfile/requirements.lock构建本地tag；这不授权部署/推送或收费API。
2. 本轮测试wrapper为voiceagent-r93-resource-server.py，复用原tests/ui/td_local_app.py；Silero为voiceagent-r93-silero.py。只读挂载脚本，临时数据仅/tmp，容器`--cpus=1 --cpuset-cpus=0 --memory=1g --memory-swap=1g --read-only --tmpfs /tmp:rw,size=128m --cap-drop=ALL --security-opt=no-new-privileges`；正式WS仅本机发布18993，VAD/模型替身及出站保护明确保留。RTC候选未启用。
3. frontend内执行原Playwright `tests/ui/td-runtime.spec.js -g 'formal browser microphone' --project=desktop-chromium --workers=1`，设置VOICE_AGENT_UI_URL=http://127.0.0.1:18993、VOICE_AGENT_TD_LOCAL_RUNTIME=1、VOICE_AGENT_TD_INPUT_SOURCE_PROBE=1、VOICE_AGENT_TD_RENDER_CLOCK_PROBE=1、VOICE_AGENT_TD_E2E_PROBE=1，并为cold/warm分别指定证据目录。生成的是浏览器假麦克风信号，不采集真人声音。
4. 原生上下文回归：`VOICE_AGENT_DOCKER_CONTEXT_TEST=1 /tmp/voiceagent-r91-py311/bin/python -m pytest -q tests/test_docker_context.py`。只用临时哨兵文件，不复制真实Key。Ruff检查新工具/测试，Change门禁另附。

本轮自建资源容器已停，不继续耗CPU；暂保留stopped元数据供独立核验，镜像tag local/strict保留供复现。Docker Desktop及其原自动恢复容器未关闭，以免影响原服务。临时/tmp/voiceagent-r93-*、哨兵上下文/tmp/voiceagent-r93-ignore-audit*、忽略Playwright产物及本轮Docker资源是测试产物，不提交数据库/音频/环境；需要复核的白名单结果已复制本目录。后续只可按记录ID清理自己创建的资源，不能批量prune或处理旧容器。

## 剩余完成条件

本轮仅支持“限定离线资源场景可在1CPU/1GiB下运行”。仍缺真实厂商负载/并发分布、真实语音VAD与完整链同跑、瞬时队列精确峰值、RTC资源、手机/Safari/弱网/物理双讲AEC、配对新增链路延迟及x86_64环境。M4-3/M5-2/M5-3复合项继续未勾；不降低契约，不把无OOM改称性能SLO全通过。

本轮限定独立复核完成：stage-review/evidence-review-r93.md。独立原生9项通过0.40秒，strict镜像/两已停容器内核配置、两个不同call历史和1134条采样核对相符，无新增确认缺陷。四个自建容器最终退出0/OOMfalse，原服务继续healthy。整体仍INSUFFICIENT EVIDENCE，非C/PASS/Gate2。
