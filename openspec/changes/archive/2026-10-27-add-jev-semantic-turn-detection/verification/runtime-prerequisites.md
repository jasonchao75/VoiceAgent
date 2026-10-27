# 本地复验资源前置条件

现有Pipecat1.8.1 RTVI观察器调用NLTK分句，需要既有依赖的数据包punkt_tab。仅pip安装NLTK不代表数据已存在；缺失时观察器可能异常，不能静默用测试分句替代宣称正式通路通过。

- 本次从NLTK官方固定index.xml及packages/tokenizers/punkt_tab.zip获取，TLS使用项目已有certifi CA，ZIP与官方index中的SHA-256逐字节匹配；校验值e57f64187974277726a3417ca6f181ec5403676c717672eef6a748a7b20e0106。
- 本机资源路径`.venv/nltk_data/tokenizers/punkt_tab/`，Git忽略；不提交模型数据。NLTK按虚拟环境默认路径直接找到，无需更改.env或真实凭证。
- 常规安装命令：`.venv/bin/python -m nltk.downloader -d .venv/nltk_data punkt_tab`。本机代理环境该下载器拒绝代理请求；本次没有关闭安全开关，采用固定官方URL、TLS和SHA校验后安全解压。早期失败日志和成功证明保留r20/nltk-*.txt。不要以关闭TLS验证修复证书问题。
- 复验：`.venv/bin/python -c "import nltk; nltk.data.find('tokenizers/punkt_tab'); from pipecat.utils.string import match_endofsentence; print(match_endofsentence('Local test.'))"`。只用合成文本，不触达厂商。
- 部署镜像/其他环境需预置同一已有依赖资源，并验证离线可读；本次未构建或部署生产镜像，不宣称其他环境资源已就绪。

官方来源：[NLTK Data](https://www.nltk.org/data.html)、[官方资源index](https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/index.xml)。这不是新增服务端AEC或新的推理API，也未使用任何Provider Key。
