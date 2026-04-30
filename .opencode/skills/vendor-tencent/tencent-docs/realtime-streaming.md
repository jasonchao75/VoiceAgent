# Tencent Cloud Realtime Streaming (Python SDK) 规范

> **极度推荐方案**: 腾讯云官方极其复杂且对特殊字符高度敏感的 URL Signature HMAC-SHA1 签名机制会导致极高的失败率，强烈建议在 VoiceAgent 场景使用官方 SDK `tencentcloud-speech-sdk-python`。

## 1. 核心信息与鉴权
- **依赖库 (Python)**: `tencentcloud-speech-sdk-python` (pip install tencentcloud-speech-sdk-python)
- **鉴权类**: `Credential(SECRET_ID, SECRET_KEY)`

## 2. 基础配置参数与枚举 (红线参数)
与大多数 SDK 采用字典配置不同，腾讯云 SDK 的 `SpeechRecognizer` 采用了 Builder 模式的 Setter 方法进行配置。
以下参数在 `VoiceAgent` 场景下极具价值：

### 2.1 引擎模型 `ENGINE_MODEL_TYPE`
这是在实例化 `SpeechRecognizer` 时的第三个必填参数：
- `16k_zh_large`：普方英大模型引擎（非电话高质量场景首选）
- `8k_zh_large`：中文电话专用大模型引擎（电话场景首选）
- `16k_multi_lang`：多语种大模型引擎

### 2.2 核心业务 Setter 方法
- `recognizer.set_need_vad(1)`: **必须开启**（设为 1）。如果不开启 VAD，音频超过 60 秒将被强制断开，对于 VoiceAgent 长时间对话这是致命的。
- `recognizer.set_vad_silence_time(1000)`: VAD 断句的静音阈值，默认为 `1000` (1秒)，支持范围 `500-2000`。
- `recognizer.set_voice_format(1)`: 设置音频格式，`1` 代表 pcm（VoiceAgent 推荐）。
- `recognizer.set_word_info(1)`: 设置为 `1` 可以返回字级别的时间戳，如果设置为 `2` 则连标点的时间戳也会返回。
- `recognizer.set_filter_dirty(1)`: 脏词过滤。
- `recognizer.set_filter_punc(1)`: 过滤句末句号。
- `recognizer.set_convert_num_mode(1)`: 智能将中文数字转为阿拉伯数字。

## 3. SDK 监听器与回调机制
腾讯 SDK 需要用户继承 `SpeechRecognitionListener`，并且非常依赖于其中的两个核心回调来应对语义结果：

```python
import json
from asr import speech_recognizer
from common import credential

class MySpeechRecognitionListener(speech_recognizer.SpeechRecognitionListener):
    def on_recognition_start(self, response):
        pass
        
    def on_sentence_begin(self, response):
        """一段话开始识别（相当于 slice_type: 0）"""
        pass

    def on_recognition_result_change(self, response):
        """识别中间结果变化（相当于 slice_type: 1），此时的结果是不可靠的临时态"""
        pass

    def on_sentence_end(self, response):
        """一句话识别结束（相当于 slice_type: 2），此时结果稳态，可以交给 LLM 处理"""
        pass
```

## 4. 音频推送机制
调用 `recognizer.start()` 后，使用 `recognizer.write(content)` 不断向服务端写入 PCM 音频流。
> **防坑警告**: 官方在 Python 示例中明确写了 `#sleep模拟实际实时语音发送间隔 time.sleep(0.02)`，腾讯云的引擎对发送速率非常苛刻，如果是读取文件模拟测试，**千万不要在一瞬间把几兆的音频直接 while 循环 push 进去**，必须按 1:1 的速率 sleep，否则会直接连接异常报错 `4000`。

---

## 5. Reference: Official API Spec
> **防幻觉红线**: 以下为官方原始 API 规范文档备份。当上方精简版参数无法满足需求或出现争议时，请**绝对以本段下方的官方原始定义为准**。

```markdown
# 实时语音识别（WebSocket）
此接口为实时语音识别接口，在参数风格、错误码等方面有区别于云 API 接口，请知悉。

## 接口要求
- **请求协议**: wss 协议
- **请求地址**: `wss://asr.cloud.tencent.com/asr/v2/<appid>?{请求参数}`
- **接口鉴权**: 签名鉴权机制。
- **数据发送**: 建议200ms发送200ms时长（即1:1实时率）的数据包，对应 PCM 大小为：8k 采样率3200字节，16k采样率6400字节。音频发送速率过快超过1:1实时率或者音频数据包之间发送间隔超过6秒，可能导致引擎出错，后台将返回错误并主动断开连接。

### 识别结果 Result 结构体格式为：
| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| slice_type | Integer | 识别结果类型：<br>0：一段话开始识别。<br>1：一段话识别中，voice_text_str 为非稳态结果（该段识别结果还可能变化）。<br>2：一段话识别结束，voice_text_str 为稳态结果（该段识别结果不再变化）。<br>注意：如果需要0和2配对返回，需要设置 filter_empty_result=0。一般在外呼场景需要配对返回，通过 slice_type=0 来判断是否有人声出现。 |
| voice_text_str | String | 当前一段话文本结果。 |
| final | Integer | 该字段返回1时表示音频流全部识别结束。 |

### 握手阶段参数说明
| 参数名称 | 必填 | 描述 |
| --- | --- | --- |
| secretid | 是 | 腾讯云注册账号的密钥 secretid。 |
| timestamp | 是 | 当前 UNIX 时间戳，单位为秒。 |
| expired | 是 | 签名的有效期截止时间 UNIX 时间戳。 |
| nonce | 是 | 随机正整数。用户需自行生成，最长10位。 |
| engine_model_type | 是 | 引擎模型类型<br>电话场景：<br>8k_zh：中文电话通用。<br>8k_zh_large：中文电话场景专用大模型引擎【大模型版】。<br>非电话场景：<br>16k_zh_en：中英粤+9种方言大模型引擎。<br>16k_zh_large：普方英大模型引擎。<br>16k_multi_lang：多语种大模型引擎。 |
| voice_id | 是 | 音频流全局唯一标识。 |
| voice_format | 否 | 语音编码方式，默认值为4。1：pcm；4：speex；8：mp3；12：wav。 |
| needvad | 否 | 0：关闭 vad，1：开启 vad，默认为0。建议客户音频超过60s时，开启 vad，提升切分效果。 |
| filter_dirty | 否 | 是否过滤脏词。0：不过滤；1：过滤；2：将脏词替换为“ * ” |
| hotword_list | 否 | 临时热词表：该参数用于提升识别准确率。单个热词限制："热词\|权重"，如：“腾讯云\|5”。权重[1-11]或者100。 |
| signature | 是 | 接口签名参数 |

### 签名生成
1. 对除 signature 之外的所有参数按字典序进行排序，拼接请求 URL （不包含协议部分：wss://）作为签名原文：
`asr.cloud.tencent.com/asr/v2/125922***?engine_model_type=16k_zh&expired=1673494772&needvad=1&nonce=1673408372&secretid=*****&timestamp=1673408372&voice_format=1&voice_id=c64385ee-3e5c`
2. 对签名原文使用 SecretKey 进行 HMAC-SHA1 加密，之后再进行 base64 编码。
3. 将 signature 值进行 **urlencode（必须进行 URL 编码，编码函数必须要支持对+、=等特殊字符的编码，否则将导致鉴权失败偶发）**后拼接得到最终请求 URL。

### 上传数据
音频流上传完成之后，客户端需发送以下内容的 text message，通知后台结束识别。
`{"type": "end"}`
```