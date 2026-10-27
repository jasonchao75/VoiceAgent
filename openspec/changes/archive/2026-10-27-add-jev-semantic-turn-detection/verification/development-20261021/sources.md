# 协议依据与证据边界

- 本地锁定代码：pipecat-ai 1.8.1、speechmatics-voice 0.2.8；ASR事件fixture不代表实包覆盖。
- Jev wire contract：官方[TypeSafe OpenAPI](https://api.typesafe.ai/openapi.json)，2026-10-21读取：POST /v1/systemone、Bearer鉴权、model/state/questions、answers中noul与Choice完整probabilities。本轮仅读取公开规范，所有客户端测试使用httpx.MockTransport，没有发送转写或凭证到远端。
- D-049：Final替换Partial不再做语义比较；没有新增比较请求。
- 本目录red文件是首次目标行为缺失的测试输出；pytest.txt是最终本地回归输出。全量测试通过不能证明新增底座已接通正式业务链路。
