# r86阶段实现与自测审核包

当前新增RTC上行来源旁路、原生captureTime同包对应、实际证据与独立增量报告；snapshot.json逐文件hash、package-check.json包SHA。不覆盖r85已审输入。默认RTC不采用新链，没有数据通道音频/服务端AEC。认证采集锚/回填/VAD冻结/RTC E2E仍未实现，全Change继续BLOCKED，不宣称最终自测/独立PASS/C/Gate2。

新源相关16后端/18客户端检查及两次各有新增风险的正式RTC真实本机验证通过，最后SSRC拒绝补丁晚于浏览器记录，边界在r86 README明确。独立审查16/6通过且逐包核验无新增缺陷。旧715全量不当新源全量。

复现使用现有锁定环境，运行tests/test_td_rtp_input.py及相关RTC SDK用例、frontend/tests/unit；不要运行收费探针或旧有限RTC实验。当前Python3.13已用，裸机安装/3.11不作承诺。

包不含.env/录音/数据库/真实客户素材/原始capability日志。包含共享工作区运行上下文，不表示所有文件由本Change修改。实际音频/临时服务目录/tmp/voiceagent-r86-*未入包；无提交/推送/部署/归档。
