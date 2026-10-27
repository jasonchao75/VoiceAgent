# r78 当前阶段源码与自测审核包

包含D-073当前源代码、Spec/决定/报告、脱敏实际范围证据与双视口截图。旧r75是旧源码；本包单独版本，不覆盖旧输入或失败证据。snapshot.json逐文件哈希，package-check.json包内核验。

主工作区完整后端706通过；编码器后补类型注解RTP8项通过；全src无增量Python3.13类型76文件通过。独立阶段审查发现的起点说明问题已红绿修复并只读复核，不能当最终独立PASS。

E2E源停声时钟仍未实现，真实厂商/实机/完整UI及默认采用仍未关闭。包不含凭证、真实客户素材、原始服务器日志、trace、录音、数据库或模型缓存；不据此承诺裸机环境或部署3.11已验证。解包后只复核必要离线用例，严禁重放已消费RTC有限实验或收费批次。

## 解包实际验证

首次新目录46项相关后端通过/2.18秒，随后Node因客户端单测目录未入包停止。修封装后新目录9项客户端通过；backend-input-identity.json证明两包src/tests/config/scripts后端输入哈希无变化，因此不重跑46项或706项。原失败包及日志以before-unit-directory前缀保留。当前405文件完整包的哈希见package-check.json，unit-extracted-checks.txt为实际新目录执行结果。源快照中的交付状态是封装冻结时点；外层self-test-report及delivery-status是验证后最新状态。
