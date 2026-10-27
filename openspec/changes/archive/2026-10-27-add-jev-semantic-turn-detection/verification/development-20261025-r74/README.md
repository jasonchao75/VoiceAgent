# r74：可复现审核输入封装修复

r73包的297个已列文件hash正确，但不证明输入完整：缺非敏感runtime配置，两个探针路径写错且静默跳过。本轮只修封装，r73原包保留以追溯。

新版加入三个configs/runtime JSON、正确scripts/evaluation探针及TypeSafe脚本、冻结原型和guard说明；显式文件清单缺失立即失败。新目录解包后加载runtime/voice/LLM配置并检查原型SHA、探针及62场景清单；结果见extracted-smoke.txt。包内逐文件SHA检查见package-check.json。

业务源码未改变；r73完整后端699 passed/38.56秒仍为当前结果，不重新扩展同类测试。未打包.env/密钥/数据库/录音/node_modules/模型缓存/原始服务器日志。独立复跑需安装pyproject及前端锁定依赖；Silero依赖资源须在隔离环境按原项目依赖准备，不借开发机缓存声称裸机即用。

本包仍缺精确跨钟指标、完整真实厂商和实机/UI验证，不能称完整交付或独立验收通过。此快照供代码与自测提前审核，旧r48及r73不覆盖。
