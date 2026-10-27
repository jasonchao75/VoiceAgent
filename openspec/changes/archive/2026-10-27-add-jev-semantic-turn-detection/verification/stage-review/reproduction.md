# 版本、复现与安全边界

## 1．取得同一候选

本阶段是未提交的共享工作区，不是一个已提交分支/PR。仓库HEAD为`2aff076d07599c5352b390edf83106d49e7bb2cb`，分支main；**HEAD不包含这些未提交实现**。以snapshot.json的各源文件SHA-256识别本次材料。review-inputs.tar.gz为对应只读输入副本，后续源码变化时可在新的临时目录解包审查，不覆盖共享工作区。评审前先核对工作区与指纹；不相符时标明已发生后续修改，不能把旧结果当新候选通过。

运行版本实测：Python3.13.2、Pipecat1.8.1、aiortc1.15.0、PyAV17.1.0、Deepgram SDK7.8.0、FastAPI0.141.1、Pydantic2.13.5、pytest8.4.2、websockets16.1.1；Node25.9.0、npm11.12.1。前端锁定的三项Pipecat客户端分别1.13.0/1.10.7/1.7.1；实际安装版本另见snapshot.json。默认项目Python类型目标3.11与本机3.13不同，默认全目录mypy失败限制仍保留。

共享工作树还有其他Change和用户素材改动。snapshot只记录审核输入哈希，不声明共享src/api.py/main.js/mobile-demo等整文件都属于本Change。不要reset/stash/覆盖其他任务，不提交.env/.models/录音/库。Riyad下载脚本、Arabic benchmark、其他Change不在本次审核归属。源码哈希不包括.env和密钥/录音数据，记录中没有真实Key。

## 2．本轮实际做了什么

本轮只读审计已有源/日志、整理材料、修正交付状态过期字段及D-061 Delta标题层级（不改行为），检查引用和哈希，运行Change文档门禁。**没有运行新业务测试，没有重新执行有限RTC实验，没有外部付费调用，没有完整回归。** 当前683后端结果来自r46，早于r47尾空格修复；r47只运行对应20项，不能拼为新全量。

## 3．评审先复核已有证据

- RTC：静态阅读r39/README.md与r41/rtc_mapping_experiment.json/.py，核对坐标、混合帧及NOT_RUN；当前约定已停止，不自动重新启动调查。
- ASR：逐行检查r47 D-062 JSONL第二例第7事件，比较窗口/词时间与`SourceSegment.__post_init__`；再核对第一例29事件及Final，区别“有字段但被拒”和“没字段”。
- TTS：读r47 D-063协议白名单，再看同目录SDK红灯/20项通过和`test_actual_sdk_single_unit_preserves_exact_authorized_text`。不要把假socket的480样本当真实厂商音频。
- 版本边界：核对evidence-index.json中的原文件和结尾结果；旧失败文件保留，不据文件名green/final猜通过。

## 4．必要时的定向离线复现（不是本轮新增执行结果）

从仓库根目录、现有.venv运行。无真实凭证需求；以下测试的网络/协议路径使用替身，不加`--execute`。

```sh
.venv/bin/pytest tests/test_td_source_frames.py tests/test_td_transcript.py tests/test_td_asr_events.py tests/test_td_runtime.py -q
.venv/bin/pytest tests/test_td_tts_vendor_probe.py tests/test_echo_synthesis.py tests/test_echo_cache.py tests/test_echo_runtime.py -q
.venv/bin/pytest tests/test_td_authority.py tests/test_td_timing.py tests/test_td_response_revision.py tests/test_td_tool_scope.py -q
python3 scripts/quality/verify_change.py add-jev-semantic-turn-detection
```

只复核与发现相关的一组；不要为审查数量全部重复。完整`pytest tests -q --ignore=tests/ui`在最终候选收敛后统一执行，本报告不要求现在重跑。禁止重放任何既有`probe_* --execute --authorization-decision D-...`，包括剩余未用次数。需外部调用另批授权。

UI需显式启动只访问loopback的离线应用，不能指向线上：

```sh
PYTHONPATH=. .venv/bin/python tests/ui/td_local_app.py --data-dir /tmp/voiceagent-td-stage-review --port 8771 --ui-origin http://127.0.0.1:5179 --scenario identifier_cache_repair
```

另一终端在frontend启动`VOICE_AGENT_UI_API_TARGET=http://127.0.0.1:8771 npm run dev -- --host 127.0.0.1 --port 5179 --strictPort`。目录名供评审新建，未被本轮启动；fixture拒绝非loopback连接、用惰性本地Key，不能使用生产库。一般UI fixture可直接用现有td-settings/history用例拦截数据；正式WS恢复需`VOICE_AGENT_TD_LOCAL_RUNTIME=1`、`VOICE_AGENT_TD_LOCAL_SCENARIO=identifier_cache_repair`和UI_URL一致。派生证据用`VOICE_AGENT_TD_UI_EVIDENCE`指向新的审核目录，默认写忽略的test-results；不覆盖历史截图、冻结HTML或baseline。此处为复现步骤，不宣称这些新端口/目录已验证。

## 5．保留产物与回退

本轮整理助手脚本`/tmp/voiceagent-stage-matrix.py`和`/tmp/voiceagent-stage-snapshot.py`仅用于文件映射/封装，不执行业务测试，不提交到源码；暂保留以便追溯。

已用本地临时数据包括`/tmp/voiceagent-td-r43-source-failure`、`/tmp/voiceagent-td-r45-cache-repair`和`/tmp/voiceagent-jev-r39-synthetic`；旧r40等路径在对应轮次报告。为证据保留，不打包/提交；厂商原安全日志与可能的音频在`scripts/vendor/deepgram/logs/`，.env、frontend/dist、test-results均忽略。只处理本任务拥有的服务，不杀其他端口或删用户数据。

当前安全回退边界：不启用未经证明的新RTC播放器，不把实际开播未知改为成功；原生/off路径保留，是否切换由用户配置而非静默降级。ASR证据不完整按D-061明确失败；已发布素材校验不暗中合成，运行恢复只用冻结会话配置。代码未提交，回退需按具体文件/TD片段制定，禁止整仓reset覆盖其他任务。
