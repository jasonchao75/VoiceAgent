# r83：D-074失败恢复与当前阶段审核输入（2026-10-25）

## 结论与边界

已关闭正式公开入口的缓存读取失败/补合成成功和补合成也失败两个组合缺口。D-074失败只跳过当前跟读，保留编号继续；实际失败历史、后续编号与清空工具、固定发布配置均核对。没有收费调用、默认RTC替换或部署。本包是阶段审核输入，**全Change未完成、未自签独立PASS/C/User Gate2**。

## 实际结果

| 检查 | 结果 / 证据 | 级别 |
|---|---|---|
| 完整后端 | 715 passed / 5依赖警告 /37.90s；backend-full.txt、backend-junit.xml | mock/fixture/本地SDK混合，非厂商 |
| 当前前端静态契约 | 15 passed；frontend-contract-current.txt | static |
| Node客户端单元 | 14 passed；client-unit-full.txt | mock |
| 正式页面/原生Worklet | 25 passed /28.6s；ui-current.txt、browser/final-ui | fixture/component；两视口、中英按用例 |
| 公开缓存恢复成功 | 1 passed /14.0s；browser-public-repair.txt、browser/evidence | local-real RTC/回执/存储；推理替身 |
| 公开补合成失败继续 | 1 passed /11.9s；browser-public-failure.txt、browser/failure-fixed | local-real RTC；失败任务无PCM，不冒充部分PCM故障实测 |
| 实际历史HTTP503→重试/筛选空/恢复 | 正负会话各2 passed；history-api-*.txt、browser/history* | local-real API/SQLite；单次中间件故障注入 |
| 实际应用进程重启 | restart-published-history.json；发布版本、独立草稿、原事件/指标原样 | local-real，正例已验证 |
| 类型 / 质量 / 构建 | Mypy77源、Ruff全src/tests、Vite通过；mypy-full.txt/ruff-full.txt/build.txt | static/build |

715后端通过后又补ASR抽屉Escape-only客户端修复。当前15静态/25浏览器/构建覆盖这份增量；不宣称715是其后重新全量执行。之前失败日志和红灯均保留，不用重跑次数替代验收。

## 修复与红绿

- 源部分PCM后异常曾发送正常task_end；serial_output现在清待播缓冲，已发任务要求实际stop，等待回执释放；IdentifierOutput记录job_failed，不标资源ready。
- 排队失败的同文Final曾重复准备；失败来源去重。output-targeted-final.txt含21项。对应红灯partial/source failure及metadata Final日志保留。
- 原本机fixture只挡TCP connect；现在connect_ex/UDP/sendmsg同样限loopback，STUN显式空。安全单测先替换底层为惰性stub，无真实外发；新守卫下公开RTC通过。
- Sessions/ASR抽屉Escape缺失已委派现有清理路径；没有引入配置或研发控件。

## 正式入口与复现

正式根路由Bot→Advanced、ASR组件、Share、Sessions保持同DOM；公开链接使用既有/api/public/demos会话入口。受控RTC仅create_app(development_rtp_candidate=True)，默认False，RTP音轨保留、无数据通道音频。tests/ui/td_local_app.py提供显式本机替身和临时存储；不等同真实厂商。

后端：`.venv/bin/python -m pytest -q --junitxml=/tmp/td-review.xml`。定向失败契约：`.venv/bin/python -m pytest tests/test_td_serial_output.py tests/test_td_identifier_output.py tests/test_td_local_fixture_safety.py -q`。前端：`npm run build`；其余精确环境与断言见对应frontend/tests/ui/td-*.spec.js。RTC组合需VOICE_AGENT_TD_LOCAL_RUNTIME=1、VOICE_AGENT_TD_LOCAL_RTP_CANDIDATE=1、对应LOCAL_SCENARIO及PUBLIC_CACHE_REPAIR/FAILURE开关，显式5178代理8793，不连真实厂商。不得运行旧已用尽授权的有限诊断或付费脚本。

## 未实现 / 失败 / 未验证分开

- 未实现：RTC上行采集源时钟/E2E；跨连接绝对输入时钟尚无完整闭环。默认RTC仍旧链，受控候选未正式采用。
- 已知失败：D-062真实ASR批次第2连接来源边界失败，已离线样本坐标修复、真实修复后未确认；旧TTS批次失败，D-065单例one后续成功，不等于完整三句。r40配置B矩阵曾1失败，当前状态需以当前用例核对，故不先勾完整B。
- 未验证：完整六模型真实范围/修订/重连、真实工具LLM/取消、语言效果/P95/费用、手机/Safari/弱网、ADC/声学出声/硬件AEC、目标Python3.11和1核1G容量。WS E2E仅配置VAD源样本→Worklet，非物理声学延迟。

## 下一步完成条件

1. B剩余配置状态逐项对照最新正式API持久化/重启/失败证据，不能把r40旧失败当通过。
2. RTC源时钟需可靠源样本/连接边界映射，缺证据仍显示缺失；不自行换架构或正式启用候选。
3. 真实厂商仅在离线根因收敛后准备精确新素材hash/次数/费用/停止计划，单独授权，不重用D-062等授权。
4. 完整范围未收敛前只做阶段独立审查；最终候选完整自测后才可提交最终独立验收。

## 版本与文件

Python3.13；锁定Pipecat/客户端版本以requirements.lock和frontend/package-lock.json为准。candidate-source.json记录源文件hash及Git HEAD，共享未提交工作区不会被称已提交版本。冻结原型v0.14 SHA-256保持657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4。

原始临时DB/日志/浏览器trace在/tmp/voiceagent-r83-public-cache、/tmp/voiceagent-r83-*.txt/log；仅白名单合成历史、证明JSON、截图和测试摘要保留于本目录。数据库、密钥、原始能力URL/音频不进入审核压缩包。旧r78包不是当前源。阶段包见review-package/。

## 封包后补充核对（不改源代码）

配置B八路径：七项通过6.0秒中的其余一项因identifier故障场景生成10秒、ordinary用例预期0.1秒而失败；未放宽断言。切回ordinary并确认服务启动后，该缓存生成/试听/保存/刷新/发布/跨Bot隔离用例1通过2.2秒。首次本机浏览器/端口权限失败同样保留，均非产品结论。config-b*.txt分别记录原运行/场景错误/服务未就绪/最终通过。失败会话实际服务进程重启后事件和指标一致，见restart-failed-history.json。原r40窄屏配置失败由当前同用例通过替代，但完整B尚待统一审计。

阶段包首次692文件逐hash解包；新目录使用同锁定环境执行输出/编号失败/守卫9项通过1.24秒，extracted-output-checks.txt。不等于重跑全部715或独立PASS。封包后文档/证据增量以外层为准，源代码未变。

## 独立阶段审查结果

[独立报告](../independent-review.md)已由未参与本轮实现的评审完成，结论BLOCKED（全Change未齐，不是本轮新增失败）；未发现新增实现缺陷。评审在工作区9项通过1.03秒、真正解包cwd9项通过0.72秒，并逐文件核验692文件包。没有重复全715或浏览器矩阵，没有写独立PASS/C/Gate2。日志见verification/stage-review/r83-independent/。
