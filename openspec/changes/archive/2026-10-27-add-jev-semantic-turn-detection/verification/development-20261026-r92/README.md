# r93对Docker静态归因的纠正（2026-10-26）

本报告Jev专项结论保持，但下方Docker“原四输入缺项”归因撤回。原生Docker哨兵context实证：旧父目录!规则已包含四输入，也过宽包含frontend/.env/node_modules及无关OpenSpec哨兵；Gitwildmatch四红绿不证明Docker行为。未发现真实frontend/.env文件，未推送或发现Key外泄证据。r93已改严格具体白名单并以Docker原生9项红绿验证，见../development-20261026-r93/README.md；原文保留为当时错判，不能作为当前缺项事实。

# r92 真实Jev＋留存ASR回放：D080等待更新（2026-10-26）

本轮关闭“真实Jev新目标能否正确进入等待状态机”的限定证据缺口：实际两次Jev1.14返回不同概率，生产normalizer/coordinator/fusion/clock在受控时钟下遵守新等待目标。**不是实时ASR＋Jev整链、硬件播放或延迟性能验证**。保留RTP和默认关闭的RTC候选，无src/前端/产品规则/基线变更。

## 实际结果与授权

- D082用户本轮明确授权两条已留存虚构ASR文本及固定助手/问题，TypeSafe固定jev-1.14.0、最多2次/每次3秒/总US$0.01、首异常停止无重试；授权记录decision-log/delivery-status。两次已消费，不可重放。
- 请求1：“please do not cancel my booking.”，noul=.7，complete=.93/incomplete=.07，融合等待963ms。
- 请求2：“please do not cancel my booking. I would like to”，noul=.05，complete=0/incomplete=1，融合等待1952.5ms。
- 受控音频静音起点6000ms；旧Final截止为7163ms（6000+963+200），此时**0提交**；原Tmax8500ms时**1提交**。该次实际触发更长等待条件，旧Final不能抢交。没有在新目标1952.5ms处另作采样，因此不声称精确在该点提交。
- 记录的两个input_tokens为380/384，按[官方模型页](https://docs.typesafe.ai/models)2026-10-26公开US$0.042/Mtok估算US$0.000032088；**实扣账单未知**。两默认64k请求保守上界US$0.005376，小于授权US$0.01；未开启长上下文，不将预算说成厂商账户硬封顶。

证据：jev-D082.jsonl、result-summary.json；精确请求/来源hash：../jev-d080-replay-r92-plan.json。来源为r91已获授权的虚构音频ASR第5/15条Partial事件；这次**不新连ASR、不发音频、不调用LLM/TTS/工具/媒体**。

## 工具边界、红绿及复现

新增scripts/evaluation/probe_td_jev_replay.py复用生产CustomTDCoordinator、SourceNormalizer、JevClient；所有待发model/state/questions必须逐项等于冻结序列，最多两次。未授权在读Key前拒绝；独占日志claim加delivery状态阻止已消费重放；首HTTP/响应/usage/model/范围异常不再发第二次。保存白名单概率、token、等待/提交事件，不保存Key/原始响应headers/body。

tests/test_td_jev_replay_probe.py初始模块缺失3红；实现3绿后，离线审读发现“首目标已到Tmax，没有旧Final窗口”不能误作D080触发，先补失败回归再增加未触发停止，最终4绿。voiceagent-r92-red.txt、voiceagent-r92-maximum-red.txt、voiceagent-r92-green.txt保留；Ruff初始过长两行/缩进后又一行被拦，换行后通过voiceagent-r92-lint.txt。这些是新测试工具准备错误，未修改产品等待规则，也未靠重跑收费请求获得绿灯。

无费用复现：`/tmp/voiceagent-r91-py311/bin/python -m pytest -q tests/test_td_jev_replay_probe.py`；脚本不带--execute仅准备dry plan。真实执行命令需要新的匹配D号授权，**D082已消费不能重跑**。本次无变化756后端/25客户端不重复扩测；r91真实Python3.11回归继续有效。

## 剩余与下一步

本场景音频时钟由执行器主动advance，真实Jev网络耗时不推进该时钟；因此不能证明实时到达竞争、耗时只计一次的实际延迟效果或手机体验。对应普通TD完整生产回归已有离线证据，实时ASR/Jev整链尚需单独数据/次数/预算/停止条件授权和流式环境，不借本批推广。

手机/Safari/VoiceOver、弱网UDP、耳机外放双讲/AEC、Linux1核1GB、新旧链成对延迟及真实LLM工具/TTS取消保持未验证。优先准备可运行的隔离Linux与实体设备，再据专项计划有界执行；不新增AEC/传输架构、不默认采用RTC、不部署、不签独立完整C/Gate2。

临时日志/tmp/voiceagent-r92-*；原始白名单日志scripts/vendor/typesafe/logs/jev-d080-recorded-asr-replay-r92-v1-D-082.log已忽略，必要副本保留本目录。无新数据库/录音，无凭证输出。既有r90核心审核包保持冻结，本轮为专项工具与证据增量。

## 历史静态归因（已撤回，独立于Jev专项）

准备资源测试时静态发现`.dockerignore`排除了Vite配置声明的demo/evaluation/login三个HTML，以及Dockerfile直接COPY的verify_webrtc_production.py。已只增加四个精确放行条目，不改变运行架构、依赖或部署。tests/test_docker_context.py用Git wildmatch审计本文件当前锚定规则，四个输入4红→4绿；**这只是当前规则的静态检查，不是Docker完整匹配器或实际镜像构建证据**。Ruff最初发现测试import顺序，排序后通过。Docker daemon尚未启动，镜像构建/1核1GB仍未验证；启动本机Docker可能恢复旧容器，已单独向用户询问，不自行启动/停旧容器或操作生产数据。

本轮已独立限定复核：stage-review/evidence-review-r92.md。实际请求/使用量/目标、受控时钟提交与Docker四精确条目核对相符；过渡门禁未披露阻塞已处理，最终无错误。整体仍INSUFFICIENT EVIDENCE，未签C/Gate2。
