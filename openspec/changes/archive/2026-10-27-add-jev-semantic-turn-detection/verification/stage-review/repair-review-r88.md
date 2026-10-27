# r88 独立返修复审（2026-10-26）

**整体：BLOCKED。** 原六项返修已按其明确契约解决（五项代码/交互与一项交接文档）。另有研发主动登记的正常RTC来源范围红灯，不能将本轮称完整RTC指标闭环或全Change PASS。未签Checkpoint C/User Gate 2。

本复审加载change-verifier，未参与返修、未代改实现或测试，未付费/部署/提交/推送。未重跑浏览器或旧有限实验；独立执行必要离线回归，并核查实际正式页面/RTC证据。

## 原六项逐项结论

| 原问题 | 复审结论 | 独立核查与证据边界 |
|---|---|---|
| B1 独立英文段直接拼接onetwo | **Resolved** | `join_source_segments`对独立词段保留边界，Soniox token provenance避免为subword凭空加空格，customTD pending合并复用；跨提交切片使用全文覆盖后的原文span，不把每个词强加空格。原review repro及正式测试通过。 |
| B2 不完整词时间切Final丢do/not | **Resolved** | `resolve_snapshot`跨范围切片先要求完整全文词覆盖与可靠时间；缺词时返回None，不以“Iagree”等损坏文本重答；完整且边界可靠时用原文span。同范围整Final无需错误切片。原故障注入repro通过。 |
| B3 新Jev target被旧Final截止绕过 | **Resolved / D-080** | poll先检新target或缺有效target，再考虑原Final窗口；原窗口不被修订重启，原Tmax不延长，无新Jev结果只保留最长兜底。原review repro与2000ms不新增Final窗口测试通过。 |
| RTC回执挂起阻塞停止与新答 | **Resolved（原确认缺陷范围）** | 新PlaybackReceiptSender串行3秒截止/abort/close/失败一次，失败后后续停止不越过；bridge.fail向真实player发interrupt。server独立5秒stop确认守卫发送永久错误，不伪造停止、不释放旧槽给新答。failCall错误遥测不再阻塞releaseClient。正常/关闭/响应丢失单元及真实公开入口故障证据一致。 |
| 完整性关闭四字段仍可编辑 | **Resolved** | `td-settings`加载/切换同步禁用4字段，规则总开关也生效；collection关闭保存null。正式根路由/同组件真实DOM，fixture API截获保存和刷新断言通过；Desktop及明确390px证据，不冒充真实厂商或物理设备。 |
| README旧r86当当前 | **Resolved** | 研发随后已将Change README、自测与当前入口指向r88，保留严格E2E=0、completed/未知事实边界及旧包为历史。评审只读核对实际文件，未把旧r87成功冒充r88通过。 |

## 本次独立执行

- 原始独立三条repro：`pytest verification/stage-review/backend_repros_20261026.py`（实际路径在本Change下），**3 passed /1依赖警告/1.05s**。
- 正式回归：`tests/test_td_review_regressions.py tests/test_td_transcript.py tests/test_td_timing.py tests/test_td_serial_output.py`，**39 passed /1警告/1.13s**。
- 生产回执与RTC入口：`node --test frontend/tests/unit/td-playback-receipts.test.js frontend/tests/unit/td-rtc-entry.test.js`，**9 passed /0 fail**。
- Change门禁：复审时0 errors/45 warnings/58未勾任务；结构通过不消除下述行为红灯。

日志见`stage-review/r88-independent/`。研发全后端754/客户端25完整结果已只读核对；未重复全量，也不把旧739当本次完整版本。当前报告尚未以待封新包hash确认冻结输入，后续只做包hash核对。

## RTC故障真实组合与事实边界

只读核查实际本机生产公开入口故障用例和`receipt-response-lost-history.json`：第二个task_started经route.fetch确已被后端204接受，但HTTP响应被挂起；错误遥测也被挂起。客户端有界进入错误页、原audio停止/解绑、历史结束；Final已触发，旧任务没有伪造task_stopped，新response1:2没有开播，旧任务终态保留`ended_started`。这修复原“永久卡停止队列”的缺陷，不能把故障解释为已确认正常停止。

由于客户端错误遥测确未到达，服务器顶层history.status为completed，未记录确定的客户端错误原因；本证据证明的是**UI显式错误结束和历史保留已播/未确认停止事实**，不证明服务器已记录完整失败原因。不得在自测报告写成“后端已获知回执响应丢失”。该边界不是凭空新增已确认规范缺陷。

## 新缺口：R88-NORMAL-RTC-SOURCE-BOUNDS

**未闭环，不能由正常播放限域通过关闭。** 严格E2E正式测试前置播放/停止/Final已通过，但等待5秒live E2E计数仍0，测试红灯保留；后续关闭E2E断言的限域正例只证明正常播放与缺失事实。两者必须同时报告，不能用后者覆盖前者。

只读已有normal诊断包含460个原生input_capture_packet、460个解码输出及18个clock_sample，没有显式unavailable事件；captureTime覆盖约125–9305ms。另一限域播放会话仍没有e2e_timing_bounds。这足以说明“浏览器有元数据”不等于“server候选源界已成功冻结”。目前证据不能唯一定位是服务端native→processed覆盖、元数据匹配、时钟前后锚、候选样本定位或本机fixture准备问题，**不得直接归因厂商/弱网或断言r87实现完全失效**。

最小关闭条件：先对已保存日志/候选speech_end_audio_ms和当时server来源匹配记录做一次离线定位，指出哪一层拒绝及理由；若现证据不足，仅补缺失字段的有界本机诊断。明确工程缺陷由研发修复并定向回归，之后在同正式入口重验源/播放区间或证据不足时明确缺失。不得赌同条件重跑直到偶然绿、放宽时钟/匹配条件、用r87旧成功当r88通过，或因此申请同类收费调用。

## 交接判断

原六项评审问题的返修可按上表关闭，但整体仍BLOCKED：正常RTC来源范围仍有实际红灯。可以交这份**返修与剩余问题包**继续审核，不能声明整Change或RTC指标已全部完成。设备/真实多语场景/完整厂商取消/目标环境与默认采用等原未验证范围仍单列，未把独立PASS缺失循环作为研发先修代码的理由。

无新增产品决定；D-080不重复询问。生产/测试修改由研发负责，本复审只写报告。

## 最终冻结包只读核验

2026-10-26，评审独立核验review-package内1104文件逐项hash及15项关键当前生产/测试源码，全部一致。archive SHA-256：`89e2c02589258d9bccecef86684ec304f63515a9fe9dca131aeee1bb899dafad`。未重跑测试或修改冻结包。本核验仅补外层报告，包内报告是冻结前时点，不重打包。原六项Resolved，严格RTC源范围红灯仍Open，整体BLOCKED不变。
