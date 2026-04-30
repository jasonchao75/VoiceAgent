# Qwen-ASR-Realtime 实时流式识别 (Python SDK) 规范

> **极度推荐方案**: 阿里云提供了基于 WebSocket 的真正双向流式识别接口，官方强烈推荐使用 DashScope Python SDK 中的 `OmniRealtimeConversation` 进行对接，内置了事件分发和状态机。

## 1. 核心信息与鉴权
- **依赖库 (Python)**: `dashscope` (需要版本 >= 1.25.6)
- **核心类**: `OmniRealtimeConversation`, `OmniRealtimeCallback`, `TranscriptionParams`
- **WebSocket URL**: 
  - 中国内地: `wss://dashscope.aliyuncs.com/api-ws/v1/realtime`
- **鉴权**: 默认从环境变量 `DASHSCOPE_API_KEY` 中读取。

## 2. SDK 回调与事件处理 (Callback)
与传统的单向请求不同，双向流式识别重度依赖事件回调，你需要继承 `OmniRealtimeCallback` 并重写事件分发：

```python
from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback

class MyCallback(OmniRealtimeCallback):
    def __init__(self, conversation):
        self.conversation = conversation
        self.handlers = {
            'session.created': self._handle_session_created,
            # 一句话最终识别结果 (稳态)
            'conversation.item.input_audio_transcription.completed': self._handle_final_text,
            # 一句话中间识别结果 (临时态)
            'conversation.item.input_audio_transcription.text': self._handle_stash_text,
            'input_audio_buffer.speech_started': lambda r: print('======Speech Start======'),
            'input_audio_buffer.speech_stopped': lambda r: print('======Speech Stop======')
        }

    def on_event(self, response):
        try:
            handler = self.handlers.get(response['type'])
            if handler:
                handler(response)
        except Exception as e:
            print(f'[Error] {e}')

    def _handle_session_created(self, response):
        print(f"Start session: {response['session']['id']}")

    def _handle_final_text(self, response):
        # 提取稳态结果，传给下游 VoiceAgent 的 LLM
        print(f"Final recognized text: {response['transcript']}")

    def _handle_stash_text(self, response):
        # 提取中间结果，供前端展示
        print(f"Got stash result: {response['stash']}")
```

## 3. 实例化与会话配置 (Session Configuration)

```python
from dashscope.audio.qwen_omni import TranscriptionParams, MultiModality

# 1. 实例化会话
conversation = OmniRealtimeConversation(
    model='qwen3-asr-flash-realtime',
    url='wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
    callback=MyCallback(conversation=None)
)
conversation.callback.conversation = conversation

# 2. 建立 WebSocket 连接
conversation.connect()

# 3. 设置会话参数 (非常关键的 VAD 与语言配置)
transcription_params = TranscriptionParams(
    language='zh',           # 音频源语言，也可选 en, ja 等
    sample_rate=16000,       # 采样率：16000 或 8000
    input_audio_format="pcm" # pcm 或 opus
)

conversation.update_session(
    output_modalities=[MultiModality.TEXT], # 仅输出文本
    enable_turn_detection=True,             # 开启服务端 VAD
    turn_detection_type="server_vad",
    turn_detection_threshold=0.0,           # VAD 灵敏度 (-1 到 1)，推荐 0.0
    turn_detection_silence_duration_ms=400, # VAD 静音断句阈值 (推荐 400ms - 800ms)
    enable_input_audio_transcription=True,
    transcription_params=transcription_params
)
```

## 4. 音频流发送与结束
启动会话后，可以通过 `append_audio` 源源不断地压入 Base64 编码后的音频字节块：

```python
import base64

# 模拟读取音频流发送
with open("test.wav", "rb") as f:
    while True:
        chunk = f.read(3200) # 假设 100ms
        if not chunk:
            break
        # 注意: append_audio 需要接收的是 base64 字符串
        audio_b64 = base64.b64encode(chunk).decode('utf-8')
        conversation.append_audio(audio_b64)
        time.sleep(0.1) 

# 发送完毕后通知服务端结束
conversation.end_session()
```
> **注意**: 如果开启了服务端 VAD (`enable_turn_detection=True`)，无需调用 `commit()`，服务端会自动进行断句。

---

## 5. Reference: Official API Spec
> **防幻觉红线**: 以下为官方原始 SDK 文档备份片段。当上方精简版参数无法满足需求或出现争议时，请**绝对以本段下方的官方原始定义为准**。

```markdown
# 实时语音识别（Qwen-ASR-Realtime）Python SDK-API参考

## 参数 (OmniRealtimeConversation)
`model` str 指定要使用的模型名称 (qwen3-asr-flash-realtime)
`url` str 语音识别服务地址：`wss://dashscope.aliyuncs.com/api-ws/v1/realtime`

## update_session 参数
`enable_turn_detection` bool: 是否开启服务端语音活动检测（VAD）。关闭后，需手动调用 commit()。默认 True。
`turn_detection_threshold` float: VAD检测阈值。推荐将该值设为0.0。取值范围：[-1, 1]。
`turn_detection_silence_duration_ms` int: VAD断句检测阈值（ms）。静音持续时长超过该阈值将被认为是语句结束。推荐将该值设为 400。取值范围：[200, 6000]。
`transcription_params`: TranscriptionParams 配置。

## TranscriptionParams 参数
`language`: zh, en, ja, de, ko, 等28种语言。
`sample_rate`: 16000 或 8000。服务端一律升采样到 16000Hz 识别。
`input_audio_format`: pcm 或 opus。

## 关键接口
`def connect(self) -> None`: 和服务端创建连接。触发 `session.created` 和 `session.updated`。
`def append_audio(self, audio_b64: str) -> None`: 将 Base64 编码后的音频数据片段追加到云端输入音频缓冲区。
`def commit(self) -> None`: enable_turn_detection 设为 True 时禁用。
`def end_session(self, timeout: int = 20) -> None`: 发送完音频后调用，通知结束会话。
```