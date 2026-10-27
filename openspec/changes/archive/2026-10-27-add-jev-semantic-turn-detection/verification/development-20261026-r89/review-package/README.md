# r89 当前实现与自测独立审核输入

当前未提交工作区，由snapshot.json逐文件SHA界定；package-check.json给归档SHA。包含完整运行源码/正式页面/测试/锁文件/质量门禁/当前68个Delta场景、22自测ID、实际命令结果/版本/红绿/真实本机冷暖RTC与重启UI证据/独立复审。共享运行上下文不代表都归本Change修改。

原r87六项及新增晚到/替换track来源缺陷已独立复审支持关闭；当前756后端/25客户端/质量构建通过。这里是可供完整独立审核的开发交包，不是全Change PASS、C、User Gate2或RTC默认采用。手机/声学/真实完整效果/目标环境等明确未验证；历史源缺失当次不能唯一归因、首探针错误不当生产事实、错误遥测未送达仅保留unknown，详见上层README及completion-audit。

解包独立目录，使用已安装的锁定Python3.13环境与Node25；各测试命令见上层README。常规完整后端结果来自原工作区；包中不携带私有Evaluation数据/麦克风/厂商Key，其无关素材测试可能按既有规则跳过，不冒充TD失败或新测结果。复现核心来源/计时/转写/串行/客户端不需任何真实Key或外部请求。独立解包验证日志在外层package-reproduction-check；最后文件身份全部复核。

不包含.env、真实凭证、SQLite、录音、原始服务器日志、trace、node_modules或venv。不合主规格/归档/提交推送/部署。当前主规格、Delta/决定/原型baseline与历史任务均保留；冻结原型SHA不变。

复现前置：解包目录不含venv/node_modules；Python使用按requirements.lock安装的环境，frontend内先运行 `npm ci --ignore-scripts --no-audit --no-fund` 安装package-lock既有依赖，再从仓库根跑Node单元/构建。离线缓存可能不全，离线安装失败不能当源码失败；准备日志完整保留。

## 独立目录复现闭包
组装版独立目录实际126核心后端/25客户端及完整Vite构建通过，import路径均指解包源；不是借原工作区源码假复现。初始漏demo.html/login.html导致构建失败已保留并补清单；已核补入文件及全部运行/测试输入与最终源SHA一致，最终包必须包含这些入口。node_modules不入包，先按原lock安装；原缓存离线不全/权限失败未改用户缓存权限，使用/tmp任务缓存后成功，失败日志保留。见package-reproduction-check.json（含实测输入SHA）；这不是声称解包后重跑全756。初始assembly快照和最终冻结点分开。
