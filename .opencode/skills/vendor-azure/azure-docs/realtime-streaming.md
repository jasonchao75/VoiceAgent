# Azure Realtime Streaming (Speech SDK) 规范

> **推荐方案**: Azure 官方强烈推荐使用其 `azure-cognitiveservices-speech` SDK 进行实时流式识别，因为它内置了重连、分段、和协议管理。手写 WebSocket 极易出现连接中断问题。

## 1. 核心信息与鉴权
- **依赖库 (Python)**: `azure-cognitiveservices-speech` (`pip install azure-cognitiveservices-speech`)
- **初始化配置**: 需要传入 `subscription` (API Key) 和 `region` (区域代码)。

```python
import azure.cognitiveservices.speech as speechsdk

# 1. 鉴权配置
speech_config = speechsdk.SpeechConfig(subscription="YourSpeechKey", region="YourSpeechRegion")

# 2. 语言设置 (必须)
speech_config.speech_recognition_language = "zh-CN"
```

## 2. 高级配置参数 (语言检测 / 自定义终点 / 热词)
除了基本的区域和主语言，Azure 提供了针对复杂场景的高级能力：

### 2.1 连续语言检测 (Continuous Language ID)
如果你不知道用户会说哪种语言，或者用户在会话期间会切换语言，你可以配置多个候选语言，开启**连续语言检测**：
```python
# 必须设置为 Continuous 才能在连续语音中动态识别语言变化
speech_config.set_property(property_id=speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode, value='Continuous')

# 配置最多 10 个候选语言
auto_detect_source_language_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=["en-US", "de-DE", "zh-CN"])

# 实例化时传入
speech_recognizer = speechsdk.SpeechRecognizer(
    speech_config=speech_config, 
    auto_detect_source_language_config=auto_detect_source_language_config,
    audio_config=audio_config
)
```

### 2.2 自定义终端 (Custom Endpoint)
如果使用了 Azure 训练的专属语音模型 (Custom Speech)，必须传入 `endpoint_id`：
```python
speech_config.endpoint_id = "YourEndpointId"
```

### 2.3 短语列表 / 热词提升 (Phrase List)
不需要重新训练模型，即可直接干预当前 Session，提升专有词汇的识别率（最多支持 500 个短语）：
```python
# 在 speech_recognizer 实例化之后添加
phrase_list_grammar = speechsdk.PhraseListGrammar.from_recognizer(speech_recognizer)
phrase_list_grammar.addPhrase("OpenCode")
phrase_list_grammar.addPhrase("VoiceAgent")
# 可选：设置权重 (0.0=禁用, 1.0=默认, 2.0=最高影响)
# phrase_list_grammar.setWeight(2.0)
```

## 3. 断句与 VAD (Semantic Segmentation)
为了解决长音频“不说话不断句”或者“说话太快不加标点”的问题，Azure 提供了针对连续流式识别的**语义分段 (Semantic Segmentation)**：

```python
# 开启语义分段 (利用标点符号和语义来更智能地断句，降低延迟和防止一大段不返回)
speech_config.set_property(speechsdk.PropertyId.Speech_SegmentationStrategy, "Semantic")
```

同时，可以通过参数调整 VAD 静音超时机制：
- `Speech_SegmentationSilenceTimeoutMs` (分割静音超时): 设置多长时间不说话就强制判定句子结束，默认为 `500` ms。如果你需要识别连串的数字(容易有停顿)，可以调大至 `2000`。
- `SpeechServiceConnection_InitialSilenceTimeoutMs` (初始静音超时): 等待用户开始说话的最大时间，如果只是偶尔下发指令，单次识别可设为 `5000`。

## 3. 流式音频输入 (Push Stream)
如果在 VoiceAgent 中通过 WebSocket 接收来自前端的 PCM 数据流，需要使用 `PushAudioInputStream` 来喂数据，而不是直接读取文件：

```python
# 创建 Push 流 (例如 16KHz 16bit 单声道 PCM)
stream_format = speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

# 实例化识别器
speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
```
当你收到前端的音频 Buffer，调用 `push_stream.write(buffer)` 即可。

## 4. 连续识别事件监听
Voice Agent 通常是常连接，需要使用 `start_continuous_recognition()`，并通过事件回调接收结果：

```python
# 中间结果回调 (Partial)
speech_recognizer.recognizing.connect(lambda evt: print(f'RECOGNIZING: {evt.result.text}'))

# 最终结果回调 (Final)
def handle_final(evt):
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print(f'RECOGNIZED: {evt.result.text}')

speech_recognizer.recognized.connect(handle_final)

# 开始识别
speech_recognizer.start_continuous_recognition()
```

## 5. 垃圾回收
- 当会话结束时，必须调用 `speech_recognizer.stop_continuous_recognition()` 以释放资源。

---

## 6. Reference: Official SDK Documentation (Excerpts)
> **防幻觉红线**: 以下为官方原始 SDK 文档备份片段。当上方精简版参数无法满足需求或出现争议时，请**绝对以本段下方的官方原始定义为准**。

```markdown
## Semantic segmentation
Semantic segmentation is a speech recognition segmentation strategy that's designed to mitigate issues associated with silence-based segmentation:

- Under-segmentation: When users speak for a long time without pauses, they can see a long sequence of text without breaks ("wall of text"), which severely degrades their readability experience.
- Over-segmentation: When a user pauses for a short time, the silence detection mechanism can segment incorrectly.

Instead of only relying on silence timeouts, semantic segmentation mostly segments and returns final results when it detects sentence-ending punctuation (such as '.' or '?'). This improves the user experience with higher-quality, semantically complete segments and prevents long intermediate results.

To use semantic segmentation, you need to set the following property on the SpeechConfig instance used to create a SpeechRecognizer:
`speech_config.set_property(speechsdk.PropertyId.Speech_SegmentationStrategy, "Semantic")`

## Use continuous recognition
In contrast to single-shot recognition, you use continuous recognition when you want to control when to stop recognizing. It requires you to connect to EventSignal to get the recognition results.
- `recognizing`: Signal for events that contain intermediate recognition results.
- `recognized`: Signal for events that contain final recognition results, which indicate a successful recognition attempt.
- `session_started`: Signal for events that indicate the start of a recognition session (operation).
- `canceled`: Signal for events that contain canceled recognition results.
```
