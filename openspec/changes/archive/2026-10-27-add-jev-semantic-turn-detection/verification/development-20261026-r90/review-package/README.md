# r90 增量审核包

这是原r89独立核验冻结包后的覆盖增量，不是独立完整仓库。基础包：`verification/development-20261026-r89/review-package/review-inputs.tar.gz`，SHA-256 `b15cf0ac6b6bd7a5faca0e575447b8d9a88615a5577c2d282375e4e854f33e8a`；保留原包不变。

在隔离目录先验证并解压r89，再解压本增量覆盖同名路径。按r90/README.md用正式Vite路由运行两个新UI测试；需要原package-lock依赖及Playwright Chromium，Chrome channel需本机安装。没有真实API/设备/默认RTC采用授权。不要在共享工作区盲目覆盖解包。

snapshot.json是本增量逐文件SHA；package-check.json记录压缩包SHA及实际重读逐文件校验。包含当前3生产前端文件、3新测试/fixture、本轮证据与当前交付文档/专项计划/独立报告。source-delta.json表明相对r89核心src/frontend/tests仅这6项变化；不包括.env、node_modules、DB/录音/原始trace。旧r89全后端和媒体代码无变化，复用其独立756/25证据。

完整C/Gate2仍未通过；此包只用于本轮界面/键盘返修与计划独立复核。最终用户验收、设备/性能/完整厂商效果另行推进。
