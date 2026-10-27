# r84：Checkpoint B证据闭合

按M4-6逐项审计真实API/存储路径，已有证据足够，不再增加或重跑同类测试。checkpoint-b-matrix.json对8范围列实际日志/哈希/级别/限制，明确r83混合日志仅7通过，缓存试听使用正确ordinary最终单例通过，旧失败不隐藏。JUnit逐case确认凭证加密脱敏与旧NULL/持久化用例实际通过。

**研发Checkpoint B本地真实API与存储范围完成**；不宣称厂商兼容、默认RTC采用、Checkpoint C或Gate2。未实现RTC来源E2E及完整真实厂商/设备阻塞仍保留，r83独立阶段BLOCKED不被本审计覆盖。无新产品规则、源码改动、付费调用或重复业务测试。

正式入口为既有根路由Advanced/ASR/Sessions/Share与公开会话，未另造验收页；缓存和推理为明确本机替身，HTTP/RTC/Worklet/SQLite为实际路径。原始临时日志仍按r83路径保留，未产生新音频/数据库。下一步H1按独立报告补可证明RTC来源坐标及缺失边界，H2准备新最小批次守卫/授权，最终重新收敛完整自测包。

## D075真实Flux英文修复确认

用户单独授权新5.1675秒虚构数字素材+3秒静音，最多1连接/30秒/US$0.02。实际1连接，进程退出0，10.742秒，18个转写来源事件missing_reason均为空；probe结果ok，证据deepgram-fresh-digits-D075.jsonl。离线14项探针回归4.56秒、Ruff、dry-run、素材哈希预检通过后才调用。登记日期字段曾用错，被Change门禁在调用前拦截，改Date后0errors再执行；未据此重复调用。

本次关闭“修复后数字来源范围无实际回包”这一单模型缺口。真实转写不等于原文全字准确，兼容/来源通过不证明识别准确率、完整六模型、重连、语速效果、LLM或TTS。D075已消费，不重复使用。按30秒常规公开USD0.0077/min保守上界US$0.00385，不是账单实际扣费；总授权US$0.02未扩大。官方价格核对2026-10-25 https://deepgram.com/pricing。

新原始日志保留scripts/vendor/deepgram/logs/deepgram-td-fresh-digits-confirmation-v1-D-075.log（gitignored），白名单副本入本目录；新素材test-results/td-vendor-inputs/20261024/digits-ready.wav同样忽略，Key不输出/入包。本轮只新执行这一个付费连接。

## 后续模型准备

为不重复已通过Flux英文，只准备Flux多语种/Nova3英文两模型独立新批次，数据不变、不同batch/hash、每连接30秒且全批首次失败停，公开保守上界US$0.00850、拟授权US$0.02。探针新增显式互斥scope，目标行为先红再实现，15项当前探针回归通过；计划dry-run/文件hash校验与Ruff通过。D076用户授权后另行登记执行，不将D075当作可复用额度。

## D076另外两模型实际结果

已授权最多2连接/每条30秒/US$0.02，全批实际2连接退出0。Flux多语种18个来源事件、10.776秒；Nova3英文7个来源事件、11.066秒，全部missing_reason为空且probe结果ok；原始安全白名单见deepgram-remaining-D076.jsonl。没有重复Flux英文，没有重试或调用其他服务。授权已消费，不复用。估计公开保守上界US$0.00850而非实际扣费。

现在Deepgram三目标模型的新数字素材基本范围兼容均有external-real证据；仍不能声称四家六模型、真实续说/重连、全链效果及TTS取消通过。剩余厂商必须先准备各自脚本守卫、格式/费用与授权，不把Deepgram授权扩展。

## 当前审核输入封包

review-package/review-inputs.tar.gz为当前r84源码/规格/决定/证据包，882文件逐SHA核验并在/tmp/voiceagent-r84-review-extracted-final新目录实际解包。解包cwd探针15项通过4.53秒；不是重复厂商调用。当前工作区同组15项通过，Ruff/Mypy单探针通过。生产src与frontend/src相较r83无增量，只有授权探针/测试及文档证据变化，不重跑已通过且无变化的715后端或25浏览器。

r83独立阶段BLOCKED报告保留，不以其结论声称r84独立通过；独立C/Gate2未填写。包内文档为封装时点，解包验证摘要在外层，package-check.json为当前包hash。未提交、推送、部署、归档或合并主规格。
