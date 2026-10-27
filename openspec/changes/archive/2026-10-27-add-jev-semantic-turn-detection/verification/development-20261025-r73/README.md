# r73 当前实现与自测审核输入

本包为当前工作区源码/规格/报告快照，供提前技术审查；全范围交付目标仍未达成，不自签独立PASS、Checkpoint C或User Gate 2。旧r48阶段快照保留，新包不覆盖旧证据。

## 已实现与正式入口

- 正式 Bot Advanced 自建TD及独立Jev配置，显式保存Key、加密持久化；Sessions逐轮证据；Share发布资源绑定。
- 普通TD/唯一提交/续说与计时竞争/Jev异常与预算/同源有效Final替换Partial。
- 严格编号路由/受控工具/永久缓存/串行输出，WS实际Worklet与鉴权回执；受控开发RTC保留RTP，任务对应、Final取消、编号仲裁见r68/r69。
- 默认RTC链未替换；未增加服务端AEC。

## 实际验证

- 本轮完整后端699 passed、5依赖警告、38.56秒，见backend-final.txt。
- r71提供Ruff/构建/类型及正式UI分批证据；全src既有类型错误不能算通过。
- r72历史真实性缺陷先红后绿：旧first_playback不再把收件时刻填入TD播放延迟，23项相关通过。
- D-072明确手机布局保留B，冻结v0.14 SHA不变；批准差异不自动代表完整UI检查点通过。

## 未实现、失败、未验证分别处理

| 分类 | 当前事实 | 关闭条件 |
|---|---|---|
| 未实现 | TD跨服务端/客户端渲染时钟的可靠对应，精确播放/e2e指标仍缺 | 同一任务保留时钟对应证据，明确测量精度；不能用网络收件时刻替代渲染时刻 |
| 失败后离线修复 | ASR实际digits边界误拒已离线修复；完整真实批次仍未证明 | 新批次冻结有效音频hash，独立授权后验证；旧音频丢失/授权消费不能重放 |
| 厂商未验证 | 六模型真实完整范围/修订/重连，TTS多文本/取消与整链 | 按明确数据、厂商、次数、费用和停止条件逐批授权，保存实际成功/失败 |
| 实机未验证 | 手机/Safari/弱网、AEC双讲、音质、1核1GB目标容量 | 对应实际设备/环境测量；开发机/fixture不替代 |
| UI未关闭 | 正式UI A/B完整矩阵与最终候选统一验收 | 对照D-056/D-072已批准差异，正式路由逐项核对；独立C由评审完成 |

## 运行和复现

源文件由snapshot.json逐项SHA识别，HEAD不能代表未提交源码。review-inputs.tar.gz仅在新目录解包，不覆盖共享工作区；共享源文件包含其他任务上下文，不能全部归属此Change。不含.env、数据库、主密钥、录音、node_modules或原始服务器日志。package-check.json核验包内每个文件hash。

离线后端：`.venv/bin/python -m pytest tests -q`。Change门禁：`python3 scripts/quality/verify_change.py add-jev-semantic-turn-detection`。前端与RTC复现参照stage-review/reproduction.md和r68/r69报告，保持本机替身/禁外部网络；不得自动重放任何已消费有限实验或收费批次。

本轮测试日志为保留证据。暂存封装脚本在/tmp/td_r73_package.py，不作为产品或验收代码；未提交/推送/部署。

62场景清单见scenario-audit.json。32组代表用例静态引用可解析（含模板化UI标题），不代表逐场景全覆盖。
