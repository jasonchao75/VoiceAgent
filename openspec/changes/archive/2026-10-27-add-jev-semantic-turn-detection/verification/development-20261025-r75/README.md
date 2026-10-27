# r75：审核包测试依赖闭包修复

阶段独立评审指出r74漏了实际ASR回归使用的白名单历史JSONL，复现FileNotFoundError；父任务静态检查另发现全tests所需deploy/quality脚本与evaluation.html。集中修封装输入，不修改产品代码或弱化测试。旧r74包保留。

新版含所需非敏感脚本、hook、页面与冻结fixture。从新临时目录解包后运行完整离线tests验证依赖闭包；结果见extracted-backend.txt，不以源工作区699通过代替解包验证。使用同一已安装依赖环境，不宣称裸机依赖安装、真实厂商、实机或最终验收通过。

原始服务器日志、凭证、数据库与录音不包含；D-062 JSONL为已有脱敏白名单事件，不发送到厂商。包内manifest区分共享代码与本Change归属。最终独立PASS/C/Gate2均未填写。

## 最终可复现输入

使用closure-complete/review-inputs.tar.gz与snapshot.json/package-check.json。新目录实际完整离线607 passed、92既有私有Evaluation素材跳过、0失败、14.85秒；与源工作区699通过范围不同。阶段评审原缺项单例独立复核通过。失败/先前不完整输入版本全部保留作追溯。
